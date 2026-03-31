import json
import logging

from flask import Blueprint, jsonify, request

from backend.db import use_db
from backend.models import get_recipe, insert_recipe, search_recipes, suggest_recipes
from backend.tag_engine import compute_tags, detect_cuisine
from backend.validation import validate_generated_recipe, validate_meal_plan, validate_suggestion_response

recipes_bp = Blueprint('recipes', __name__)


# ---------------------------------------------------------------------------
#  Cost-tracking helpers
# ---------------------------------------------------------------------------

def _log_cost(endpoint, served_from, recipe_count=0):
    """Log whether a request was served from DB (free) or LLM (paid)."""
    try:
        with use_db() as db:
            db.execute(
                "INSERT INTO llm_cost_log (endpoint, served_from, recipe_count) VALUES (?, ?, ?)",
                (endpoint, served_from, recipe_count)
            )
            db.commit()
    except Exception:
        logging.debug("Failed to log cost entry", exc_info=True)


def _save_suggestion_to_db(s):
    """Persist an LLM-generated suggestion as a lightweight recipe in the DB.

    This means the *next* time someone asks for a similar meal, the DB suggest
    engine can return it without an LLM call.
    """
    try:
        recipe_data = {
            'name': s['name'],
            'description': s.get('description', ''),
            'category': s.get('category', 'general'),
            'cuisine': s.get('cuisine', 'International'),
            'meal_type': s.get('meal_type', 'any'),
            'difficulty': s.get('difficulty', 'medium'),
            'prep_time_min': int(s.get('prep_time_min', 0) or 0),
            'cook_time_min': int(s.get('cook_time_min', 0) or 0),
            'total_time_min': int(s.get('prep_time_min', 0) or 0) + int(s.get('cook_time_min', 0) or 0),
            'servings': 1,
            'calories': int(s.get('calories', 0)),
            'protein': int(s.get('protein', 0)),
            'carbs': int(s.get('carbs', 0)),
            'fat': int(s.get('fat', 0)),
            'fiber': int(s.get('fiber', 0) or 0),
            'sugar': int(s.get('sugar', 0) or 0),
            'ingredients': s.get('ingredients', []),
            'steps': s.get('steps', []),
            'tips': s.get('tips', ''),
            'equipment': s.get('equipment', []),
            'allergens': s.get('allergens', []),
            'diet': s.get('diet', []),
            'meal_prep_friendly': s.get('meal_prep_friendly', False),
            'source': 'llm_cached',
        }

        # Skip if missing critical data
        if not recipe_data['name'] or not recipe_data['calories']:
            return None

        # Skip if already in DB (by name)
        with use_db() as db:
            existing = db.execute(
                "SELECT id FROM recipes WHERE name = ? AND status = 'active' LIMIT 1",
                (recipe_data['name'],)
            ).fetchone()
            if existing:
                return existing['id']

        # Detect cuisine
        cuisine_info = detect_cuisine(recipe_data)
        recipe_data['cuisine'] = cuisine_info.get('cuisine', recipe_data['cuisine'])
        recipe_data['country_of_origin'] = cuisine_info.get('country', 'International')
        recipe_data['region'] = cuisine_info.get('region', 'International')

        # Compute tags
        tags = compute_tags(recipe_data)

        recipe_id = insert_recipe(recipe_data, tags_dict=tags)
        return recipe_id
    except Exception:
        logging.warning("Failed to cache LLM suggestion to DB", exc_info=True)
        return None


def _save_full_recipe_to_db(result, cuisine='', category='', diet_filters=None):
    """Persist a full LLM-generated recipe (with ingredients/steps) to the DB."""
    try:
        # Parse prep/cook time from strings like "15 min"
        def _parse_min(val):
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                import re
                nums = re.findall(r'\d+', val)
                return int(nums[0]) if nums else 0
            return 0

        # Normalize ingredients to structured format
        ingredients = result.get('ingredients', [])
        structured_ings = []
        for ing in ingredients:
            if isinstance(ing, dict):
                structured_ings.append(ing)
            else:
                structured_ings.append({'item': str(ing), 'amount': '', 'grams': 0})

        recipe_data = {
            'name': result.get('name', 'Unnamed Recipe'),
            'description': result.get('description', ''),
            'category': category or result.get('category', 'general'),
            'cuisine': cuisine or result.get('cuisine', 'International'),
            'meal_type': result.get('meal_type', 'any'),
            'difficulty': result.get('difficulty', 'medium'),
            'prep_time_min': _parse_min(result.get('prep_time', result.get('prep_time_min', 0))),
            'cook_time_min': _parse_min(result.get('cook_time', result.get('cook_time_min', 0))),
            'servings': int(result.get('servings', 1) or 1),
            'calories': int(result.get('calories', 0)),
            'protein': int(result.get('protein', 0)),
            'carbs': int(result.get('carbs', 0)),
            'fat': int(result.get('fat', 0)),
            'fiber': int(result.get('fiber', 0) or 0),
            'sugar': int(result.get('sugar', 0) or 0),
            'ingredients': structured_ings,
            'steps': result.get('steps', []),
            'tips': result.get('tips', ''),
            'equipment': result.get('equipment', []),
            'allergens': result.get('allergens', []),
            'diet': diet_filters or result.get('diet', []),
            'meal_prep_friendly': result.get('meal_prep_friendly', False),
            'source': 'llm_cached',
        }
        recipe_data['total_time_min'] = recipe_data['prep_time_min'] + recipe_data['cook_time_min']

        if not recipe_data['name'] or not recipe_data['calories']:
            return None

        # Skip duplicates
        with use_db() as db:
            existing = db.execute(
                "SELECT id FROM recipes WHERE name = ? AND status = 'active' LIMIT 1",
                (recipe_data['name'],)
            ).fetchone()
            if existing:
                return existing['id']

        cuisine_info = detect_cuisine(recipe_data)
        recipe_data['cuisine'] = cuisine_info.get('cuisine', recipe_data['cuisine'])
        recipe_data['country_of_origin'] = cuisine_info.get('country', 'International')
        recipe_data['region'] = cuisine_info.get('region', 'International')

        tags = compute_tags(recipe_data)
        recipe_id = insert_recipe(recipe_data, tags_dict=tags)
        return recipe_id
    except Exception:
        logging.warning("Failed to cache full LLM recipe to DB", exc_info=True)
        return None


# ---------------------------------------------------------------------------
#  LLM-powered endpoints (with DB caching)
# ---------------------------------------------------------------------------

@recipes_bp.route('/suggest-llm', methods=['POST'])
def suggest_llm():
    """Generate recipe suggestions via LLM, then cache them in the DB."""
    from backend.llm_client import call_llm_json

    data = request.get_json() or {}
    meal_types = data.get('meal_types', ['dinner'])
    remaining = data.get('remaining', {})
    goal = data.get('goal', 'maintenance')
    diet_filters = data.get('diet_filters', [])
    liked = data.get('liked', [])
    disliked = data.get('disliked', [])
    hour = data.get('hour_of_day', 12)

    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'
    liked_str = ', '.join(liked[:5]) if liked else 'none'
    disliked_str = ', '.join(disliked[:5]) if disliked else 'none'

    prompt = f"""You are an elite fitness nutrition coach. Suggest exactly 5 meal recipes for a client.

Context:
- Meal type: {', '.join(meal_types)}
- Goal: {goal}
- Remaining macros today: {remaining.get('calories', 2000)} cal, {remaining.get('protein', 40)}g protein, {remaining.get('carbs', 50)}g carbs, {remaining.get('fat', 20)}g fat
- Diet restrictions: {diet_str}
- Foods they like: {liked_str}
- Foods they dislike: {disliked_str}
- Current hour: {hour}:00

Return ONLY a valid JSON object with this exact structure:
{{
  "top_pick_reason": "1-2 sentence explanation of why #1 is the best choice right now",
  "suggestions": [
    {{
      "name": "Appetizing recipe name",
      "description": "One sentence describing the dish",
      "why": "Why this fits the client's needs right now",
      "calories": <integer>,
      "protein": <integer grams>,
      "carbs": <integer grams>,
      "fat": <integer grams>,
      "cuisine": "Italian/Mexican/Thai/etc",
      "category": "poultry/red_meat/fish/seafood/vegan/vegetarian",
      "meal_type": "{meal_types[0]}",
      "difficulty": "easy/medium/hard",
      "prep_time_min": <integer>,
      "cook_time_min": <integer>,
      "rank": <1-5>
    }}
  ]
}}

Rules:
- CRITICAL: protein*4 + carbs*4 + fat*9 must be within 10% of stated calories
- Rank 1 = best fit for remaining macros and goal
- Vary cuisines and protein sources across the 5 suggestions
- Each suggestion should fit within the remaining macro budget
- Respect diet restrictions strictly
- Avoid disliked foods, prefer liked foods
- For {goal}: {"high protein, low cal" if goal in ("fat_loss", "cutting") else "high protein, high carbs" if goal in ("bulking", "muscle_building") else "balanced macros"}"""

    try:
        result = call_llm_json(prompt, max_tokens=3000)
        if isinstance(result, dict) and 'suggestions' in result:
            # Validate LLM response structure with Pydantic
            validated = validate_suggestion_response(result)
            if not validated:
                logging.warning("LLM suggestion response failed validation, using raw response")

            saved_count = 0
            for s in result['suggestions']:
                s['source'] = 'llm'
                # Cache each suggestion to DB for future free retrieval
                db_id = _save_suggestion_to_db(s)
                if db_id:
                    s['id'] = db_id
                    saved_count += 1
            _log_cost('suggest', 'llm', saved_count)
            return jsonify(result)
        return jsonify({'error': 'Invalid LLM response format'}), 500
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'LLM generation failed: {e}'}), 500


@recipes_bp.route('/generate-llm', methods=['POST'])
def generate_recipe_llm():
    """Generate a full recipe via LLM, then cache it in the DB."""
    from backend.llm_client import call_llm_json

    data = request.get_json() or {}
    name = data.get('name', 'a healthy meal')
    calories = data.get('calories', 500)
    protein = data.get('protein', 35)
    carbs = data.get('carbs', 50)
    fat = data.get('fat', 15)
    cuisine = data.get('cuisine', '')
    category = data.get('category', '')
    diet_filters = data.get('diet_filters', [])

    # Check DB first — maybe this exact recipe was already generated
    with use_db() as db:
        existing = db.execute(
            "SELECT id FROM recipes WHERE name = ? AND status = 'active' LIMIT 1",
            (name,)
        ).fetchone()
    if existing:
        full = get_recipe(existing['id'])
        if full and full.get('ingredients') and full.get('steps'):
            # Serve from cache — free!
            ings = full['ingredients']
            _log_cost('generate', 'db_cache', 1)
            return jsonify({
                'name': full['name'],
                'prep_time': f"{full.get('prep_time_min', 0)} min",
                'cook_time': f"{full.get('cook_time_min', 0)} min",
                'servings': str(full.get('servings', 1)),
                'ingredients': [
                    f"{i['amount']} {i['item']}" if isinstance(i, dict) else str(i)
                    for i in (ings if isinstance(ings, list) else [])
                ],
                'steps': full.get('steps', []),
                'tips': full.get('tips', ''),
                'calories': full['calories'],
                'protein': full['protein'],
                'carbs': full['carbs'],
                'fat': full['fat'],
                'source': 'db_cache'
            })

    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'

    prompt = f"""Generate a complete recipe for: "{name}"

Target macros per serving: {calories} cal, {protein}g protein, {carbs}g carbs, {fat}g fat
{f"Cuisine: {cuisine}" if cuisine else ""}
{f"Category: {category}" if category else ""}
Diet restrictions: {diet_str}

Return ONLY a valid JSON object:
{{
  "name": "{name}",
  "description": "One sentence describing the dish",
  "prep_time": "X min",
  "cook_time": "X min",
  "servings": "X",
  "ingredients": [
    {{"item": "ingredient name", "amount": "200g", "grams": 200}},
    ...
  ],
  "steps": ["Step 1...", "Step 2...", ...],
  "tips": "One fitness coaching tip about this meal",
  "equipment": ["pan", "oven", ...],
  "allergens": ["dairy", "gluten", ...],
  "calories": {calories},
  "protein": {protein},
  "carbs": {carbs},
  "fat": {fat}
}}

Rules:
- Include exact gram measurements for all ingredients
- 6-12 ingredients, 4-8 clear steps
- Make it practical, delicious, and achievable for a home cook
- The tip should relate to fitness/nutrition timing/benefits
- Macros must be realistic for the ingredients listed"""

    try:
        result = call_llm_json(prompt, max_tokens=3000)
        if isinstance(result, dict) and ('ingredients' in result or 'steps' in result):
            # Validate LLM response structure with Pydantic
            validated = validate_generated_recipe(result)
            if not validated:
                logging.warning("LLM recipe response failed validation, using raw response")

            # Save full recipe to DB — next time it's free
            db_id = _save_full_recipe_to_db(result, cuisine, category, diet_filters)
            if db_id:
                result['id'] = db_id

            # Normalize ingredients for frontend
            result['ingredients'] = [
                f"{ing.get('amount', '')} {ing.get('item', ing)}".strip()
                if isinstance(ing, dict) else str(ing)
                for ing in result.get('ingredients', [])
            ]
            result['source'] = 'llm'
            _log_cost('generate', 'llm', 1)
            return jsonify(result)
        return jsonify({'error': 'Invalid LLM response format'}), 500
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'LLM recipe generation failed: {e}'}), 500


@recipes_bp.route('', methods=['GET'])
def list_recipes():
    filters = {
        'meal_type': request.args.get('meal_type'),
        'cuisine': request.args.get('cuisine'),
        'category': request.args.get('category'),
        'max_calories': request.args.get('max_calories'),
        'min_protein': request.args.get('min_protein'),
        'max_carbs': request.args.get('max_carbs'),
        'max_fat': request.args.get('max_fat'),
        'max_time': request.args.get('max_time'),
        'search': request.args.get('search'),
        'diet': request.args.get('diet'),
        'goal': request.args.get('goal'),
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(max(1, int(request.args.get('per_page', 20))), 100)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid pagination parameters'}), 400

    result = search_recipes(filters, page, per_page)
    return jsonify(result)


@recipes_bp.route('/<int:recipe_id>', methods=['GET'])
def get_single_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if not recipe:
        return jsonify({'error': 'Recipe not found'}), 404
    return jsonify(recipe)


@recipes_bp.route('/suggest', methods=['POST'])
def suggest():
    data = request.get_json() or {}
    context = {
        'meal_types': data.get('meal_types', []),
        'diet_filters': data.get('diet_filters', []),
        'goal': data.get('goal', ''),
        'remaining': data.get('remaining', {}),
        'liked': data.get('liked', []),
        'disliked': data.get('disliked', []),
        'hour_of_day': data.get('hour_of_day'),
        'day_of_week': data.get('day_of_week'),
        'recent_meal_names': data.get('recent_meal_names', []),
        'recent_cuisines': data.get('recent_cuisines', []),
        'recent_protein_sources': data.get('recent_protein_sources', []),
        'meals_eaten_today': data.get('meals_eaten_today', 0),
        'health_conditions': data.get('health_conditions', []),
        'activity_level': data.get('activity_level', 'moderate'),
        'gender': data.get('gender', ''),
        'age': data.get('age', 0),
        'pantry': data.get('pantry', []),
        'workout_calories_today': data.get('workout_calories_today', 0),
        'has_recent_workout': data.get('has_recent_workout', False),
        'is_recovery_day': data.get('is_recovery_day', False),
        'weight_trend': data.get('weight_trend', 'stable'),
        'weight_change_rate': data.get('weight_change_rate', 0),
        'weekly_macro_trend': data.get('weekly_macro_trend', {}),
        'water_ml': data.get('water_ml', 0),
        'water_target_ml': data.get('water_target_ml', 2300),
        'days_with_logs': data.get('days_with_logs', 0),
        'minutes_since_last_meal': data.get('minutes_since_last_meal'),
    }
    results = suggest_recipes(context, limit=5)
    if not results:
        return jsonify({'suggestions': [], 'top_pick_reason': 'No matching recipes found in database. Try generating recipes first.'})

    _log_cost('suggest', 'db', len(results))

    top = results[0]
    remaining = context.get('remaining', {})
    reason = f"Best match for your remaining {remaining.get('calories', '?')} cal / {remaining.get('protein', '?')}g protein. "
    reason += top.get('why', '')

    return jsonify({
        'top_pick_reason': reason,
        'suggestions': results,
        'source': 'database'
    })


def _extract_ingredient_words(recipe_dict):
    """Extract normalized ingredient keywords from a recipe for overlap scoring."""
    words = set()
    for ing in recipe_dict.get('ingredients', []):
        text = ing.lower() if isinstance(ing, str) else ing.get('item', '').lower()
        for w in text.split():
            if len(w) >= 3 and not w.replace('.', '').replace(',', '').isdigit():
                words.add(w)
    return words


@recipes_bp.route('/meal-plan', methods=['POST'])
def meal_plan():
    """Generate a 7-day meal plan from DB recipes with ingredient overlap optimization."""
    data = request.get_json() or {}
    diet_filters = data.get('diet_filters', [])
    goal = data.get('goal', '')
    target_cal = data.get('target_calories', 2000)
    target_prot = data.get('target_protein', 150)
    liked = data.get('liked', [])
    disliked = data.get('disliked', [])

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    meal_slots = ['breakfast', 'lunch', 'dinner', 'snack']
    used_ids = set()
    plan = []

    # Track ingredient words across the plan for overlap scoring
    plan_ingredients = set()

    # Pre-fetch only id + ingredients (not full rows) for overlap scoring
    from backend.db import use_db
    recipe_ingredients_cache = {}
    with use_db() as db:
        rows = db.execute(
            "SELECT id, ingredients FROM recipes WHERE status = 'active'"
        ).fetchall()
    for row in rows:
        rd = {'ingredients': json.loads(row['ingredients']) if row['ingredients'] else []}
        recipe_ingredients_cache[row['id']] = _extract_ingredient_words(rd)

    for day in days:
        meals = []
        for slot in meal_slots:
            fraction = 0.2 if slot == 'snack' else 0.27
            context = {
                'meal_types': [slot],
                'diet_filters': diet_filters,
                'goal': goal,
                'remaining': {
                    'calories': int(target_cal * fraction),
                    'protein': int(target_prot * fraction)
                },
                'liked': liked,
                'disliked': disliked
            }
            results = suggest_recipes(context, limit=10)

            # Re-rank by ingredient overlap with existing plan
            if plan_ingredients and results:
                for r in results:
                    r_ings = recipe_ingredients_cache.get(r['id'], set())
                    overlap = len(r_ings & plan_ingredients)
                    r['_overlap_score'] = min(overlap * 2, 15)
                results.sort(key=lambda r: -(r.get('_overlap_score', 0) + (10 - r['rank'])))

            pick = None
            for r in results:
                if r['id'] not in used_ids:
                    pick = r
                    break
            if not pick and results:
                pick = results[0]
            if not pick:
                continue

            used_ids.add(pick['id'])
            plan_ingredients.update(recipe_ingredients_cache.get(pick['id'], set()))

            meals.append({
                'type': slot,
                'name': pick['name'],
                'description': pick.get('description', ''),
                'calories': pick['calories'],
                'protein': pick['protein'],
                'carbs': pick['carbs'],
                'fat': pick['fat'],
                'recipe_id': pick['id']
            })
        plan.append({'day': day, 'meals': meals})

    return jsonify({'plan': plan, 'source': 'database'})


@recipes_bp.route('/meal-plan-llm', methods=['POST'])
def meal_plan_llm():
    """Generate a 7-day meal plan via LLM when DB is empty."""
    from backend.llm_client import call_llm_json

    data = request.get_json() or {}
    goal = data.get('goal', 'maintenance')
    target_cal = data.get('target_calories', 2000)
    target_prot = data.get('target_protein', 150)
    diet_filters = data.get('diet_filters', [])

    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'

    prompt = f"""Create a 7-day meal plan for a fitness-focused client.

Target per day: {target_cal} calories, {target_prot}g protein
Goal: {goal}
Diet restrictions: {diet_str}

Return ONLY valid JSON:
{{
  "plan": [
    {{
      "day": "Monday",
      "meals": [
        {{
          "type": "breakfast",
          "name": "Meal name",
          "description": "One sentence description",
          "calories": <int>,
          "protein": <int>,
          "carbs": <int>,
          "fat": <int>
        }}
      ]
    }}
  ]
}}

Rules:
- Each day: breakfast, lunch, dinner, snack (4 meals)
- Daily total should be close to {target_cal} cal and {target_prot}g protein
- protein*4 + carbs*4 + fat*9 must be within 10% of stated calories per meal
- Vary cuisines and proteins across the week
- Respect diet restrictions strictly
- Make meals practical and appetizing"""

    try:
        result = call_llm_json(prompt, max_tokens=6000)
        if isinstance(result, dict) and 'plan' in result:
            # Validate LLM response structure with Pydantic
            validated = validate_meal_plan(result)
            if not validated:
                logging.warning("LLM meal plan response failed validation, using raw response")

            # Cache every meal from the plan to DB
            saved = 0
            for day in result.get('plan', []):
                for meal in day.get('meals', []):
                    meal['meal_type'] = meal.get('type', 'any')
                    db_id = _save_suggestion_to_db(meal)
                    if db_id:
                        meal['recipe_id'] = db_id
                        saved += 1
            _log_cost('meal_plan', 'llm', saved)
            result['source'] = 'llm'
            return jsonify(result)
        return jsonify({'error': 'Invalid meal plan format'}), 500
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Meal plan generation failed: {e}'}), 500


@recipes_bp.route('/<int:recipe_id>/similar', methods=['GET'])
def similar_recipes(recipe_id):
    recipe = get_recipe(recipe_id)
    if not recipe:
        return jsonify({'error': 'Recipe not found'}), 404

    filters = {
        'cuisine': recipe.get('cuisine'),
        'category': recipe.get('category'),
    }
    result = search_recipes(filters, page=1, per_page=6)
    # Exclude the original recipe
    result['recipes'] = [r for r in result['recipes'] if r['id'] != recipe_id][:5]
    return jsonify(result)


# ---------------------------------------------------------------------------
#  Recipe Scaling
# ---------------------------------------------------------------------------

@recipes_bp.route('/<int:recipe_id>/scale', methods=['GET'])
def scale_recipe(recipe_id):
    """Return a recipe with ingredients and macros scaled to requested servings."""
    recipe = get_recipe(recipe_id)
    if not recipe:
        return jsonify({'error': 'Recipe not found'}), 404

    try:
        target_servings = float(request.args.get('servings', recipe.get('servings', 1)))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid servings value'}), 400

    original_servings = max(recipe.get('servings', 1), 1)
    scale_factor = target_servings / original_servings

    # Scale macros
    for field in ('calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar'):
        if recipe.get(field) is not None:
            recipe[field] = round(recipe[field] * scale_factor)

    # Scale ingredients
    scaled_ingredients = []
    for ing in recipe.get('ingredients', []):
        if isinstance(ing, dict):
            scaled = dict(ing)
            if scaled.get('grams'):
                scaled['grams'] = round(scaled['grams'] * scale_factor)
            if scaled.get('amount'):
                scaled['amount'] = _scale_amount_str(scaled['amount'], scale_factor)
            scaled_ingredients.append(scaled)
        elif isinstance(ing, str):
            scaled_ingredients.append(_scale_ingredient_string(ing, scale_factor))
        else:
            scaled_ingredients.append(ing)

    recipe['ingredients'] = scaled_ingredients
    recipe['servings'] = round(target_servings) if target_servings == int(target_servings) else target_servings
    recipe['scale_factor'] = round(scale_factor, 2)

    return jsonify(recipe)


def _scale_amount_str(amount_str, factor):
    """Scale a quantity string like '200g' or '1/2 cup'."""
    import re
    # Match leading number (int, float, or fraction)
    match = re.match(r'^(\d+(?:\.\d+)?(?:/\d+)?)\s*(.*)', str(amount_str))
    if not match:
        return amount_str
    num_str, unit = match.groups()
    try:
        if '/' in num_str:
            parts = num_str.split('/')
            num = float(parts[0]) / float(parts[1])
        else:
            num = float(num_str)
        scaled = num * factor
        # Format nicely
        if scaled == int(scaled):
            return f"{int(scaled)} {unit}".strip()
        return f"{scaled:.1f} {unit}".strip()
    except (ValueError, ZeroDivisionError):
        return amount_str


def _scale_ingredient_string(ing_str, factor):
    """Scale a plain text ingredient like '200g chicken breast'."""
    import re
    match = re.match(r'^(\d+(?:\.\d+)?)\s*(g|ml|oz|lb|kg|cup|cups|tbsp|tsp|tablespoon|teaspoon)?\s*(.*)', ing_str, re.IGNORECASE)
    if not match:
        return ing_str
    num_str, unit, rest = match.groups()
    try:
        scaled = float(num_str) * factor
        unit = unit or ''
        if scaled == int(scaled):
            return f"{int(scaled)}{unit} {rest}".strip()
        return f"{scaled:.1f}{unit} {rest}".strip()
    except ValueError:
        return ing_str


# ---------------------------------------------------------------------------
#  Smart Grocery List
# ---------------------------------------------------------------------------

# Category mapping for common ingredients
_GROCERY_CATEGORIES = {
    'produce': {'onion', 'garlic', 'tomato', 'lettuce', 'spinach', 'kale', 'broccoli',
                'pepper', 'cucumber', 'carrot', 'celery', 'avocado', 'lemon', 'lime',
                'ginger', 'cilantro', 'parsley', 'basil', 'mint', 'mushroom', 'zucchini',
                'potato', 'sweet potato', 'corn', 'peas', 'green beans', 'cabbage',
                'cauliflower', 'asparagus', 'bell pepper', 'jalapeño', 'scallion',
                'arugula', 'banana', 'apple', 'berries', 'blueberries', 'strawberries'},
    'protein': {'chicken', 'beef', 'pork', 'turkey', 'salmon', 'tuna', 'shrimp', 'cod',
                'tofu', 'tempeh', 'egg', 'eggs', 'lamb', 'duck', 'tilapia', 'sausage',
                'bacon', 'steak', 'ground beef', 'ground turkey', 'chicken breast',
                'chicken thigh', 'fish', 'seafood', 'scallops', 'mussels'},
    'dairy': {'milk', 'cheese', 'yogurt', 'butter', 'cream', 'sour cream', 'cream cheese',
              'mozzarella', 'parmesan', 'cheddar', 'feta', 'ricotta', 'cottage cheese',
              'greek yogurt', 'heavy cream', 'whipping cream'},
    'grains': {'rice', 'pasta', 'bread', 'oats', 'quinoa', 'flour', 'tortilla', 'noodles',
               'couscous', 'barley', 'bulgur', 'pita', 'wrap', 'bagel', 'cereal',
               'brown rice', 'white rice', 'whole wheat', 'panko', 'breadcrumbs'},
    'pantry': {'olive oil', 'vegetable oil', 'coconut oil', 'soy sauce', 'vinegar',
               'honey', 'maple syrup', 'sugar', 'salt', 'pepper', 'cumin', 'paprika',
               'oregano', 'thyme', 'cinnamon', 'nutmeg', 'chili powder', 'turmeric',
               'cayenne', 'garlic powder', 'onion powder', 'mustard', 'ketchup',
               'hot sauce', 'sriracha', 'fish sauce', 'sesame oil', 'tahini',
               'peanut butter', 'almond butter', 'coconut milk', 'stock', 'broth',
               'tomato paste', 'tomato sauce', 'canned tomatoes', 'beans', 'lentils',
               'chickpeas', 'nuts', 'almonds', 'walnuts', 'cashews', 'seeds',
               'chia seeds', 'flax seeds', 'protein powder', 'cornstarch'},
}


def _categorize_ingredient(name):
    """Assign a grocery category to an ingredient name."""
    name_lower = name.lower()
    for category, keywords in _GROCERY_CATEGORIES.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return 'other'


def _normalize_ingredient_name(name):
    """Normalize an ingredient name for deduplication."""
    import re
    name = name.lower().strip()
    # Remove common descriptors
    for word in ('fresh', 'dried', 'chopped', 'diced', 'minced', 'sliced', 'ground',
                 'large', 'small', 'medium', 'organic', 'frozen', 'canned', 'raw',
                 'cooked', 'boneless', 'skinless', 'extra-virgin', 'low-fat', 'whole'):
        name = re.sub(rf'\b{word}\b', '', name)
    return re.sub(r'\s+', ' ', name).strip()


@recipes_bp.route('/grocery-list', methods=['POST'])
def grocery_list():
    """Generate a consolidated grocery list from recipe IDs or a meal plan."""
    data = request.get_json() or {}
    recipe_ids = data.get('recipe_ids', [])
    plan = data.get('plan', [])  # Accept a meal plan structure directly
    pantry = set(item.lower() for item in data.get('pantry', []))

    # Collect recipe IDs from plan if provided
    if plan and not recipe_ids:
        for day in plan:
            for meal in day.get('meals', []):
                rid = meal.get('recipe_id')
                if rid:
                    recipe_ids.append(rid)

    if not recipe_ids:
        return jsonify({'error': 'No recipe IDs provided'}), 400

    # Fetch all recipes
    aggregated = {}  # normalized_name -> {name, grams, amount, category, recipe_names}

    for rid in recipe_ids:
        recipe = get_recipe(rid)
        if not recipe:
            continue

        for ing in recipe.get('ingredients', []):
            if isinstance(ing, dict):
                item_name = ing.get('item', '')
                grams = ing.get('grams', 0) or 0
                amount = ing.get('amount', '')
            elif isinstance(ing, str):
                item_name = ing
                grams = 0
                amount = ''
            else:
                continue

            if not item_name:
                continue

            norm = _normalize_ingredient_name(item_name)
            if not norm:
                continue

            if norm not in aggregated:
                aggregated[norm] = {
                    'name': item_name.strip(),
                    'total_grams': 0,
                    'amounts': [],
                    'category': _categorize_ingredient(item_name),
                    'recipes': [],
                    'in_pantry': any(p in norm for p in pantry) if pantry else False,
                }

            aggregated[norm]['total_grams'] += grams
            if amount:
                aggregated[norm]['amounts'].append(amount)
            aggregated[norm]['recipes'].append(recipe.get('name', f'Recipe #{rid}'))

    # Build final list grouped by category
    items = []
    for _norm, data in aggregated.items():
        # Combine amounts
        combined_amount = ''
        if data['total_grams'] > 0:
            combined_amount = f"{data['total_grams']}g"
        elif data['amounts']:
            combined_amount = ' + '.join(data['amounts'])

        items.append({
            'name': data['name'],
            'amount': combined_amount,
            'category': data['category'],
            'recipe_count': len(data['recipes']),
            'recipes': list(set(data['recipes'])),
            'in_pantry': data['in_pantry'],
        })

    # Sort: by category, then alphabetically
    items.sort(key=lambda x: (x['category'], x['name'].lower()))

    # Group by category
    grouped = {}
    for item in items:
        cat = item['category']
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(item)

    return jsonify({
        'items': items,
        'grouped': grouped,
        'total_items': len(items),
        'pantry_items': sum(1 for i in items if i['in_pantry']),
        'to_buy': sum(1 for i in items if not i['in_pantry']),
    })
