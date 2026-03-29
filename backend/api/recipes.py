from flask import Blueprint, request, jsonify
from backend.models import get_recipe, search_recipes, suggest_recipes

recipes_bp = Blueprint('recipes', __name__)


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


@recipes_bp.route('/meal-plan', methods=['POST'])
def meal_plan():
    """Generate a 7-day meal plan from DB recipes."""
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

    for day in days:
        meals = []
        for slot in meal_slots:
            # Each meal targets ~25-30% of daily macros (snack gets less)
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
            results = suggest_recipes(context, limit=5)
            # Pick one not already used
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
