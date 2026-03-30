import json
import hashlib
import hmac
import logging
import os
import secrets
import threading
from flask import Blueprint, request, jsonify
from backend.db import get_db, use_db
from backend.models import (
    get_recipe, search_recipes, insert_recipe, insert_tags,
    update_recipe, delete_recipe, get_tag_stats, get_overview_stats,
    _insert_tags_on_conn
)
from backend.tag_engine import detect_cuisine, compute_tags
from backend.recipe_generator import (
    build_generation_plan, create_batch, run_generation, get_generation_status
)
from config import DB_PATH

admin_bp = Blueprint('admin', __name__)


def _check_admin(req):
    token = req.headers.get('X-Admin-Token') or req.args.get('token')
    if not token:
        return False
    with use_db() as db:
        row = db.execute("SELECT token FROM admin_sessions WHERE token = ?", (token,)).fetchone()
        return row is not None


@admin_bp.route('/login', methods=['POST'])
def login():
    from config import ADMIN_PASSWORD
    data = request.get_json() or {}
    password = data.get('password', '')
    expected = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
    provided = hashlib.sha256(password.encode()).hexdigest()
    if not hmac.compare_digest(provided, expected):
        logging.warning("Failed admin login attempt from %s", request.remote_addr)
        return jsonify({'error': 'Invalid password'}), 401

    token = secrets.token_hex(32)
    with use_db() as db:
        db.execute("INSERT INTO admin_sessions (token) VALUES (?)", (token,))
        db.commit()
    return jsonify({'token': token})


@admin_bp.route('/stats', methods=['GET'])
def stats():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(get_overview_stats())


@admin_bp.route('/llm-savings', methods=['GET'])
def llm_savings():
    """Show how many LLM calls were saved by the recipe cache."""
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        rows = db.execute("""
            SELECT endpoint, served_from,
                   COUNT(*) as requests,
                   SUM(recipe_count) as recipes
            FROM llm_cost_log
            GROUP BY endpoint, served_from
            ORDER BY endpoint, served_from
        """).fetchall()
        totals = db.execute("""
            SELECT served_from,
                   COUNT(*) as requests,
                   SUM(recipe_count) as recipes
            FROM llm_cost_log
            GROUP BY served_from
        """).fetchall()
        # Count cached recipes
        cached_count = db.execute(
            "SELECT COUNT(*) FROM recipes WHERE source = 'llm_cached' AND status = 'active'"
        ).fetchone()[0]
    breakdown = [dict(r) for r in rows]
    summary = {r['served_from']: {'requests': r['requests'], 'recipes': r['recipes']} for r in totals}
    db_saved = summary.get('db', {}).get('requests', 0) + summary.get('db_cache', {}).get('requests', 0)
    llm_calls = summary.get('llm', {}).get('requests', 0)
    total = db_saved + llm_calls
    return jsonify({
        'breakdown': breakdown,
        'summary': summary,
        'cached_recipes': cached_count,
        'total_requests': total,
        'db_served': db_saved,
        'llm_calls': llm_calls,
        'savings_pct': round(db_saved / total * 100, 1) if total > 0 else 0
    })


@admin_bp.route('/tags', methods=['GET'])
def tag_stats():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(get_tag_stats())


@admin_bp.route('/recipes', methods=['GET'])
def list_admin_recipes():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    filters = {k: v for k, v in {
        'meal_type': request.args.get('meal_type'),
        'cuisine': request.args.get('cuisine'),
        'category': request.args.get('category'),
        'search': request.args.get('search'),
    }.items() if v}

    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(max(1, int(request.args.get('per_page', 50))), 200)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid pagination parameters'}), 400

    with use_db() as db:
        conditions = ["1=1"]
        params = []
        status_filter = request.args.get('status', 'active')
        if status_filter != 'all':
            conditions.append("status = ?")
            params.append(status_filter)

        # Safe column filter — only allow known columns
        safe_columns = {'meal_type', 'cuisine', 'category'}
        for k, v in filters.items():
            if k == 'search':
                conditions.append("name LIKE ?")
                params.append(f"%{v}%")
            elif k in safe_columns:
                conditions.append(f"{k} = ?")
                params.append(v)

        where = " AND ".join(conditions)
        count = db.execute(f"SELECT COUNT(*) FROM recipes WHERE {where}", params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = db.execute(
            f"SELECT id, name, category, cuisine, meal_type, calories, protein, carbs, fat, status, created_at FROM recipes WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

    return jsonify({
        'recipes': [dict(r) for r in rows],
        'total': count,
        'page': page,
        'per_page': per_page,
        'pages': (count + per_page - 1) // per_page
    })


@admin_bp.route('/recipes', methods=['POST'])
def create_recipe():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Recipe name required'}), 400

    data['source'] = 'manual'
    cuisine_info = detect_cuisine(data)
    data.setdefault('cuisine', cuisine_info['cuisine'])
    data.setdefault('country_of_origin', cuisine_info['country'])
    data.setdefault('region', cuisine_info['region'])

    if data.get('total_time_min', 0) == 0:
        data['total_time_min'] = data.get('prep_time_min', 0) + data.get('cook_time_min', 0)

    tags = compute_tags(data)
    recipe_id = insert_recipe(data, tags_dict=tags)  # atomic insert

    return jsonify({'id': recipe_id, 'message': 'Recipe created'}), 201


@admin_bp.route('/recipes/<int:recipe_id>', methods=['PUT'])
def edit_recipe(recipe_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    recipe = get_recipe(recipe_id)
    if not recipe:
        return jsonify({'error': 'Recipe not found'}), 404

    update_recipe(recipe_id, data)

    # Re-tag if macro/ingredient data changed
    retag_fields = {'calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar',
                    'ingredients', 'category', 'meal_type', 'allergens', 'name'}
    if retag_fields & set(data.keys()):
        updated = get_recipe(recipe_id)
        tags = compute_tags(updated)
        with use_db() as db:
            db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
            _insert_tags_on_conn(db, recipe_id, tags)
            db.commit()

    return jsonify({'message': 'Recipe updated'})


@admin_bp.route('/recipes/<int:recipe_id>', methods=['DELETE'])
def remove_recipe(recipe_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    delete_recipe(recipe_id)
    return jsonify({'message': 'Recipe archived'})


@admin_bp.route('/retag', methods=['POST'])
def retag_all():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    with use_db() as db:
        recipes = db.execute("SELECT id FROM recipes WHERE status = 'active'").fetchall()

    count = 0
    # Process in batches of 50 within single transactions
    recipe_ids = [row['id'] for row in recipes]
    batch_size = 50
    for i in range(0, len(recipe_ids), batch_size):
        batch = recipe_ids[i:i + batch_size]
        with use_db() as db:
            for rid in batch:
                recipe = get_recipe(rid)
                if not recipe:
                    continue
                tags = compute_tags(recipe)
                db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (rid,))
                _insert_tags_on_conn(db, rid, tags)
                count += 1
            db.commit()

    return jsonify({'message': f'Re-tagged {count} recipes'})


@admin_bp.route('/api-keys', methods=['GET'])
def list_api_keys():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        rows = db.execute(
            "SELECT id, provider, key_name, SUBSTR(api_key, 1, 8) || '...' as key_preview, model, is_active, usage_count, last_used_at, created_at FROM api_keys ORDER BY provider, key_name"
        ).fetchall()
    return jsonify({'keys': [dict(r) for r in rows]})


@admin_bp.route('/api-keys', methods=['POST'])
def add_api_key():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data or not data.get('provider') or not data.get('api_key'):
        return jsonify({'error': 'Provider and api_key required'}), 400

    with use_db() as db:
        try:
            db.execute("""
                INSERT INTO api_keys (provider, key_name, api_key, model, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (
                data['provider'],
                data.get('key_name', 'default'),
                data['api_key'],
                data.get('model', ''),
                1 if data.get('is_active', True) else 0
            ))
            db.commit()
        except Exception as e:
            return jsonify({'error': f'Key already exists for this provider/name: {e}'}), 409
    return jsonify({'message': 'API key added'}), 201


@admin_bp.route('/api-keys/<int:key_id>', methods=['PUT'])
def update_api_key(key_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    with use_db() as db:
        sets = []
        params = []
        # Only allow known fields
        for field in ('api_key', 'model', 'key_name'):
            if field in data:
                sets.append(f"{field} = ?")
                params.append(data[field])
        if 'is_active' in data:
            sets.append("is_active = ?")
            params.append(1 if data['is_active'] else 0)

        if sets:
            params.append(key_id)
            db.execute(f"UPDATE api_keys SET {', '.join(sets)} WHERE id = ?", params)
            db.commit()
    return jsonify({'message': 'API key updated'})


@admin_bp.route('/api-keys/<int:key_id>', methods=['DELETE'])
def delete_api_key(key_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        db.commit()
    return jsonify({'message': 'API key deleted'})


def get_active_api_key(provider='anthropic'):
    """Get the active API key for a provider from the database."""
    with use_db() as db:
        row = db.execute(
            "SELECT api_key, model FROM api_keys WHERE provider = ? AND is_active = 1 ORDER BY id LIMIT 1",
            (provider,)
        ).fetchone()
        return dict(row) if row else None


def record_api_key_usage(provider='anthropic'):
    """Record that an API key was used (call after successful LLM call)."""
    try:
        with use_db() as db:
            db.execute(
                "UPDATE api_keys SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP WHERE provider = ? AND is_active = 1",
                (provider,)
            )
            db.commit()
    except Exception:
        logging.debug("Failed to record API key usage", exc_info=True)


@admin_bp.route('/generate/start', methods=['POST'])
def start_generation():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    batch_size = data.get('batch_size', 10)
    max_items = data.get('max_items', None)
    provider = data.get('provider', None)  # 'anthropic' or 'ollama'
    model = data.get('model', None)  # e.g. 'claude-sonnet-4-6', 'llama3.1'

    plan = build_generation_plan(batch_size)
    if max_items:
        plan = plan[:max_items]
    batch_id = create_batch(plan, batch_id=None)

    thread = threading.Thread(
        target=run_generation,
        args=(batch_id, batch_size, max_items, provider, model),
        daemon=True
    )
    thread.start()

    return jsonify({
        'batch_id': batch_id,
        'total_prompts': len(plan),
        'expected_recipes': sum(p['count'] for p in plan),
        'provider': provider or 'auto',
        'model': model or 'default',
        'message': 'Generation started in background'
    })


@admin_bp.route('/generate/status', methods=['GET'])
def generation_status():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    batch_id = request.args.get('batch_id')
    status = get_generation_status(batch_id)
    if status is None:
        return jsonify({'error': 'Batch not found'}), 404
    return jsonify(status)


# ---------------------------------------------------------------------------
#  Advanced Admin Endpoints
# ---------------------------------------------------------------------------


@admin_bp.route('/users', methods=['GET'])
def list_users():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(max(1, int(request.args.get('per_page', 50))), 200)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid pagination'}), 400

    search = request.args.get('search', '')
    with use_db() as db:
        conditions = ["1=1"]
        params = []
        if search:
            conditions.append("(email LIKE ? OR name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " AND ".join(conditions)

        count = db.execute(f"SELECT COUNT(*) FROM users WHERE {where}", params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = db.execute(
            f"""SELECT id, email, name, created_at, updated_at,
                       LENGTH(profile_data) as profile_size,
                       LENGTH(user_data) as data_size
                FROM users WHERE {where}
                ORDER BY id DESC LIMIT ? OFFSET ?""",
            params + [per_page, offset]
        ).fetchall()

        # Get session counts per user
        user_ids = [r['id'] for r in rows]
        session_counts = {}
        if user_ids:
            placeholders = ','.join(['?'] * len(user_ids))
            sess_rows = db.execute(
                f"SELECT user_id, COUNT(*) as cnt FROM user_sessions WHERE user_id IN ({placeholders}) GROUP BY user_id",
                user_ids
            ).fetchall()
            session_counts = {r['user_id']: r['cnt'] for r in sess_rows}

    users = []
    for r in rows:
        u = dict(r)
        u['active_sessions'] = session_counts.get(r['id'], 0)
        users.append(u)

    return jsonify({
        'users': users,
        'total': count,
        'page': page,
        'per_page': per_page,
        'pages': (count + per_page - 1) // per_page
    })


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_detail(user_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    with use_db() as db:
        row = db.execute(
            "SELECT id, email, name, profile_data, created_at, updated_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'User not found'}), 404
        user = dict(row)
        try:
            user['profile_data'] = json.loads(user['profile_data'] or '{}')
        except (json.JSONDecodeError, TypeError):
            user['profile_data'] = {}

        sessions = db.execute(
            "SELECT token, created_at FROM user_sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        user['sessions'] = [{'token_preview': s['token'][:12] + '...', 'created_at': s['created_at']} for s in sessions]

    return jsonify(user)


@admin_bp.route('/users/<int:user_id>/sessions', methods=['DELETE'])
def revoke_user_sessions(user_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        db.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        db.commit()
    return jsonify({'message': 'All sessions revoked'})


@admin_bp.route('/system', methods=['GET'])
def system_info():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    with use_db() as db:
        # Database stats
        recipe_count = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]
        archived_count = db.execute("SELECT COUNT(*) FROM recipes WHERE status != 'active'").fetchone()[0]
        tag_count = db.execute("SELECT COUNT(*) FROM recipe_tags").fetchone()[0]
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        user_session_count = db.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        admin_session_count = db.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0]
        api_key_count = db.execute("SELECT COUNT(*) FROM api_keys WHERE is_active = 1").fetchone()[0]
        gen_job_count = db.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0]
        llm_log_count = db.execute("SELECT COUNT(*) FROM llm_cost_log").fetchone()[0]

        # Recent activity
        recent_recipes = db.execute(
            "SELECT COUNT(*) FROM recipes WHERE created_at > datetime('now', '-7 days')"
        ).fetchone()[0]
        recent_users = db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-7 days')"
        ).fetchone()[0]

        # DB file size
        db_size = 0
        try:
            db_size = os.path.getsize(DB_PATH)
        except OSError:
            pass

        # Table sizes
        tables = ['recipes', 'recipe_tags', 'users', 'user_sessions', 'admin_sessions',
                  'api_keys', 'generation_jobs', 'generation_queue', 'llm_cost_log']
        table_stats = {}
        for t in tables:
            try:
                cnt = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                table_stats[t] = cnt
            except Exception:
                table_stats[t] = 0

    return jsonify({
        'database': {
            'path': DB_PATH,
            'size_bytes': db_size,
            'size_mb': round(db_size / (1024 * 1024), 2) if db_size else 0,
            'tables': table_stats,
        },
        'counts': {
            'active_recipes': recipe_count,
            'archived_recipes': archived_count,
            'tags': tag_count,
            'users': user_count,
            'user_sessions': user_session_count,
            'admin_sessions': admin_session_count,
            'active_api_keys': api_key_count,
            'generation_jobs': gen_job_count,
            'llm_log_entries': llm_log_count,
        },
        'recent_7d': {
            'new_recipes': recent_recipes,
            'new_users': recent_users,
        }
    })


@admin_bp.route('/analytics', methods=['GET'])
def analytics():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    with use_db() as db:
        # Nutrition distribution (histogram buckets)
        cal_dist = db.execute("""
            SELECT
                CASE
                    WHEN calories < 200 THEN '0-199'
                    WHEN calories < 400 THEN '200-399'
                    WHEN calories < 600 THEN '400-599'
                    WHEN calories < 800 THEN '600-799'
                    ELSE '800+'
                END as bucket,
                COUNT(*) as cnt
            FROM recipes WHERE status = 'active'
            GROUP BY bucket ORDER BY bucket
        """).fetchall()

        prot_dist = db.execute("""
            SELECT
                CASE
                    WHEN protein < 10 THEN '0-9g'
                    WHEN protein < 20 THEN '10-19g'
                    WHEN protein < 30 THEN '20-29g'
                    WHEN protein < 40 THEN '30-39g'
                    WHEN protein < 50 THEN '40-49g'
                    ELSE '50g+'
                END as bucket,
                COUNT(*) as cnt
            FROM recipes WHERE status = 'active'
            GROUP BY bucket ORDER BY bucket
        """).fetchall()

        # Difficulty distribution
        diff_dist = db.execute("""
            SELECT difficulty, COUNT(*) as cnt
            FROM recipes WHERE status = 'active'
            GROUP BY difficulty ORDER BY cnt DESC
        """).fetchall()

        # Time distribution
        time_dist = db.execute("""
            SELECT
                CASE
                    WHEN total_time_min <= 15 THEN '0-15 min'
                    WHEN total_time_min <= 30 THEN '16-30 min'
                    WHEN total_time_min <= 60 THEN '31-60 min'
                    WHEN total_time_min <= 120 THEN '61-120 min'
                    ELSE '120+ min'
                END as bucket,
                COUNT(*) as cnt
            FROM recipes WHERE status = 'active'
            GROUP BY bucket ORDER BY bucket
        """).fetchall()

        # Top 10 cuisines
        top_cuisines = db.execute("""
            SELECT cuisine, COUNT(*) as cnt
            FROM recipes WHERE status = 'active'
            GROUP BY cuisine ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Recipe creation over time (last 30 days)
        daily_created = db.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM recipes
            WHERE created_at > datetime('now', '-30 days')
            GROUP BY day ORDER BY day
        """).fetchall()

        # Source distribution
        source_dist = db.execute("""
            SELECT COALESCE(source, 'unknown') as source, COUNT(*) as cnt
            FROM recipes WHERE status = 'active'
            GROUP BY source ORDER BY cnt DESC
        """).fetchall()

        # Macro averages by meal type
        macro_by_meal = db.execute("""
            SELECT meal_type,
                   COUNT(*) as cnt,
                   ROUND(AVG(calories)) as avg_cal,
                   ROUND(AVG(protein)) as avg_prot,
                   ROUND(AVG(carbs)) as avg_carb,
                   ROUND(AVG(fat)) as avg_fat
            FROM recipes WHERE status = 'active'
            GROUP BY meal_type ORDER BY cnt DESC
        """).fetchall()

        # User registrations over time (last 30 days)
        user_signups = db.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM users
            WHERE created_at > datetime('now', '-30 days')
            GROUP BY day ORDER BY day
        """).fetchall()

    return jsonify({
        'calorie_distribution': [dict(r) for r in cal_dist],
        'protein_distribution': [dict(r) for r in prot_dist],
        'difficulty_distribution': [dict(r) for r in diff_dist],
        'time_distribution': [dict(r) for r in time_dist],
        'top_cuisines': [dict(r) for r in top_cuisines],
        'daily_recipes_created': [dict(r) for r in daily_created],
        'source_distribution': [dict(r) for r in source_dist],
        'macro_by_meal_type': [dict(r) for r in macro_by_meal],
        'user_signups': [dict(r) for r in user_signups],
    })


@admin_bp.route('/audit', methods=['GET'])
def recipe_audit():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    with use_db() as db:
        # Missing descriptions
        missing_desc = db.execute("""
            SELECT id, name, cuisine, meal_type FROM recipes
            WHERE status = 'active' AND (description IS NULL OR description = '')
            LIMIT 50
        """).fetchall()

        # Missing ingredients or steps
        missing_content = db.execute("""
            SELECT id, name, cuisine, meal_type FROM recipes
            WHERE status = 'active' AND (ingredients = '[]' OR steps = '[]' OR ingredients IS NULL OR steps IS NULL)
            LIMIT 50
        """).fetchall()

        # Zero-calorie recipes (likely data errors)
        zero_cal = db.execute("""
            SELECT id, name, cuisine, meal_type, calories, protein FROM recipes
            WHERE status = 'active' AND calories = 0
            LIMIT 50
        """).fetchall()

        # Extremely high calorie (>1500 per serving)
        high_cal = db.execute("""
            SELECT id, name, cuisine, meal_type, calories, protein, carbs, fat FROM recipes
            WHERE status = 'active' AND calories > 1500
            ORDER BY calories DESC LIMIT 50
        """).fetchall()

        # Zero protein
        zero_protein = db.execute("""
            SELECT id, name, cuisine, meal_type, calories, protein FROM recipes
            WHERE status = 'active' AND protein = 0 AND category NOT IN ('vegan', 'vegetarian')
            LIMIT 50
        """).fetchall()

        # Macro imbalance: calories don't roughly match macros
        macro_mismatch = db.execute("""
            SELECT id, name, calories, protein, carbs, fat,
                   (protein * 4 + carbs * 4 + fat * 9) as computed_cal
            FROM recipes
            WHERE status = 'active'
              AND calories > 0
              AND ABS(calories - (protein * 4 + carbs * 4 + fat * 9)) > calories * 0.3
            ORDER BY ABS(calories - (protein * 4 + carbs * 4 + fat * 9)) DESC
            LIMIT 50
        """).fetchall()

        # Recipes without tags
        no_tags = db.execute("""
            SELECT r.id, r.name, r.cuisine, r.meal_type FROM recipes r
            LEFT JOIN recipe_tags rt ON rt.recipe_id = r.id
            WHERE r.status = 'active' AND rt.id IS NULL
            LIMIT 50
        """).fetchall()

        # Potential duplicates (same name)
        dupes = db.execute("""
            SELECT name, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
            FROM recipes WHERE status = 'active'
            GROUP BY LOWER(name) HAVING cnt > 1
            ORDER BY cnt DESC LIMIT 30
        """).fetchall()

    return jsonify({
        'missing_description': [dict(r) for r in missing_desc],
        'missing_content': [dict(r) for r in missing_content],
        'zero_calories': [dict(r) for r in zero_cal],
        'high_calories': [dict(r) for r in high_cal],
        'zero_protein': [dict(r) for r in zero_protein],
        'macro_mismatch': [dict(r) for r in macro_mismatch],
        'no_tags': [dict(r) for r in no_tags],
        'potential_duplicates': [dict(r) for r in dupes],
        'summary': {
            'missing_description': len(missing_desc),
            'missing_content': len(missing_content),
            'zero_calories': len(zero_cal),
            'high_calories': len(high_cal),
            'zero_protein': len(zero_protein),
            'macro_mismatch': len(macro_mismatch),
            'no_tags': len(no_tags),
            'potential_duplicates': len(dupes),
        }
    })


@admin_bp.route('/recipes/bulk', methods=['POST'])
def bulk_recipe_action():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or not data.get('ids') or not data.get('action'):
        return jsonify({'error': 'ids and action required'}), 400

    ids = data['ids']
    action = data['action']

    if not isinstance(ids, list) or len(ids) > 500:
        return jsonify({'error': 'ids must be a list of up to 500'}), 400

    allowed_actions = {'archive', 'activate', 'retag'}
    if action not in allowed_actions:
        return jsonify({'error': f'action must be one of: {", ".join(allowed_actions)}'}), 400

    placeholders = ','.join(['?'] * len(ids))
    affected = 0

    with use_db() as db:
        if action == 'archive':
            cur = db.execute(f"UPDATE recipes SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders}) AND status = 'active'", ids)
            affected = cur.rowcount
        elif action == 'activate':
            cur = db.execute(f"UPDATE recipes SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders}) AND status != 'active'", ids)
            affected = cur.rowcount
        elif action == 'retag':
            for rid in ids:
                recipe = get_recipe(rid)
                if recipe:
                    tags = compute_tags(recipe)
                    db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (rid,))
                    _insert_tags_on_conn(db, rid, tags)
                    affected += 1
        db.commit()

    return jsonify({'message': f'{action} applied to {affected} recipes', 'affected': affected})


@admin_bp.route('/maintenance/cleanup', methods=['POST'])
def run_cleanup():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    results = {}
    with use_db() as db:
        # Purge old sessions
        cur = db.execute("DELETE FROM user_sessions WHERE created_at < datetime('now', '-30 days')")
        results['expired_user_sessions'] = cur.rowcount
        cur = db.execute("DELETE FROM admin_sessions WHERE created_at < datetime('now', '-7 days')")
        results['expired_admin_sessions'] = cur.rowcount
        # Purge completed generation jobs older than 30 days
        cur = db.execute("DELETE FROM generation_queue WHERE batch_id IN (SELECT batch_id FROM generation_jobs WHERE status IN ('completed', 'completed_with_errors') AND created_at < datetime('now', '-30 days'))")
        results['old_queue_items'] = cur.rowcount
        cur = db.execute("DELETE FROM generation_jobs WHERE status IN ('completed', 'completed_with_errors') AND created_at < datetime('now', '-30 days')")
        results['old_generation_jobs'] = cur.rowcount
        db.commit()
        # Optimize
        db.execute("PRAGMA optimize")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        results['optimized'] = True

    return jsonify({'message': 'Cleanup completed', 'results': results})


@admin_bp.route('/export/recipes', methods=['GET'])
def export_recipes():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    limit = min(int(request.args.get('limit', 1000)), 5000)
    with use_db() as db:
        rows = db.execute(
            "SELECT * FROM recipes WHERE status = 'active' ORDER BY id LIMIT ?",
            (limit,)
        ).fetchall()

    from backend.models import recipe_to_dict
    recipes = [recipe_to_dict(r) for r in rows]
    return jsonify({'recipes': recipes, 'count': len(recipes)})
