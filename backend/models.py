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


def _time_appropriate_meals(hour):
    """Map hour of day to appropriate meal types."""
    if hour is None:
        return []
    if 5 <= hour < 11:
        return ['breakfast', 'pre_workout']
    elif 11 <= hour < 14:
        return ['lunch', 'post_workout']
    elif 14 <= hour < 17:
        return ['snack', 'pre_workout']
    elif 17 <= hour < 21:
        return ['dinner', 'post_workout']
    else:
        return ['snack']


def _adaptive_meal_fraction(meals_eaten_today):
    """Return fraction of remaining macros to target for this meal."""
    if meals_eaten_today is None:
        return 0.4
    meals_left = max(1, 4 - meals_eaten_today)
    return max(0.25, min(0.8, 1.0 / meals_left))


def _current_season():
    """Return current season based on month."""
    from datetime import date
    month = date.today().month
    if month in (3, 4, 5):
        return 'spring'
    elif month in (6, 7, 8):
        return 'summer'
    elif month in (9, 10, 11):
        return 'autumn'
    else:
        return 'winter'


# Health condition → beneficial tag mappings
HEALTH_CONDITION_BOOSTS = {
    'diabetes_t2': {'health': ['blood_sugar_friendly'], 'satiety': ['blood_sugar_stable'], 'macro_profile': ['low_sugar', 'very_low_sugar', 'good_fiber', 'high_fiber']},
    'diabetes_t1': {'health': ['blood_sugar_friendly'], 'satiety': ['blood_sugar_stable']},
    'prediabetes': {'health': ['blood_sugar_friendly'], 'macro_profile': ['good_fiber', 'high_fiber', 'low_sugar']},
    'insulin_resistance': {'health': ['blood_sugar_friendly'], 'satiety': ['blood_sugar_stable'], 'macro_profile': ['low_sugar', 'good_fiber', 'high_fiber']},
    'high_cholesterol': {'health': ['heart_healthy', 'low_cholesterol'], 'micronutrients': ['omega_3_rich'], 'macro_profile': ['low_fat']},
    'high_triglycerides': {'macro_profile': ['low_carb', 'very_low_sugar', 'low_sugar'], 'micronutrients': ['omega_3_rich']},
    'high_blood_pressure': {'health': ['heart_healthy'], 'micronutrients': ['potassium_rich', 'magnesium_rich']},
    'heart_disease': {'health': ['heart_healthy', 'anti_inflammatory'], 'micronutrients': ['omega_3_rich'], 'macro_profile': ['good_fiber', 'high_fiber']},
    'pcos': {'health': ['blood_sugar_friendly', 'anti_inflammatory'], 'macro_profile': ['low_carb']},
    'hypothyroid': {'health': ['anti_inflammatory'], 'micronutrients': ['zinc_rich', 'iron_rich']},
    'hyperthyroid': {'micronutrients': ['calcium_rich']},
    'hashimoto': {'health': ['anti_inflammatory'], 'micronutrients': ['zinc_rich', 'iron_rich']},
    'ibs': {'health': ['gut_friendly'], 'texture_experience': ['mild']},
    'ibd_crohn': {'health': ['gut_friendly'], 'texture_experience': ['mild']},
    'ibd_colitis': {'health': ['gut_friendly'], 'texture_experience': ['mild']},
    'celiac': {'dietary': ['gluten_free']},
    'kidney_disease': {'macro_profile': ['moderate_protein']},
    'gout': {'protein_source': ['plant_protein', 'dairy_protein', 'egg_protein']},
    'anemia': {'micronutrients': ['iron_rich', 'vitamin_c_rich']},
    'b12_deficiency': {'micronutrients': ['b_vitamin_rich'], 'protein_source': ['animal_protein']},
    'osteoporosis': {'micronutrients': ['calcium_rich', 'magnesium_rich'], 'health': ['bone_health']},
    'lactose_intolerant': {'dietary': ['dairy_free']},
    'fatty_liver': {'macro_profile': ['low_fat', 'low_sugar', 'good_fiber'], 'health': ['low_cholesterol']},
    'acid_reflux': {'texture_experience': ['mild']},
    'gallbladder': {'macro_profile': ['very_low_fat', 'low_fat']},
    'arthritis': {'health': ['anti_inflammatory'], 'micronutrients': ['omega_3_rich']},
    'fibromyalgia': {'health': ['anti_inflammatory'], 'micronutrients': ['magnesium_rich']},
    'endometriosis': {'health': ['anti_inflammatory'], 'micronutrients': ['omega_3_rich']},
    'autoimmune': {'health': ['anti_inflammatory'], 'micronutrients': ['omega_3_rich']},
    'anxiety_depression': {'health': ['brain_food'], 'micronutrients': ['magnesium_rich', 'b_vitamin_rich', 'omega_3_rich']},
    'migraine': {'micronutrients': ['magnesium_rich'], 'macro_profile': ['very_low_sugar']},
    'sleep_apnea': {'coaching': ['sleep_friendly'], 'macro_profile': ['low_sugar']},
    'food_allergies': {},
    'nut_allergy': {},
    'shellfish_allergy': {},
    'egg_allergy': {},
    'soy_allergy': {},
}

# Health condition → harmful tag penalties
HEALTH_CONDITION_PENALTIES = {
    'diabetes_t2': {'macro_profile': ['high_sugar']},
    'insulin_resistance': {'macro_profile': ['high_sugar', 'high_carb_low_fat']},
    'high_cholesterol': {'macro_profile': ['high_fat_low_carb']},
    'ibs': {'texture_experience': ['spicy']},
    'ibd_crohn': {'texture_experience': ['spicy']},
    'acid_reflux': {'texture_experience': ['spicy', 'tangy']},
    'kidney_disease': {'macro_profile': ['very_high_protein', 'ultra_high_protein', 'high_protein']},
    'gout': {'protein_source': ['red_meat_protein', 'shellfish_protein']},
    'migraine': {'texture_experience': ['spicy']},
}


def suggest_recipes(context, limit=5):
    """Score and rank recipes from DB based on user context.

    Scoring dimensions (max ~180+ points):
      - Meal type match: +30
      - Time-of-day: +15
      - Goal alignment: +25
      - Health condition fit: +20 / -40
      - Macro fit (adaptive): +20
      - Coaching context: +12
      - Seasonal + lifestyle: +10
      - Cuisine diversity: -15
      - Protein source rotation: -12
      - Preference match: +10 / -100
      - Pantry match: +12
      - Micronutrient bonus: +8
      - Cooking time: +5
      - Recent meal penalty: -30
      - Workout awareness: +10
      - Random variety: +0-5
    """
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

    import random

    # Extract all context signals
    meal_types = context.get('meal_types', [])
    goal = context.get('goal', '')
    liked = [f.lower().strip() for f in context.get('liked', [])]
    disliked = [f.lower().strip() for f in context.get('disliked', [])]
    hour_of_day = context.get('hour_of_day')
    day_of_week = context.get('day_of_week')  # 0=Sun, 6=Sat
    recent_meal_names = [n.lower() for n in context.get('recent_meal_names', [])]
    recent_cuisines = [c.lower() for c in context.get('recent_cuisines', [])]
    recent_protein_sources = [p.lower() for p in context.get('recent_protein_sources', [])]
    meals_eaten_today = context.get('meals_eaten_today', 0)
    health_conditions = context.get('health_conditions', [])
    pantry = [p.lower().strip() for p in context.get('pantry', [])]
    workout_cals = context.get('workout_calories_today', 0)
    has_recent_workout = context.get('has_recent_workout', False)
    weight_trend = context.get('weight_trend', 'stable')

    meal_fraction = _adaptive_meal_fraction(meals_eaten_today)
    time_meals = _time_appropriate_meals(hour_of_day)
    season = _current_season()
    is_weekend = day_of_week in (0, 6) if day_of_week is not None else False

    # Count cuisine frequency for diversity penalty
    cuisine_counts = {}
    for c in recent_cuisines:
        cuisine_counts[c] = cuisine_counts.get(c, 0) + 1

    # Count protein source frequency for rotation
    protein_counts = {}
    for p in recent_protein_sources:
        protein_counts[p] = protein_counts.get(p, 0) + 1

    # Pre-compute health boost/penalty tag sets
    health_boost_tags = {}  # {(dimension, tag): count}
    health_penalty_tags = {}
    for cond in health_conditions:
        for dim, tags in HEALTH_CONDITION_BOOSTS.get(cond, {}).items():
            for tag in tags:
                health_boost_tags[(dim, tag)] = health_boost_tags.get((dim, tag), 0) + 1
        for dim, tags in HEALTH_CONDITION_PENALTIES.get(cond, {}).items():
            for tag in tags:
                health_penalty_tags[(dim, tag)] = health_penalty_tags.get((dim, tag), 0) + 1

    scored = []
    for row in rows:
        recipe = recipe_to_dict(row)
        rtags = tags_by_recipe.get(recipe['id'], {})
        score = 0.0

        # ── Meal type match (+30) ──
        if meal_types:
            if recipe.get('meal_type') in meal_types:
                score += 30
            elif recipe.get('meal_type') == 'any':
                score += 10

        # ── Time-of-day (+15) ──
        if time_meals and recipe.get('meal_type') in time_meals:
            score += 15
        elif time_meals and recipe.get('meal_type') == 'any':
            score += 5

        # ── Goal alignment (+25) ──
        if goal and goal in rtags.get('goal', []):
            score += 25
        elif goal:
            goal_map = {
                'fat_loss': ['cutting', 'maintenance', 'aggressive_fat_loss'],
                'aggressive_fat_loss': ['cutting', 'fat_loss'],
                'muscle_gain': ['bulking', 'lean_bulk', 'muscle_building'],
                'lean_bulk': ['bulking', 'muscle_building', 'maintenance'],
                'maintain': ['maintenance', 'recomp'],
                'recomp': ['maintenance', 'cutting', 'fat_loss'],
            }
            related = goal_map.get(goal, [])
            if any(g in rtags.get('goal', []) for g in related):
                score += 12

        # ── Health condition fit (+20 / -40) ──
        if health_boost_tags:
            health_bonus = 0
            for dim, dim_tags in rtags.items():
                for tag in dim_tags:
                    health_bonus += health_boost_tags.get((dim, tag), 0) * 4
            score += min(health_bonus, 20)
        if health_penalty_tags:
            health_penalty = 0
            for dim, dim_tags in rtags.items():
                for tag in dim_tags:
                    health_penalty += health_penalty_tags.get((dim, tag), 0) * 8
            score -= min(health_penalty, 40)

        # ── Macro fit (+20) — adaptive fraction ──
        if remaining:
            rem_cal = remaining.get('calories', 500)
            rem_prot = remaining.get('protein', 30)
            # Add workout calories back to budget
            effective_cal = rem_cal + (workout_cals * 0.5 if workout_cals else 0)
            if effective_cal > 0:
                target_cal = effective_cal * meal_fraction
                cal_fit = max(0, 1 - abs(recipe['calories'] - target_cal) / max(effective_cal, 1))
                score += cal_fit * 8
            if rem_prot > 0:
                target_prot = rem_prot * meal_fraction
                prot_fit = max(0, 1 - abs(recipe['protein'] - target_prot) / max(rem_prot, 1))
                score += prot_fit * 8
            if recipe['calories'] <= rem_cal and recipe['protein'] <= rem_prot:
                score += 4

        # ── Coaching context (+12) ──
        coaching_tags = rtags.get('coaching', [])
        if hour_of_day is not None:
            if 5 <= hour_of_day < 10 and 'morning_energy' in coaching_tags:
                score += 8
            elif 13 <= hour_of_day < 16 and 'afternoon_slump_buster' in coaching_tags:
                score += 8
            elif hour_of_day >= 20 and 'sleep_friendly' in coaching_tags:
                score += 8
            elif hour_of_day >= 20 and 'evening_wind_down' in coaching_tags:
                score += 6
        if weight_trend == 'plateau' and 'plateau_breaker' in coaching_tags:
            score += 12
        if weight_trend == 'plateau' and 'metabolic_boost' in coaching_tags:
            score += 8

        # ── Seasonal + lifestyle (+10) ──
        seasonal_tags = rtags.get('seasonal', [])
        if season in seasonal_tags:
            score += 6
        if season == 'winter' and 'soup_season' in seasonal_tags:
            score += 4
        if season == 'summer' and 'bbq_season' in seasonal_tags:
            score += 4

        lifestyle_tags = rtags.get('lifestyle', [])
        if is_weekend:
            if 'weekend_project' in lifestyle_tags or 'date_night' in lifestyle_tags:
                score += 5
        else:
            if 'weeknight_quick' in lifestyle_tags or 'office_lunch' in lifestyle_tags:
                score += 5
            if 'desk_meal' in lifestyle_tags and 11 <= (hour_of_day or 12) <= 14:
                score += 4

        # ── Cuisine diversity (-15) ──
        recipe_cuisine = (recipe.get('cuisine') or '').lower()
        if recipe_cuisine and recipe_cuisine in cuisine_counts:
            freq = cuisine_counts[recipe_cuisine]
            score -= min(freq * 5, 15)

        # ── Protein source rotation (-12) ──
        recipe_psources = rtags.get('protein_source', [])
        if recipe_psources and protein_counts:
            for ps in recipe_psources:
                ps_lower = ps.lower()
                if ps_lower in protein_counts:
                    score -= min(protein_counts[ps_lower] * 4, 12)
                    break

        # ── Recent meal penalty (-30) ──
        name_lower = recipe['name'].lower()
        name_words = set(name_lower.split())
        if recent_meal_names:
            for recent in recent_meal_names:
                recent_words = recent.split()
                if name_lower == recent:
                    score -= 30
                    break
                overlap = sum(1 for w in recent_words if len(w) > 3 and w in name_words)
                if overlap >= 2:
                    score -= 20
                    break
                elif overlap == 1 and len(recent_words) <= 3:
                    score -= 10
                    break

        # ── Preference match (+10 / -100) ──
        ing_names = ' '.join(i.lower() if isinstance(i, str) else i.get('item', '').lower()
                            for i in recipe.get('ingredients', []))

        for liked_food in liked:
            liked_words = liked_food.split()
            if any(w in name_words for w in liked_words) or liked_food in ing_names:
                score += 10
                break

        for disliked_food in disliked:
            disliked_words = disliked_food.split()
            if any(w in name_words for w in disliked_words) or disliked_food in ing_names:
                score -= 100
                break

        # ── Pantry match (+12) ──
        if pantry:
            pantry_hits = sum(1 for p in pantry if p in ing_names)
            score += min(pantry_hits * 3, 12)

        # ── Micronutrient bonus (+8) ──
        # Boost fiber-rich if user is low on fiber
        remaining_fiber = remaining.get('fiber', 0)
        if remaining_fiber > 10:
            fiber_tags = rtags.get('macro_profile', [])
            if 'high_fiber' in fiber_tags or 'very_high_fiber' in fiber_tags:
                score += 5
            elif 'good_fiber' in fiber_tags:
                score += 3
        # Penalize high-sugar if user already had too much processed sugar
        processed_sugar = remaining.get('sugar_processed', 0)
        if processed_sugar > 30:
            if 'high_sugar' in rtags.get('macro_profile', []):
                score -= 8

        # Boost satiety for fat loss goals
        if goal in ('fat_loss', 'aggressive_fat_loss'):
            sat_tags = rtags.get('satiety', [])
            if 'high_satiety' in sat_tags or 'very_filling' in sat_tags:
                score += 5
            if 'slow_digesting' in sat_tags:
                score += 3

        # ── Workout awareness (+10) ──
        if has_recent_workout:
            if 'recovery_focused' in rtags.get('health', []):
                score += 8
            if 'post_workout' == recipe.get('meal_type'):
                score += 6
            if 'high_protein' in rtags.get('macro_profile', []) or 'very_high_protein' in rtags.get('macro_profile', []):
                score += 4
            if 'electrolyte_rich' in rtags.get('health', []):
                score += 4

        # ── Cooking time (+5) ──
        cook_time = recipe.get('total_time_min', 60)
        if cook_time <= 15:
            score += 5
        elif cook_time <= 30:
            score += 3
        # On weekdays, penalize long cook times
        if not is_weekend and cook_time > 45:
            score -= 5

        # ── Random variety (+0-5) ──
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
    remaining = context.get('remaining', {})
    hour = context.get('hour_of_day')
    meals_eaten = context.get('meals_eaten_today', 0)
    health_conditions = context.get('health_conditions', [])
    has_recent_workout = context.get('has_recent_workout', False)
    weight_trend = context.get('weight_trend', 'stable')
    pantry = context.get('pantry', [])
    rtags = recipe.get('tags', {})

    # Lead reason for #1
    if rank == 0:
        rem_cal = remaining.get('calories', 0)
        rem_prot = remaining.get('protein', 0)
        if rem_cal and rem_prot:
            reasons.append(f"Best fit for your remaining {rem_cal}cal / {rem_prot}g protein")
        else:
            reasons.append("Best overall match for your goals")

    # Time-of-day
    if hour is not None:
        time_labels = _time_appropriate_meals(hour)
        if recipe.get('meal_type') in time_labels:
            if 5 <= hour < 11:
                reasons.append("perfect for this morning")
            elif 17 <= hour < 21:
                reasons.append("great for tonight")
            elif 13 <= hour < 16:
                reasons.append("ideal afternoon pick")

    # Post-workout context
    if has_recent_workout:
        if 'recovery_focused' in rtags.get('health', []):
            reasons.append("great for post-workout recovery")
        elif 'high_protein' in rtags.get('macro_profile', []) or 'very_high_protein' in rtags.get('macro_profile', []):
            reasons.append("high protein for your workout recovery")

    # Health condition relevance
    if health_conditions and len(reasons) < 4:
        condition_labels = {
            'diabetes_t2': 'blood sugar friendly', 'prediabetes': 'blood sugar friendly',
            'insulin_resistance': 'blood sugar friendly',
            'high_cholesterol': 'heart healthy', 'heart_disease': 'heart healthy',
            'high_blood_pressure': 'heart healthy',
            'ibs': 'gut friendly', 'ibd_crohn': 'gut friendly', 'ibd_colitis': 'gut friendly',
            'anemia': 'iron rich', 'osteoporosis': 'calcium rich',
            'anxiety_depression': 'brain-boosting nutrients',
            'arthritis': 'anti-inflammatory', 'autoimmune': 'anti-inflammatory',
        }
        for cond in health_conditions:
            label = condition_labels.get(cond)
            if label:
                # Check if recipe actually has the relevant tags
                boosts = HEALTH_CONDITION_BOOSTS.get(cond, {})
                for dim, tags in boosts.items():
                    if any(t in rtags.get(dim, []) for t in tags):
                        reasons.append(label)
                        break
                else:
                    continue
                break

    # Plateau coaching
    if weight_trend == 'plateau' and any(t in rtags.get('coaching', []) for t in ('plateau_breaker', 'metabolic_boost')):
        reasons.append("may help break your plateau")

    # Adaptive fraction context
    if meals_eaten >= 3 and remaining.get('calories', 0) > 0:
        reasons.append("helps use your remaining budget")

    # Macros
    if recipe['protein'] >= 35:
        reasons.append(f"packed with {recipe['protein']}g protein")
    elif recipe['protein'] >= 25:
        reasons.append(f"{recipe['protein']}g protein")

    if remaining.get('calories') and recipe['calories'] <= remaining['calories'] * 0.5:
        reasons.append("fits your calorie budget")
    elif remaining.get('calories') and recipe['calories'] <= remaining['calories']:
        reasons.append("within remaining calories")

    # Satiety for fat loss
    goal = context.get('goal', '')
    if goal in ('fat_loss', 'aggressive_fat_loss'):
        sat = rtags.get('satiety', [])
        if 'high_satiety' in sat or 'very_filling' in sat:
            reasons.append("keeps you full longer")

    # Pantry match
    if pantry:
        ing_text = ' '.join(i.lower() if isinstance(i, str) else i.get('item', '').lower()
                            for i in recipe.get('ingredients', []))
        hits = [p for p in pantry if p.lower() in ing_text]
        if len(hits) >= 2:
            reasons.append(f"uses {', '.join(hits[:3])} from your pantry")
        elif len(hits) == 1:
            reasons.append(f"uses {hits[0]} you have")

    # Cooking time
    if recipe.get('total_time_min', 0) <= 15:
        reasons.append(f"ready in just {recipe['total_time_min']} min")
    elif recipe.get('total_time_min', 0) <= 25:
        reasons.append(f"ready in {recipe['total_time_min']} min")
    elif recipe.get('total_time_min', 0) <= 30:
        reasons.append("quick to prepare")

    # Seasonal
    season = _current_season()
    if season in rtags.get('seasonal', []):
        season_label = {'spring': 'spring', 'summer': 'summer', 'autumn': 'fall', 'winter': 'winter'}
        reasons.append(f"perfect for {season_label.get(season, season)}")

    # Cuisine
    if recipe.get('cuisine') and recipe['cuisine'] != 'International':
        reasons.append(f"{recipe['cuisine']} cuisine")

    return '. '.join(reasons[:4]) if reasons else "Good match for your goals"


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
