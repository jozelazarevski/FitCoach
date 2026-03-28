import json
import hashlib
import secrets
import threading
from flask import Blueprint, request, jsonify
from backend.db import get_db, init_db
from backend.models import (
    get_recipe, search_recipes, insert_recipe, insert_tags,
    update_recipe, delete_recipe, get_tag_stats, get_overview_stats
)
from backend.tag_engine import detect_cuisine, compute_tags
from backend.recipe_generator import (
    build_generation_plan, create_batch, run_generation, get_generation_status
)

admin_bp = Blueprint('admin', __name__)

# Simple token-based auth
def _check_admin(req):
    token = req.headers.get('X-Admin-Token') or req.args.get('token')
    if not token:
        return False
    db = get_db()
    row = db.execute("SELECT token FROM admin_sessions WHERE token = ?", (token,)).fetchone()
    db.close()
    return row is not None


@admin_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    password = data.get('password', '')
    # Simple password check - hash of 'fitcoach-admin'
    expected = hashlib.sha256(b'fitcoach-admin').hexdigest()
    provided = hashlib.sha256(password.encode()).hexdigest()
    if provided != expected:
        return jsonify({'error': 'Invalid password'}), 401

    token = secrets.token_hex(32)
    db = get_db()
    db.execute("INSERT INTO admin_sessions (token) VALUES (?)", (token,))
    db.commit()
    db.close()
    return jsonify({'token': token})


@admin_bp.route('/stats', methods=['GET'])
def stats():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(get_overview_stats())


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

    # Include archived for admin
    db = get_db()
    conditions = ["1=1"]
    params = []
    status_filter = request.args.get('status', 'active')
    if status_filter != 'all':
        conditions.append("status = ?")
        params.append(status_filter)
    for k, v in filters.items():
        if k == 'search':
            conditions.append("name LIKE ?")
            params.append(f"%{v}%")
        else:
            conditions.append(f"{k} = ?")
            params.append(v)

    where = " AND ".join(conditions)
    count = db.execute(f"SELECT COUNT(*) FROM recipes WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT id, name, category, cuisine, meal_type, calories, protein, carbs, fat, status, created_at FROM recipes WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    db.close()

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

    recipe_id = insert_recipe(data)
    tags = compute_tags(data)
    insert_tags(recipe_id, tags)

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
        db = get_db()
        db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
        db.commit()
        db.close()
        tags = compute_tags(updated)
        insert_tags(recipe_id, tags)

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

    db = get_db()
    recipes = db.execute("SELECT id FROM recipes WHERE status = 'active'").fetchall()
    db.close()

    count = 0
    for row in recipes:
        recipe = get_recipe(row['id'])
        if recipe:
            db = get_db()
            db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (row['id'],))
            db.commit()
            db.close()
            tags = compute_tags(recipe)
            insert_tags(row['id'], tags)
            count += 1

    return jsonify({'message': f'Re-tagged {count} recipes'})


@admin_bp.route('/api-keys', methods=['GET'])
def list_api_keys():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    rows = db.execute(
        "SELECT id, provider, key_name, SUBSTR(api_key, 1, 8) || '...' as key_preview, model, is_active, usage_count, last_used_at, created_at FROM api_keys ORDER BY provider, key_name"
    ).fetchall()
    db.close()
    return jsonify({'keys': [dict(r) for r in rows]})


@admin_bp.route('/api-keys', methods=['POST'])
def add_api_key():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data or not data.get('provider') or not data.get('api_key'):
        return jsonify({'error': 'Provider and api_key required'}), 400

    db = get_db()
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
        db.close()
        return jsonify({'error': f'Key already exists for this provider/name: {e}'}), 409
    db.close()
    return jsonify({'message': 'API key added'}), 201


@admin_bp.route('/api-keys/<int:key_id>', methods=['PUT'])
def update_api_key(key_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    db = get_db()
    sets = []
    params = []
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
    db.close()
    return jsonify({'message': 'API key updated'})


@admin_bp.route('/api-keys/<int:key_id>', methods=['DELETE'])
def delete_api_key(key_id):
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    db.commit()
    db.close()
    return jsonify({'message': 'API key deleted'})


def get_active_api_key(provider='anthropic'):
    """Get the active API key for a provider from the database."""
    db = get_db()
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
    db.close()
    return dict(row) if row else None


@admin_bp.route('/generate/start', methods=['POST'])
def start_generation():
    if not _check_admin(request):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    batch_size = data.get('batch_size', 10)
    max_items = data.get('max_items', None)

    plan = build_generation_plan(batch_size)
    if max_items:
        plan = plan[:max_items]
    batch_id = create_batch(plan, batch_id=None)

    # Run in background thread
    thread = threading.Thread(
        target=run_generation,
        args=(batch_id, batch_size, max_items),
        daemon=True
    )
    thread.start()

    return jsonify({
        'batch_id': batch_id,
        'total_prompts': len(plan),
        'expected_recipes': sum(p['count'] for p in plan),
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
