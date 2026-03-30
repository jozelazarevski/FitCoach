import json
from flask import Blueprint, request, jsonify
from backend.models import get_recipe, search_recipes, suggest_recipes, recipe_to_dict

recipes_bp = Blueprint('recipes', __name__)


@recipes_bp.route('/suggest-llm', methods=['POST'])
def suggest_llm():
    """Generate recipe suggestions via LLM when DB is empty or insufficient."""
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
            # Add source marker
            for s in result['suggestions']:
                s['source'] = 'llm'
            return jsonify(result)
        return jsonify({'error': 'Invalid LLM response format'}), 500
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'LLM generation failed: {e}'}), 500


@recipes_bp.route('/generate-llm', methods=['POST'])
def generate_recipe_llm():
    """Generate a full recipe via LLM for a given suggestion."""
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

    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'

    prompt = f"""Generate a complete recipe for: "{name}"

Target macros per serving: {calories} cal, {protein}g protein, {carbs}g carbs, {fat}g fat
{f"Cuisine: {cuisine}" if cuisine else ""}
{f"Category: {category}" if category else ""}
Diet restrictions: {diet_str}

Return ONLY a valid JSON object:
{{
  "name": "{name}",
  "prep_time": "X min",
  "cook_time": "X min",
  "servings": "X",
  "ingredients": ["200g chicken breast", "1 cup rice", ...],
  "steps": ["Step 1...", "Step 2...", ...],
  "tips": "One fitness coaching tip about this meal",
  "calories": {calories},
  "protein": {protein},
  "carbs": {carbs},
  "fat": {fat}
}}

Rules:
- Include exact measurements for all ingredients
- 6-12 ingredients, 4-8 clear steps
- Make it practical, delicious, and achievable for a home cook
- The tip should relate to fitness/nutrition timing/benefits
- Macros must be realistic for the ingredients listed"""

    try:
        result = call_llm_json(prompt, max_tokens=3000)
        if isinstance(result, dict) and 'ingredients' in result:
            # Ensure ingredients are strings for frontend rendering
            result['ingredients'] = [
                f"{ing['amount']} {ing['item']}" if isinstance(ing, dict) else str(ing)
                for ing in result['ingredients']
            ]
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
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 100)

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
