import json
import random
import time
from datetime import date

from backend.db import use_db

# Track recently suggested recipe IDs to avoid repetition across requests
# Format: {recipe_id: timestamp}
_recently_suggested = {}
_RECENT_SUGGEST_TTL = 3600  # 1 hour


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
    with use_db() as db:
        # Single query: recipe + all tags via GROUP_CONCAT
        row = db.execute("""
            SELECT r.*,
                   GROUP_CONCAT(rt.dimension || ':' || rt.tag, '||') as _tag_str
            FROM recipes r
            LEFT JOIN recipe_tags rt ON rt.recipe_id = r.id
            WHERE r.id = ? AND r.status = 'active'
            GROUP BY r.id
        """, (recipe_id,)).fetchone()
        if not row:
            return None
        recipe = recipe_to_dict(row)
        # Parse concatenated tags
        recipe['tags'] = {}
        tag_str = recipe.pop('_tag_str', None)
        if tag_str:
            for pair in tag_str.split('||'):
                dim, _, tag = pair.partition(':')
                if dim and tag:
                    recipe['tags'].setdefault(dim, []).append(tag)
        return recipe


def search_recipes(filters=None, page=1, per_page=20):
    with use_db() as db:
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
            for filter_key, column, op in [
                ('max_calories', 'r.calories', '<='),
                ('min_protein', 'r.protein', '>='),
                ('max_carbs', 'r.carbs', '<='),
                ('max_fat', 'r.fat', '<='),
                ('max_time', 'r.total_time_min', '<='),
            ]:
                val = filters.get(filter_key)
                if val is not None:
                    try:
                        conditions.append(f"{column} {op} ?")
                        params.append(int(val))
                    except (ValueError, TypeError):
                        pass  # skip malformed numeric filter
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
    month = date.today().month
    if month in (3, 4, 5):
        return 'spring'
    elif month in (6, 7, 8):
        return 'summer'
    elif month in (9, 10, 11):
        return 'autumn'
    else:
        return 'winter'


# Allergen mapping: health condition → allergen strings in recipe.allergens[]
ALLERGEN_HARD_EXCLUDE = {
    'nut_allergy': ['tree_nuts', 'peanuts', 'nuts', 'almonds', 'walnuts', 'cashews', 'pecans', 'pistachios', 'hazelnuts', 'macadamia'],
    'shellfish_allergy': ['shellfish', 'shrimp', 'crab', 'lobster', 'mussels', 'clams', 'oysters', 'scallops'],
    'egg_allergy': ['egg', 'eggs'],
    'soy_allergy': ['soy', 'soya', 'tofu', 'tempeh', 'edamame'],
    'celiac': ['gluten', 'wheat', 'barley', 'rye'],
    'lactose_intolerant': ['dairy', 'milk', 'lactose', 'cheese', 'cream'],
    'food_allergies': [],  # generic, no auto-exclude
}


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
    """Score and rank recipes from DB based on full user context.

    27 scoring dimensions (~250+ point scale):
      Core:        meal type +30, time-of-day +15, goal +25
      Health:      condition boost +20 / penalty -40, allergen hard-exclude -1000
      Macros:      cal+protein+carbs+fat adaptive fit +28, trajectory correction +10
      Context:     coaching +12, seasonal+lifestyle +10, workout +14, recovery +8
      Variety:     cuisine diversity -15, protein rotation -12, recent meal -30
      Preference:  liked +15 (recency-weighted), disliked -100
      Practical:   pantry match +15, difficulty progression +8, cooking time +5/-5
      Nutrition:   energy density +8, fiber/sugar +8, satiety +8, hydration +6
      Budget:      cost awareness +5
      Jitter:      random +0-5
    """
    # Select only columns needed for scoring — skip heavy JSON blobs (steps, tips)
    _SCORE_COLS = ("r.id, r.name, r.category, r.cuisine, r.meal_type, r.difficulty, "
                   "r.calories, r.protein, r.carbs, r.fat, r.fiber, r.sugar, "
                   "r.total_time_min, r.prep_time_min, r.cook_time_min, r.servings, "
                   "r.ingredients, r.allergens, r.meal_prep_friendly, r.description")

    with use_db() as db:
        conditions = ["r.status = 'active'"]
        params = []

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

        remaining = context.get('remaining', {})
        if remaining.get('calories'):
            max_cal = int(remaining['calories'] * 1.2)
            conditions.append("r.calories <= ?")
            params.append(max_cal)

        where = " AND ".join(conditions)
        rows = db.execute(
            f"SELECT {_SCORE_COLS} FROM recipes r WHERE {where} LIMIT 200", params
        ).fetchall()

        recipe_ids = [r['id'] for r in rows]
        if not recipe_ids:
            return []

        placeholders = ','.join('?' * len(recipe_ids))
        all_tags = db.execute(
            f"SELECT recipe_id, dimension, tag FROM recipe_tags WHERE recipe_id IN ({placeholders})",
            recipe_ids
        ).fetchall()

    tags_by_recipe = {}
    for t in all_tags:
        tags_by_recipe.setdefault(t['recipe_id'], {}).setdefault(t['dimension'], []).append(t['tag'])

    # ═══════════════════════════════════════════════════
    # Extract all context signals
    # ═══════════════════════════════════════════════════
    meal_types = context.get('meal_types', [])
    goal = context.get('goal', '')
    liked = [f.lower().strip() for f in context.get('liked', [])]
    disliked = [f.lower().strip() for f in context.get('disliked', [])]
    hour_of_day = context.get('hour_of_day')
    day_of_week = context.get('day_of_week')
    recent_meal_names = [n.lower() for n in context.get('recent_meal_names', [])]
    recent_cuisines = [c.lower() for c in context.get('recent_cuisines', [])]
    recent_protein_sources = [p.lower() for p in context.get('recent_protein_sources', [])]
    meals_eaten_today = context.get('meals_eaten_today', 0)
    today_meal_names = [n.lower() for n in context.get('today_meal_names', [])]
    # Build keyword sets for diversity checking
    _SEAFOOD = {'shrimp', 'fish', 'salmon', 'tuna', 'cod', 'tilapia', 'prawn', 'prawns',
                 'crab', 'lobster', 'mahi', 'halibut', 'trout', 'sardine', 'mackerel',
                 'anchovy', 'anchovies', 'clam', 'clams', 'mussel', 'mussels', 'oyster',
                 'oysters', 'squid', 'calamari', 'octopus', 'scallop', 'scallops',
                 'swordfish', 'bass', 'snapper', 'haddock', 'catfish', 'ceviche',
                 'sushi', 'sashimi', 'seafood', 'shellfish'}
    _POULTRY = {'chicken', 'turkey', 'duck', 'poultry', 'hen', 'wings', 'thigh', 'thighs', 'breast'}
    _RED_MEAT = {'beef', 'steak', 'pork', 'lamb', 'veal', 'bison', 'venison',
                 'burger', 'meatball', 'meatballs', 'ribs', 'bacon', 'ham', 'sausage'}
    _FOOD_GROUPS = [('seafood', _SEAFOOD), ('poultry', _POULTRY), ('red_meat', _RED_MEAT)]

    def _detect_food_groups(text):
        """Detect which food groups appear in a text string using substring matching."""
        text_lower = text.lower()
        groups = set()
        for group_name, group_words in _FOOD_GROUPS:
            for keyword in group_words:
                if keyword in text_lower:
                    groups.add(group_name)
                    break
        return groups

    # Today's food groups — HARD EXCLUDE same protein type twice in one day
    _today_groups = set()
    for meal_name in today_meal_names:
        _today_groups |= _detect_food_groups(meal_name)

    # Weekly food group frequency (moderate penalty)
    _weekly_group_counts = {}
    for meal_name in recent_meal_names:
        words = set(meal_name.split())
        for group_name, group_words in _FOOD_GROUPS:
            if words & group_words:
                _weekly_group_counts[group_name] = _weekly_group_counts.get(group_name, 0) + 1
    health_conditions = context.get('health_conditions', [])
    pantry = [p.lower().strip() for p in context.get('pantry', [])]
    workout_cals = context.get('workout_calories_today', 0)
    has_recent_workout = context.get('has_recent_workout', False)
    is_recovery_day = context.get('is_recovery_day', False)
    weight_trend = context.get('weight_trend', 'stable')
    weekly_trend = context.get('weekly_macro_trend', {})
    water_ml = context.get('water_ml', 0)
    water_target = context.get('water_target_ml', 2300)
    days_with_logs = context.get('days_with_logs', 0)
    mins_since_meal = context.get('minutes_since_last_meal')
    problematic_foods = [f.lower().strip() for f in context.get('problematic_foods', [])]
    beneficial_foods = [f.lower().strip() for f in context.get('beneficial_foods', [])]

    meal_fraction = _adaptive_meal_fraction(meals_eaten_today)
    time_meals = _time_appropriate_meals(hour_of_day)
    season = _current_season()
    is_weekend = day_of_week in (0, 6) if day_of_week is not None else False
    is_meal_prep_day = day_of_week == 0 if day_of_week is not None else False  # Sunday

    # Cuisine frequency for diversity — prefer pre-computed from MealHistory if available
    cuisine_counts = context.get('cuisine_frequency', {})
    if not cuisine_counts:
        for c in recent_cuisines:
            cuisine_counts[c] = cuisine_counts.get(c, 0) + 1

    # Protein source frequency for rotation — prefer pre-computed from MealHistory
    protein_counts = context.get('protein_frequency', {})
    if not protein_counts:
        for p in recent_protein_sources:
            protein_counts[p] = protein_counts.get(p, 0) + 1

    # Boost for missing protein sources (encourage variety)
    missing_proteins = context.get('missing_proteins', [])

    # Pre-compute health boost/penalty tag sets
    health_boost_tags = {}
    health_penalty_tags = {}
    for cond in health_conditions:
        for dim, tags in HEALTH_CONDITION_BOOSTS.get(cond, {}).items():
            for tag in tags:
                health_boost_tags[(dim, tag)] = health_boost_tags.get((dim, tag), 0) + 1
        for dim, tags in HEALTH_CONDITION_PENALTIES.get(cond, {}).items():
            for tag in tags:
                health_penalty_tags[(dim, tag)] = health_penalty_tags.get((dim, tag), 0) + 1

    # Pre-compute allergen exclusion set
    excluded_allergens = set()
    for cond in health_conditions:
        for allergen in ALLERGEN_HARD_EXCLUDE.get(cond, []):
            excluded_allergens.add(allergen.lower())

    # Macro trajectory analysis
    protein_deficit = False
    calorie_surplus = False
    carb_surplus = False
    fat_surplus = False
    if weekly_trend and weekly_trend.get('days_tracked', 0) >= 3:
        avg_prot = weekly_trend.get('avg_protein', 0)
        tgt_prot = weekly_trend.get('target_protein', 0)
        if tgt_prot and avg_prot < tgt_prot * 0.85:
            protein_deficit = True
        avg_cal = weekly_trend.get('avg_calories', 0)
        tgt_cal = weekly_trend.get('target_calories', 0)
        if tgt_cal and avg_cal > tgt_cal * 1.1:
            calorie_surplus = True
        avg_carbs = weekly_trend.get('avg_carbs', 0)
        tgt_carbs = weekly_trend.get('target_carbs', 0)
        if tgt_carbs and avg_carbs > tgt_carbs * 1.15:
            carb_surplus = True
        avg_fat = weekly_trend.get('avg_fat', 0)
        tgt_fat = weekly_trend.get('target_fat', 0)
        if tgt_fat and avg_fat > tgt_fat * 1.15:
            fat_surplus = True

    # Hydration gap
    dehydrated = water_target > 0 and water_ml < water_target * 0.5

    # User experience level
    is_beginner = days_with_logs < 7
    is_experienced = days_with_logs >= 30

    # Hunger signal from time since last meal
    very_hungry = mins_since_meal is not None and mins_since_meal > 300  # 5+ hours

    # ═══════════════════════════════════════════════════
    # Pre-parse lightweight recipe dicts for scoring
    # Only parse ingredients/allergens JSON, skip steps/tips
    # ═══════════════════════════════════════════════════
    _json_fields = ('ingredients', 'allergens')
    parsed_recipes = []
    for row in rows:
        r = dict(row)
        for field in _json_fields:
            if r.get(field) and isinstance(r[field], str):
                try:
                    r[field] = json.loads(r[field])
                except (json.JSONDecodeError, TypeError):
                    r[field] = []
        # Pre-compute ingredient text once per recipe (used in allergens, preferences, pantry)
        ings = r.get('ingredients', [])
        r['_ing_text'] = ' '.join(
            i.lower() if isinstance(i, str) else i.get('item', '').lower()
            for i in ings
        )
        parsed_recipes.append(r)

    # ═══════════════════════════════════════════════════
    # Score each recipe
    # ═══════════════════════════════════════════════════
    scored = []
    for recipe in parsed_recipes:
        rtags = tags_by_recipe.get(recipe['id'], {})
        score = 0.0
        ing_text = recipe['_ing_text']

        # ── 1. Allergen hard-exclude (-1000) ──
        if excluded_allergens:
            recipe_allergens = {a.lower() for a in recipe.get('allergens', [])}
            if recipe_allergens & excluded_allergens:
                score -= 1000
            else:
                for allergen in excluded_allergens:
                    if allergen in ing_text:
                        score -= 1000
                        break

        # ── 2. Meal type match (+30 / -200) ──
        recipe_meal = recipe.get('meal_type', 'any')
        if meal_types:
            if recipe_meal in meal_types:
                score += 30
            elif recipe_meal == 'any':
                score += 5
            else:
                # Wrong meal type — heavy penalty
                # Breakfast is special: lamb chops, steak, etc. should never appear
                if 'breakfast' in meal_types and recipe_meal in ('dinner', 'lunch'):
                    score -= 200
                elif 'dinner' in meal_types and recipe_meal == 'breakfast':
                    score -= 100
                else:
                    score -= 50

        # ── 3. Time-of-day (+15 / -100) ──
        if time_meals and recipe_meal in time_meals:
            score += 15
        elif time_meals and recipe_meal == 'any':
            score += 5
        elif time_meals and recipe_meal not in time_meals and recipe_meal != 'any':
            # Dinner items in the morning, breakfast at night, etc.
            score -= 30

        # ── 3b. Meal suitability check (tag-based) ──
        meal_suit = rtags.get('meal_suitability', [])
        if meal_types:
            requested = meal_types[0] if meal_types else 'dinner'
            suit_key = f'{requested}_suitable'
            if suit_key in meal_suit:
                score += 25  # Recipe is suitable for this meal
            else:
                score -= 150  # Recipe is NOT suitable — heavy penalty

        # ── 4. Goal alignment (+25) ──
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

        # ── 5. Health condition fit (+20 / -40) ──
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

        # ── 6. Macro fit (+28) — all four macros, adaptive fraction ──
        if remaining:
            rem_cal = remaining.get('calories', 500)
            rem_prot = remaining.get('protein', 30)
            rem_carbs = remaining.get('carbs', 50)
            rem_fat = remaining.get('fat', 20)
            effective_cal = rem_cal + (workout_cals * 0.5 if workout_cals else 0)

            # Protein weight boosted if weekly deficit detected
            prot_weight = 10 if protein_deficit else 8

            if effective_cal > 0:
                target_cal = effective_cal * meal_fraction
                cal_fit = max(0, 1 - abs(recipe['calories'] - target_cal) / max(effective_cal, 1))
                score += cal_fit * 8
            if rem_prot > 0:
                target_prot = rem_prot * meal_fraction
                prot_fit = max(0, 1 - abs(recipe['protein'] - target_prot) / max(rem_prot, 1))
                score += prot_fit * prot_weight
            if rem_carbs > 0:
                target_carbs = rem_carbs * meal_fraction
                carb_fit = max(0, 1 - abs(recipe['carbs'] - target_carbs) / max(rem_carbs, 1))
                carb_weight = 4 if not carb_surplus else 6  # weight more if trending over
                score += carb_fit * carb_weight
            if rem_fat > 0:
                target_fat = rem_fat * meal_fraction
                fat_fit = max(0, 1 - abs(recipe['fat'] - target_fat) / max(rem_fat, 1))
                fat_weight = 4 if not fat_surplus else 6
                score += fat_fit * fat_weight

            if recipe['calories'] <= rem_cal and recipe['protein'] <= rem_prot:
                score += 4

        # ── 7. Macro trajectory correction (+10) ──
        macro_tags = rtags.get('macro_profile', [])
        if protein_deficit:
            if 'very_high_protein' in macro_tags or 'ultra_high_protein' in macro_tags:
                score += 10
            elif 'high_protein' in macro_tags:
                score += 6
        if calorie_surplus:
            if 'very_low_calorie' in macro_tags or 'low_calorie' in macro_tags:
                score += 6
            if 'high_calorie' in macro_tags or 'very_high_calorie' in macro_tags:
                score -= 6
        if carb_surplus:
            if 'low_carb' in macro_tags or 'very_low_carb' in macro_tags:
                score += 5
        if fat_surplus:
            if 'low_fat' in macro_tags or 'very_low_fat' in macro_tags:
                score += 5

        # ── 8. Coaching context (+12) ──
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
        if weight_trend == 'plateau':
            if 'plateau_breaker' in coaching_tags:
                score += 12
            if 'metabolic_boost' in coaching_tags:
                score += 8
        if very_hungry and 'snack_replacement' in coaching_tags:
            score += 5

        # ── 9. Seasonal + lifestyle (+10) ──
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

        # Meal prep day (Sunday)
        if is_meal_prep_day:
            if recipe.get('meal_prep_friendly'):
                score += 8
            if 'batch_cook' in rtags.get('cooking_style', []):
                score += 4
            if 'freezer_friendly' in lifestyle_tags:
                score += 3

        # ── 10. Workout awareness (+14) ──
        if has_recent_workout:
            if 'recovery_focused' in rtags.get('health', []):
                score += 8
            if 'post_workout' == recipe.get('meal_type'):
                score += 6
            if 'high_protein' in macro_tags or 'very_high_protein' in macro_tags:
                score += 4
            if 'electrolyte_rich' in rtags.get('health', []):
                score += 4
        if is_recovery_day:
            if 'recovery_focused' in rtags.get('health', []):
                score += 8
            if 'anti_inflammatory' in rtags.get('health', []):
                score += 5

        # ── 11. Cuisine diversity (-30) ──
        recipe_cuisine = (recipe.get('cuisine') or '').lower()
        if recipe_cuisine and recipe_cuisine in cuisine_counts:
            freq = cuisine_counts[recipe_cuisine]
            score -= min(freq * 8, 30)

        # ── 12. Protein source rotation (-35 / +15) ──
        recipe_psources = rtags.get('protein_source', [])
        if recipe_psources and protein_counts:
            for ps in recipe_psources:
                ps_lower = ps.lower()
                if ps_lower in protein_counts:
                    score -= min(protein_counts[ps_lower] * 8, 35)
                    break
        # Boost recipes with protein sources the user hasn't eaten recently
        if recipe_psources and missing_proteins:
            for ps in recipe_psources:
                if ps.lower() in missing_proteins:
                    score += 20
                    break

        # ── 13. Recent meal penalty (-50, cumulative) ──
        name_lower = recipe['name'].lower()
        name_words = set(name_lower.split())
        recipe_words = name_words  # alias for later sections
        weekly_repeat_penalty = 0
        if recent_meal_names:
            for recent in recent_meal_names:
                recent_words = recent.split()
                if name_lower == recent:
                    weekly_repeat_penalty += 50  # exact repeat this week
                elif sum(1 for w in recent_words if len(w) > 3 and w in name_words) >= 2:
                    weekly_repeat_penalty += 30  # very similar dish
                elif sum(1 for w in recent_words if len(w) > 3 and w in name_words) == 1 and len(recent_words) <= 3:
                    weekly_repeat_penalty += 15  # partial overlap
            score -= min(weekly_repeat_penalty, 80)  # cap at -80

        # ── 13b. Same-day protein exclusion (-500) ──
        # Do NOT suggest the same protein type twice in one day
        if _today_groups:
            # Use primary_protein tag for reliable detection
            recipe_prot = rtags.get('primary_protein', ['none'])
            if isinstance(recipe_prot, list):
                recipe_prot = recipe_prot[0] if recipe_prot else 'none'
            # Map primary_protein to food groups
            _PROT_TO_GROUP = {
                'chicken': 'poultry', 'turkey': 'poultry',
                'beef': 'red_meat', 'pork': 'red_meat', 'lamb': 'red_meat',
                'salmon': 'seafood', 'tuna': 'seafood', 'shrimp': 'seafood', 'white_fish': 'seafood',
            }
            recipe_group = _PROT_TO_GROUP.get(recipe_prot)
            if recipe_group and recipe_group in _today_groups:
                score -= 500  # Hard exclude — never repeat protein type same day
            # Fallback: also check name/ingredients for safety
            elif not recipe_group:
                recipe_groups = _detect_food_groups(name_lower)
                ing_text = recipe.get('_ing_text', '')
                if ing_text:
                    recipe_groups |= _detect_food_groups(ing_text)
                if recipe_groups & _today_groups:
                    score -= 500

        # ── 13c. Weekly food group diversity (-25 per repeat) ──
        if _weekly_group_counts:
            rgroups = _detect_food_groups(name_lower) | _detect_food_groups(recipe.get('_ing_text', ''))
            for grp in rgroups:
                freq = _weekly_group_counts.get(grp, 0)
                if freq >= 3:
                    score -= 25  # Ate this type 3+ times this week
                elif freq >= 2:
                    score -= 12  # Ate this type twice this week

        # ── 14. Preference match with recency weighting (+15 / -100) ──
        for idx, liked_food in enumerate(liked):
            liked_words = liked_food.split()
            if any(w in name_words for w in liked_words) or liked_food in ing_text:
                # More recent preferences (later in array) get higher weight
                recency = 0.5 + 0.5 * (idx / max(len(liked), 1))
                score += 15 * recency
                break

        for disliked_food in disliked:
            disliked_words = disliked_food.split()
            if any(w in name_words for w in disliked_words) or disliked_food in ing_text:
                score -= 100
                break

        # ── 14b. Feeling-based food scoring (+10 / -30) ──
        for prob_food in problematic_foods:
            if prob_food in name_lower or prob_food in ing_text:
                score -= 30
                break
        for ben_food in beneficial_foods:
            if ben_food in name_lower or ben_food in ing_text:
                score += 10
                break

        # ── 15. Pantry match with coverage ratio (+15) ──
        if pantry:
            pantry_hits = sum(1 for p in pantry if p in ing_text)
            score += min(pantry_hits * 3, 12)
            # Bonus if pantry covers most ingredients
            ing_count_tags = rtags.get('ingredient_count', [])
            if ing_count_tags:
                try:
                    total_ings = int(ing_count_tags[0])
                    if total_ings > 0 and pantry_hits / total_ings >= 0.6:
                        score += 3  # user can almost make this now
                except (ValueError, IndexError):
                    pass

        # ── 16. Energy density for goals (+8) ──
        energy_tags = rtags.get('energy_density', [])
        if goal in ('fat_loss', 'aggressive_fat_loss'):
            if 'very_low' in energy_tags or 'low' in energy_tags:
                score += 8  # volumetric eating — more food, fewer calories
            elif 'high' in energy_tags:
                score -= 4
        elif goal in ('muscle_gain', 'lean_bulk'):
            if 'high' in energy_tags:
                score += 5  # calorie-dense for surplus
            elif 'very_low' in energy_tags:
                score -= 3

        # ── 17. Fiber and sugar gap (+8) ──
        remaining_fiber = remaining.get('fiber', 0)
        if remaining_fiber > 10:
            if 'high_fiber' in macro_tags or 'very_high_fiber' in macro_tags:
                score += 5
            elif 'good_fiber' in macro_tags:
                score += 3
        processed_sugar = remaining.get('sugar_processed', 0)
        if processed_sugar > 30:
            if 'high_sugar' in macro_tags:
                score -= 8

        # ── 18. Satiety boost for fat loss (+8) ──
        if goal in ('fat_loss', 'aggressive_fat_loss'):
            sat_tags = rtags.get('satiety', [])
            if 'high_satiety' in sat_tags or 'very_filling' in sat_tags:
                score += 5
            if 'slow_digesting' in sat_tags:
                score += 3
        # Also boost satiety if very hungry (long gap since last meal)
        if very_hungry:
            sat_tags = rtags.get('satiety', [])
            if 'high_satiety' in sat_tags or 'very_filling' in sat_tags:
                score += 4

        # ── 19. Hydration awareness (+6) ──
        if dehydrated:
            if 'hydrating' in rtags.get('health', []):
                score += 6
            if 'electrolyte_rich' in rtags.get('health', []):
                score += 4

        # ── 20. Difficulty progression (+8) ──
        difficulty = recipe.get('difficulty', 'medium')
        complexity_tags = rtags.get('ingredient_complexity', [])
        if is_beginner:
            if difficulty == 'easy':
                score += 6
            elif difficulty == 'hard':
                score -= 5
            if 'minimal' in complexity_tags or 'simple' in complexity_tags:
                score += 4
            if 'beginner_cook' in coaching_tags or 'intro_to_cooking' in coaching_tags:
                score += 6
        elif is_experienced:
            if difficulty == 'hard':
                score += 2  # small bonus for variety
            if 'complex_recipe' in coaching_tags:
                score += 2

        # ── 21. Cost awareness (+5) ──
        cost_tags = rtags.get('cost', [])
        # Users with large pantries tend to be budget-conscious
        if len(pantry) >= 8:
            if 'budget_friendly' in cost_tags:
                score += 5
            elif 'luxury' in cost_tags:
                score -= 3
        # End of month budget heuristic (days 25-31)
        if date.today().day >= 25:
            if 'budget_friendly' in cost_tags:
                score += 3

        # ── 22. Cooking time (+5/-5) ──
        cook_time = recipe.get('total_time_min', 60)
        if cook_time <= 15:
            score += 5
        elif cook_time <= 30:
            score += 3
        if not is_weekend and cook_time > 45:
            score -= 5
        # Late night: penalize long cook times
        if hour_of_day is not None and hour_of_day >= 21 and cook_time > 30:
            score -= 4

        # ── 24. Flavor diversity (+10 / -10) ──
        # Penalize if today's meals already have the same dominant flavor
        recipe_flavors = set(rtags.get('flavor_profile', []))
        if today_meal_names and recipe_flavors:
            # Build today's flavor profile from recent meal tags
            today_flavor_counts = {}
            for tmeal in today_meal_names:
                for flav in recipe_flavors:
                    # Simple: check if flavor-indicating words appear in today's meal names
                    if flav in ('spicy_hot',) and any(w in tmeal for w in ('spicy', 'chili', 'hot')):
                        today_flavor_counts[flav] = today_flavor_counts.get(flav, 0) + 1
                    elif flav in ('cheesy',) and 'cheese' in tmeal:
                        today_flavor_counts[flav] = today_flavor_counts.get(flav, 0) + 1
            for flav, cnt in today_flavor_counts.items():
                if flav in recipe_flavors and cnt >= 1:
                    score -= 10  # Already had this flavor today
        # Boost uncommon/diverse flavors
        diverse_flavors = {'smoky', 'umami', 'citrusy', 'earthy', 'herbal'}
        if recipe_flavors & diverse_flavors:
            score += 5

        # ── 25. Prep style preference (+8 / -5) ──
        recipe_prep = set(rtags.get('prep_style', []))
        if hour_of_day is not None:
            # Evening/late: prefer hands_off, one_pot, minimal_cooking
            if hour_of_day >= 19 and recipe_prep & {'hands_off', 'one_pot', 'minimal_cooking'}:
                score += 8
            # Morning: prefer no_cook, minimal_cooking
            if hour_of_day < 10 and recipe_prep & {'no_cook', 'minimal_cooking'}:
                score += 8
            # Weeknight (Mon-Thu evening): boost quick/easy
            if day_of_week in (0, 1, 2, 3) and hour_of_day >= 17:
                if recipe_prep & {'one_pot', 'hands_off', 'minimal_cooking'}:
                    score += 5
            # Weekend: don't penalize active_cooking
            if day_of_week in (5, 6) and 'active_cooking' in recipe_prep:
                score += 3
        # Penalize marinating/chilling if user wants quick
        if mins_since_meal is not None and mins_since_meal > 300:
            # User is hungry (5+ hours since last meal) — penalize slow prep
            if recipe_prep & {'requires_marinating', 'requires_chilling'}:
                score -= 10

        # ── 26. Equipment availability (+5 / -5) ──
        recipe_equip = set(rtags.get('equipment_needs', []))
        # Boost simple equipment
        if 'no_special_equipment' in recipe_equip:
            score += 5
        if 'stovetop_only' in recipe_equip and not (recipe_equip & {'oven_required', 'grill_required'}):
            score += 3
        # Penalize specialty equipment for weeknight quick meals
        if hour_of_day is not None and hour_of_day >= 17 and day_of_week in (0, 1, 2, 3):
            if recipe_equip & {'grill_required', 'slow_cooker'}:
                score -= 5

        # ── 27. Primary protein diversity (tag-based) (+15 / -20) ──
        # Use primary_protein tag for weekly rotation
        recipe_prot_tag = rtags.get('primary_protein', ['none'])
        if isinstance(recipe_prot_tag, list):
            recipe_prot_tag = recipe_prot_tag[0] if recipe_prot_tag else 'none'
        if recipe_prot_tag != 'none' and protein_counts:
            # Check how often this specific protein appeared this week
            # protein_counts may use tag names or raw names
            prot_freq = protein_counts.get(recipe_prot_tag, 0)
            if prot_freq == 0:
                score += 15  # Novel protein this week — big boost
            elif prot_freq == 1:
                score += 5   # Only had it once — still ok
            elif prot_freq >= 3:
                score -= 20  # Had it 3+ times this week — penalize

        # ── 28. Random variety ──
        score += random.uniform(0, 15)

        recipe['tags'] = rtags

        # Penalize recipes that were recently suggested (avoid same results on refresh)
        now = time.time()
        rid = recipe['id']
        if rid in _recently_suggested and (now - _recently_suggested[rid]) < _RECENT_SUGGEST_TTL:
            score -= 25

        scored.append((score, recipe))

    # Clean up expired entries
    now = time.time()
    expired = [k for k, v in _recently_suggested.items() if now - v > _RECENT_SUGGEST_TTL]
    for k in expired:
        del _recently_suggested[k]

    scored.sort(key=lambda x: -x[0])
    results = []
    for i, (score, recipe) in enumerate(scored[:limit]):
        # Record as recently suggested
        _recently_suggested[recipe['id']] = time.time()
        results.append({
            'rank': i + 1,
            'id': recipe['id'],
            'name': recipe['name'],
            'description': recipe.get('description', ''),
            'why': _generate_why(recipe, context, i, recipe.get('_ing_text', '')),
            'calories': recipe['calories'],
            'protein': recipe['protein'],
            'carbs': recipe['carbs'],
            'fat': recipe['fat'],
            'has_recipe': True
        })
    return results


def _generate_why(recipe, context, rank, ing_text=''):
    reasons = []
    remaining = context.get('remaining', {})
    hour = context.get('hour_of_day')
    meals_eaten = context.get('meals_eaten_today', 0)
    health_conditions = context.get('health_conditions', [])
    has_recent_workout = context.get('has_recent_workout', False)
    is_recovery_day = context.get('is_recovery_day', False)
    weight_trend = context.get('weight_trend', 'stable')
    weekly_trend = context.get('weekly_macro_trend', {})
    pantry = context.get('pantry', [])
    water_ml = context.get('water_ml', 0)
    water_target = context.get('water_target_ml', 2300)
    days_with_logs = context.get('days_with_logs', 0)
    rtags = recipe.get('tags', {})
    goal = context.get('goal', '')

    # Lead reason for #1
    if rank == 0:
        rem_cal = remaining.get('calories', 0)
        rem_prot = remaining.get('protein', 0)
        if rem_cal and rem_prot:
            reasons.append(f"Best fit for your remaining {rem_cal}cal / {rem_prot}g protein")
        else:
            reasons.append("Best overall match for your goals")

    # Macro trajectory correction
    if weekly_trend.get('days_tracked', 0) >= 3:
        avg_prot = weekly_trend.get('avg_protein', 0)
        tgt_prot = weekly_trend.get('target_protein', 0)
        if tgt_prot and avg_prot < tgt_prot * 0.85:
            mp = rtags.get('macro_profile', [])
            if 'very_high_protein' in mp or 'ultra_high_protein' in mp:
                reasons.append("helps fix your weekly protein gap")

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

    # Post-workout / recovery context
    if has_recent_workout:
        if 'recovery_focused' in rtags.get('health', []):
            reasons.append("great for post-workout recovery")
        elif 'high_protein' in rtags.get('macro_profile', []):
            reasons.append("high protein for your workout recovery")
    elif is_recovery_day:
        if 'anti_inflammatory' in rtags.get('health', []):
            reasons.append("supports recovery after yesterday's workout")

    # Health condition relevance
    if health_conditions and len(reasons) < 5:
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
                boosts = HEALTH_CONDITION_BOOSTS.get(cond, {})
                for dim, tags in boosts.items():
                    if any(t in rtags.get(dim, []) for t in tags):
                        reasons.append(label)
                        break
                else:
                    continue
                break

    # Hydration
    if water_target > 0 and water_ml < water_target * 0.5:
        if 'hydrating' in rtags.get('health', []):
            reasons.append("helps with your hydration")

    # Plateau coaching
    if weight_trend == 'plateau' and any(t in rtags.get('coaching', []) for t in ('plateau_breaker', 'metabolic_boost')):
        reasons.append("may help break your plateau")

    # Energy density
    energy = rtags.get('energy_density', [])
    if goal in ('fat_loss', 'aggressive_fat_loss') and ('very_low' in energy or 'low' in energy):
        reasons.append("low calorie density — more food, fewer calories")
    elif goal in ('muscle_gain', 'lean_bulk') and 'high' in energy:
        reasons.append("calorie-dense for your bulk")

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

    # Satiety
    if goal in ('fat_loss', 'aggressive_fat_loss'):
        sat = rtags.get('satiety', [])
        if 'high_satiety' in sat or 'very_filling' in sat:
            reasons.append("keeps you full longer")

    # Pantry match
    if pantry:
        hits = [p for p in pantry if p.lower() in ing_text]
        if len(hits) >= 3:
            reasons.append(f"uses {', '.join(hits[:3])} from your pantry")
        elif len(hits) == 2:
            reasons.append(f"uses {hits[0]} and {hits[1]} you have")
        elif len(hits) == 1:
            reasons.append(f"uses {hits[0]} you have")

    # Meal prep day
    day_of_week = context.get('day_of_week')
    if day_of_week == 0 and recipe.get('meal_prep_friendly'):
        reasons.append("great for Sunday meal prep")

    # Difficulty for beginners
    if days_with_logs < 7 and recipe.get('difficulty') == 'easy':
        reasons.append("easy to make")

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

    # Cost
    cost = rtags.get('cost', [])
    if 'budget_friendly' in cost:
        reasons.append("budget friendly")

    # Cuisine
    if recipe.get('cuisine') and recipe['cuisine'] != 'International':
        reasons.append(f"{recipe['cuisine']} cuisine")

    # Flavor profile highlights
    flavors = rtags.get('flavor_profile', [])
    flavor_labels = {'smoky': 'smoky flavor', 'umami': 'rich umami taste', 'citrusy': 'bright citrus notes',
                     'herbal': 'fresh herbs', 'spicy_hot': 'spicy kick'}
    for flav, label in flavor_labels.items():
        if flav in flavors and len(reasons) < 6:
            reasons.append(label)
            break

    # Prep style highlights
    prep = rtags.get('prep_style', [])
    if 'no_cook' in prep and len(reasons) < 6:
        reasons.append("no cooking required")
    elif 'one_pot' in prep and len(reasons) < 6:
        reasons.append("one-pot — easy cleanup")
    elif 'hands_off' in prep and len(reasons) < 6:
        reasons.append("mostly hands-off cooking")

    # Primary protein for context
    prot_tag = rtags.get('primary_protein', ['none'])
    if isinstance(prot_tag, list):
        prot_tag = prot_tag[0] if prot_tag else 'none'
    if prot_tag != 'none' and len(reasons) < 6:
        missing_prots = context.get('missing_proteins', [])
        if prot_tag in missing_prots:
            reasons.append(f"{prot_tag} — you haven't had this recently")

    return '. '.join(reasons[:6]) if reasons else "Good match for your goals"


def insert_recipe(recipe_data, tags_dict=None):
    """Insert recipe and optionally its tags in a single transaction."""
    with use_db() as db:
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
        if tags_dict:
            _insert_tags_on_conn(db, recipe_id, tags_dict)
        db.commit()
        return recipe_id


def _insert_tags_on_conn(db, recipe_id, tags_dict):
    """Insert tags using an existing connection (no commit)."""
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


def insert_tags(recipe_id, tags_dict):
    """Insert tags in their own transaction. Use insert_recipe(tags_dict=) for atomicity."""
    with use_db() as db:
        _insert_tags_on_conn(db, recipe_id, tags_dict)
        db.commit()


# Whitelist of columns that can be updated via the API
_UPDATABLE_COLUMNS = frozenset({
    'name', 'description', 'category', 'cuisine', 'country_of_origin', 'region',
    'meal_type', 'difficulty', 'prep_time_min', 'cook_time_min', 'total_time_min',
    'servings', 'calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar',
    'ingredients', 'steps', 'tips', 'equipment', 'allergens', 'diet',
    'meal_prep_friendly', 'source', 'status',
})


def update_recipe(recipe_id, updates):
    with use_db() as db:
        sets = []
        params = []
        for key, val in updates.items():
            if key not in _UPDATABLE_COLUMNS:
                continue  # reject unknown/unsafe column names
            if key in ('ingredients', 'steps', 'equipment', 'allergens', 'diet'):
                val = json.dumps(val) if isinstance(val, list) else val
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(recipe_id)
        db.execute(f"UPDATE recipes SET {', '.join(sets)} WHERE id = ?", params)
        db.commit()


def delete_recipe(recipe_id):
    with use_db() as db:
        db.execute("UPDATE recipes SET status = 'archived' WHERE id = ?", (recipe_id,))
        db.commit()


def get_tag_stats():
    with use_db() as db:
        rows = db.execute("""
            SELECT dimension, tag, COUNT(*) as cnt
            FROM recipe_tags rt
            JOIN recipes r ON rt.recipe_id = r.id
            WHERE r.status = 'active'
            GROUP BY dimension, tag
            ORDER BY dimension, cnt DESC
        """).fetchall()
    stats = {}
    for r in rows:
        stats.setdefault(r['dimension'], {})[r['tag']] = r['cnt']
    return stats


def get_overview_stats():
    with use_db() as db:
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
