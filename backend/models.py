import json
from backend.db import get_db


def recipe_to_dict(row):
    d = dict(row)
    for field in ('ingredients', 'steps', 'equipment', 'allergens', 'diet'):
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    return d


def get_recipe(recipe_id):
    db = get_db()
    row = db.execute("SELECT * FROM recipes WHERE id = ? AND status = 'active'", (recipe_id,)).fetchone()
    if not row:
        return None
    recipe = recipe_to_dict(row)
    tags = db.execute("SELECT dimension, tag FROM recipe_tags WHERE recipe_id = ?", (recipe_id,)).fetchall()
    recipe['tags'] = {}
    for t in tags:
        recipe['tags'].setdefault(t['dimension'], []).append(t['tag'])
    db.close()
    return recipe


def search_recipes(filters=None, page=1, per_page=20):
    db = get_db()
    conditions = ["r.status = 'active'"]
    params = []

    if filters:
        if filters.get('meal_type'):
            conditions.append("r.meal_type = ?")
            params.append(filters['meal_type'])
        if filters.get('cuisine'):
            conditions.append("r.cuisine = ?")
            params.append(filters['cuisine'])
        if filters.get('category'):
            conditions.append("r.category = ?")
            params.append(filters['category'])
        if filters.get('max_calories'):
            conditions.append("r.calories <= ?")
            params.append(int(filters['max_calories']))
        if filters.get('min_protein'):
            conditions.append("r.protein >= ?")
            params.append(int(filters['min_protein']))
        if filters.get('max_carbs'):
            conditions.append("r.carbs <= ?")
            params.append(int(filters['max_carbs']))
        if filters.get('max_fat'):
            conditions.append("r.fat <= ?")
            params.append(int(filters['max_fat']))
        if filters.get('max_time'):
            conditions.append("r.total_time_min <= ?")
            params.append(int(filters['max_time']))
        if filters.get('search'):
            conditions.append("r.name LIKE ?")
            params.append(f"%{filters['search']}%")
        if filters.get('diet'):
            diets = filters['diet'].split(',') if isinstance(filters['diet'], str) else filters['diet']
            for diet in diets:
                conditions.append("""r.id IN (
                    SELECT recipe_id FROM recipe_tags WHERE dimension = 'dietary' AND tag = ?
                )""")
                params.append(diet.strip())
        if filters.get('goal'):
            conditions.append("""r.id IN (
                SELECT recipe_id FROM recipe_tags WHERE dimension = 'goal' AND tag = ?
            )""")
            params.append(filters['goal'])

    where = " AND ".join(conditions)
    count = db.execute(f"SELECT COUNT(*) FROM recipes r WHERE {where}", params).fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM recipes r WHERE {where} ORDER BY r.id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    recipes = [recipe_to_dict(r) for r in rows]
    db.close()
    return {'recipes': recipes, 'total': count, 'page': page, 'per_page': per_page,
            'pages': (count + per_page - 1) // per_page}


def suggest_recipes(context, limit=5):
    """Score and rank recipes from DB based on user context."""
    db = get_db()

    conditions = ["r.status = 'active'"]
    params = []

    # Pre-filter by diet compliance
    diet_filters = context.get('diet_filters', [])
    for diet in diet_filters:
        tag_map = {
            'vegan': 'vegan', 'vegetarian': 'vegetarian', 'keto': 'keto_friendly',
            'low_carb': 'low_carb', 'high_protein': 'high_protein',
            'paleo': 'paleo', 'gluten_free': 'gluten_free', 'dairy_free': 'dairy_free',
            'mediterranean': 'mediterranean_diet', 'whole30': 'whole30_compliant'
        }
        mapped = tag_map.get(diet, diet)
        conditions.append("""r.id IN (
            SELECT recipe_id FROM recipe_tags WHERE dimension = 'dietary' AND tag = ?
        )""")
        params.append(mapped)

    # Pre-filter by calorie range if remaining is known
    remaining = context.get('remaining', {})
    if remaining.get('calories'):
        max_cal = int(remaining['calories'] * 1.2)
        conditions.append("r.calories <= ?")
        params.append(max_cal)

    where = " AND ".join(conditions)
    rows = db.execute(
        f"SELECT * FROM recipes r WHERE {where} LIMIT 200", params
    ).fetchall()

    # Load tags for scoring
    recipe_ids = [r['id'] for r in rows]
    if not recipe_ids:
        db.close()
        return []

    placeholders = ','.join('?' * len(recipe_ids))
    all_tags = db.execute(
        f"SELECT recipe_id, dimension, tag FROM recipe_tags WHERE recipe_id IN ({placeholders})",
        recipe_ids
    ).fetchall()
    db.close()

    tags_by_recipe = {}
    for t in all_tags:
        tags_by_recipe.setdefault(t['recipe_id'], {}).setdefault(t['dimension'], []).append(t['tag'])

    # Score each recipe
    scored = []
    meal_types = context.get('meal_types', [])
    goal = context.get('goal', '')
    liked = [f.lower() for f in context.get('liked', [])]
    disliked = [f.lower() for f in context.get('disliked', [])]

    for row in rows:
        recipe = recipe_to_dict(row)
        rtags = tags_by_recipe.get(recipe['id'], {})
        score = 0.0

        # Meal type match
        if meal_types:
            if recipe.get('meal_type') in meal_types:
                score += 30

        # Goal alignment
        if goal and goal in rtags.get('goal', []):
            score += 25

        # Macro fit
        if remaining:
            rem_cal = remaining.get('calories', 500)
            rem_prot = remaining.get('protein', 30)
            if rem_cal > 0:
                cal_fit = max(0, 1 - abs(recipe['calories'] - rem_cal * 0.4) / rem_cal)
                score += cal_fit * 15
            if rem_prot > 0:
                prot_fit = max(0, 1 - abs(recipe['protein'] - rem_prot * 0.4) / rem_prot)
                score += prot_fit * 15

        # Preference match
        name_lower = recipe['name'].lower()
        if any(l in name_lower for l in liked):
            score += 10
        if any(d in name_lower for d in disliked):
            score -= 50

        # Variety bonus (randomize a bit)
        import random
        score += random.uniform(0, 5)

        recipe['tags'] = rtags
        scored.append((score, recipe))

    scored.sort(key=lambda x: -x[0])
    results = []
    for i, (score, recipe) in enumerate(scored[:limit]):
        results.append({
            'rank': i + 1,
            'id': recipe['id'],
            'name': recipe['name'],
            'description': recipe.get('description', ''),
            'why': _generate_why(recipe, context, i),
            'calories': recipe['calories'],
            'protein': recipe['protein'],
            'carbs': recipe['carbs'],
            'fat': recipe['fat'],
            'has_recipe': True
        })
    return results


def _generate_why(recipe, context, rank):
    reasons = []
    if rank == 0:
        reasons.append("Best macro fit for your remaining targets")
    remaining = context.get('remaining', {})
    if recipe['protein'] >= 30:
        reasons.append(f"{recipe['protein']}g protein")
    if remaining.get('calories') and recipe['calories'] <= remaining['calories'] * 0.5:
        reasons.append("fits your calorie budget")
    if recipe.get('total_time_min', 0) <= 30:
        reasons.append("quick to prepare")
    return '. '.join(reasons) if reasons else "Good match for your goals"


def insert_recipe(recipe_data):
    db = get_db()
    cur = db.execute("""
        INSERT INTO recipes (name, description, category, cuisine, country_of_origin, region,
            meal_type, difficulty, prep_time_min, cook_time_min, total_time_min, servings,
            calories, protein, carbs, fat, fiber, sugar,
            ingredients, steps, tips, equipment, allergens, diet,
            meal_prep_friendly, source, generation_batch)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        recipe_data['name'],
        recipe_data.get('description', ''),
        recipe_data.get('category', 'general'),
        recipe_data.get('cuisine', 'International'),
        recipe_data.get('country_of_origin', 'International'),
        recipe_data.get('region', 'International'),
        recipe_data.get('meal_type', 'any'),
        recipe_data.get('difficulty', 'medium'),
        recipe_data.get('prep_time_min', 0),
        recipe_data.get('cook_time_min', 0),
        recipe_data.get('total_time_min', 0),
        recipe_data.get('servings', 1),
        recipe_data['calories'],
        recipe_data['protein'],
        recipe_data['carbs'],
        recipe_data['fat'],
        recipe_data.get('fiber', 0),
        recipe_data.get('sugar', 0),
        json.dumps(recipe_data.get('ingredients', [])),
        json.dumps(recipe_data.get('steps', [])),
        recipe_data.get('tips', ''),
        json.dumps(recipe_data.get('equipment', [])),
        json.dumps(recipe_data.get('allergens', [])),
        json.dumps(recipe_data.get('diet', [])),
        1 if recipe_data.get('meal_prep_friendly') else 0,
        recipe_data.get('source', 'generated'),
        recipe_data.get('generation_batch', None)
    ))
    recipe_id = cur.lastrowid
    db.commit()
    db.close()
    return recipe_id


def insert_tags(recipe_id, tags_dict):
    db = get_db()
    for dimension, values in tags_dict.items():
        if isinstance(values, list):
            for v in values:
                db.execute(
                    "INSERT OR IGNORE INTO recipe_tags (recipe_id, dimension, tag) VALUES (?, ?, ?)",
                    (recipe_id, dimension, str(v))
                )
        elif isinstance(values, (str, int, float)):
            db.execute(
                "INSERT OR IGNORE INTO recipe_tags (recipe_id, dimension, tag) VALUES (?, ?, ?)",
                (recipe_id, dimension, str(values))
            )
    db.commit()
    db.close()


def update_recipe(recipe_id, updates):
    db = get_db()
    sets = []
    params = []
    for key, val in updates.items():
        if key in ('ingredients', 'steps', 'equipment', 'allergens', 'diet'):
            val = json.dumps(val) if isinstance(val, list) else val
        sets.append(f"{key} = ?")
        params.append(val)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(recipe_id)
    db.execute(f"UPDATE recipes SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    db.close()


def delete_recipe(recipe_id):
    db = get_db()
    db.execute("UPDATE recipes SET status = 'archived' WHERE id = ?", (recipe_id,))
    db.commit()
    db.close()


def get_tag_stats():
    db = get_db()
    rows = db.execute("""
        SELECT dimension, tag, COUNT(*) as cnt
        FROM recipe_tags rt
        JOIN recipes r ON rt.recipe_id = r.id
        WHERE r.status = 'active'
        GROUP BY dimension, tag
        ORDER BY dimension, cnt DESC
    """).fetchall()
    db.close()
    stats = {}
    for r in rows:
        stats.setdefault(r['dimension'], {})[r['tag']] = r['cnt']
    return stats


def get_overview_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]
    by_cuisine = db.execute(
        "SELECT cuisine, COUNT(*) as cnt FROM recipes WHERE status = 'active' GROUP BY cuisine ORDER BY cnt DESC"
    ).fetchall()
    by_meal = db.execute(
        "SELECT meal_type, COUNT(*) as cnt FROM recipes WHERE status = 'active' GROUP BY meal_type ORDER BY cnt DESC"
    ).fetchall()
    by_category = db.execute(
        "SELECT category, COUNT(*) as cnt FROM recipes WHERE status = 'active' GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    avg_macros = db.execute(
        "SELECT AVG(calories) as cal, AVG(protein) as prot, AVG(carbs) as carb, AVG(fat) as fat FROM recipes WHERE status = 'active'"
    ).fetchone()
    db.close()
    return {
        'total_recipes': total,
        'by_cuisine': {r['cuisine']: r['cnt'] for r in by_cuisine},
        'by_meal_type': {r['meal_type']: r['cnt'] for r in by_meal},
        'by_category': {r['category']: r['cnt'] for r in by_category},
        'avg_macros': {
            'calories': round(avg_macros['cal'] or 0),
            'protein': round(avg_macros['prot'] or 0),
            'carbs': round(avg_macros['carb'] or 0),
            'fat': round(avg_macros['fat'] or 0)
        }
    }
