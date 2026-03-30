import json
import hashlib
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
    data = request.get_json() or {}
    password = data.get('password', '')
    expected = hashlib.sha256(b'fitcoach-admin').hexdigest()
    provided = hashlib.sha256(password.encode()).hexdigest()
    if provided != expected:
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

    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 200)

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
        if row:
            db.execute(
                "UPDATE api_keys SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP WHERE provider = ? AND is_active = 1",
                (provider,)
            )
            db.commit()
        return dict(row) if row else None


@admin_bp.route('/users', methods=['GET'])
def list_users():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    search = request.args.get('search', '')
    with use_db() as db:
        conditions = ["1=1"]
        params = []
        if search:
            conditions.append("(u.email LIKE ? OR u.name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " AND ".join(conditions)
        rows = db.execute(f"""
            SELECT u.id, u.email, u.name, u.profile_data, u.created_at, u.updated_at,
                   (SELECT COUNT(*) FROM user_sessions WHERE user_id = u.id) as active_sessions
            FROM users u WHERE {where} ORDER BY u.created_at DESC
        """, params).fetchall()
        total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    users = []
    for r in rows:
        u = dict(r)
        try:
            u['profile'] = json.loads(u.pop('profile_data', '{}') or '{}')
        except (json.JSONDecodeError, TypeError):
            u['profile'] = {}
        users.append(u)
    return jsonify({'users': users, 'total': total})


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        row = db.execute("""
            SELECT u.id, u.email, u.name, u.profile_data, u.user_data, u.created_at, u.updated_at,
                   (SELECT COUNT(*) FROM user_sessions WHERE user_id = u.id) as active_sessions
            FROM users u WHERE u.id = ?
        """, (user_id,)).fetchone()
    if not row:
        return jsonify({'error': 'User not found'}), 404
    user = dict(row)
    try:
        user['profile'] = json.loads(user.pop('profile_data', '{}') or '{}')
    except (json.JSONDecodeError, TypeError):
        user['profile'] = {}
    try:
        user['user_data'] = json.loads(user.get('user_data', '{}') or '{}')
    except (json.JSONDecodeError, TypeError):
        user['user_data'] = {}
    return jsonify(user)


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    with use_db() as db:
        sets = []
        params = []
        for field in ('name', 'email'):
            if field in data:
                sets.append(f"{field} = ?")
                params.append(data[field])
        if sets:
            sets.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)
            db.commit()
    return jsonify({'message': 'User updated'})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        db.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
    return jsonify({'message': 'User deleted'})


@admin_bp.route('/users/<int:user_id>/sessions', methods=['DELETE'])
def revoke_user_sessions(user_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        count = db.execute("SELECT COUNT(*) FROM user_sessions WHERE user_id = ?", (user_id,)).fetchone()[0]
        db.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        db.commit()
    return jsonify({'message': f'Revoked {count} sessions'})


@admin_bp.route('/usage', methods=['GET'])
def usage_overview():
    """Comprehensive usage analytics."""
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    with use_db() as db:
        # Recipe stats
        total_recipes = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]
        recipes_by_source = db.execute("""
            SELECT COALESCE(source, 'unknown') as source, COUNT(*) as count
            FROM recipes WHERE status = 'active' GROUP BY source ORDER BY count DESC
        """).fetchall()

        # User stats
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_sessions = db.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        new_users_7d = db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()[0]
        new_users_30d = db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-30 days')"
        ).fetchone()[0]

        # LLM usage
        llm_total = db.execute("SELECT COUNT(*) FROM llm_cost_log").fetchone()[0]
        llm_by_source = db.execute("""
            SELECT served_from, COUNT(*) as requests, SUM(recipe_count) as recipes
            FROM llm_cost_log GROUP BY served_from
        """).fetchall()
        llm_by_day = db.execute("""
            SELECT DATE(created_at) as day, served_from, COUNT(*) as requests
            FROM llm_cost_log
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY day, served_from ORDER BY day
        """).fetchall()

        # Recipe creation timeline (last 30 days)
        recipes_by_day = db.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM recipes WHERE created_at >= datetime('now', '-30 days') AND status = 'active'
            GROUP BY day ORDER BY day
        """).fetchall()

        # User registration timeline
        users_by_day = db.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM users WHERE created_at >= datetime('now', '-30 days')
            GROUP BY day ORDER BY day
        """).fetchall()

        # Top cuisines & categories
        top_cuisines = db.execute("""
            SELECT cuisine, COUNT(*) as count FROM recipes WHERE status = 'active'
            GROUP BY cuisine ORDER BY count DESC LIMIT 10
        """).fetchall()
        top_categories = db.execute("""
            SELECT category, COUNT(*) as count FROM recipes WHERE status = 'active'
            GROUP BY category ORDER BY count DESC LIMIT 10
        """).fetchall()
        meal_distribution = db.execute("""
            SELECT meal_type, COUNT(*) as count FROM recipes WHERE status = 'active'
            GROUP BY meal_type ORDER BY count DESC
        """).fetchall()

        # Generation jobs summary
        gen_completed = db.execute(
            "SELECT COUNT(*) FROM generation_jobs WHERE status IN ('completed', 'completed_with_errors')"
        ).fetchone()[0]
        gen_running = db.execute(
            "SELECT COUNT(*) FROM generation_jobs WHERE status = 'running'"
        ).fetchone()[0]
        gen_total_recipes = db.execute(
            "SELECT COALESCE(SUM(completed), 0) FROM generation_jobs"
        ).fetchone()[0]

        # DB size
        import os
        from config import DB_PATH
        db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2) if os.path.exists(DB_PATH) else 0

    return jsonify({
        'recipes': {
            'total': total_recipes,
            'by_source': [dict(r) for r in recipes_by_source],
            'by_day': [dict(r) for r in recipes_by_day],
            'top_cuisines': [dict(r) for r in top_cuisines],
            'top_categories': [dict(r) for r in top_categories],
            'meal_distribution': [dict(r) for r in meal_distribution],
        },
        'users': {
            'total': total_users,
            'active_sessions': active_sessions,
            'new_7d': new_users_7d,
            'new_30d': new_users_30d,
            'by_day': [dict(r) for r in users_by_day],
        },
        'llm': {
            'total_requests': llm_total,
            'by_source': [dict(r) for r in llm_by_source],
            'by_day': [dict(r) for r in llm_by_day],
        },
        'generation': {
            'completed_jobs': gen_completed,
            'running_jobs': gen_running,
            'total_generated': gen_total_recipes,
        },
        'system': {
            'db_size_mb': db_size_mb,
        }
    })


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
