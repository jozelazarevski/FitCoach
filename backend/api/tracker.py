"""Tracker API endpoints — restaurant mode and food logging helpers."""

import logging

from flask import Blueprint, jsonify, request

tracker_bp = Blueprint('tracker', __name__)
logger = logging.getLogger(__name__)


@tracker_bp.route('/restaurant', methods=['POST'])
def restaurant_estimate():
    """Estimate macros for restaurant menu items.

    Accepts: restaurant (name), items (list of dish names),
    remaining_macros (today's remaining budget).
    Returns estimated macros per item + best pick recommendation.
    """
    from backend.llm_client import call_llm_json

    data = request.get_json() or {}
    restaurant = data.get('restaurant', '').strip()
    items = data.get('items', [])
    remaining = data.get('remaining_macros', {})
    goal = data.get('goal', 'maintenance')

    if not items and not restaurant:
        return jsonify({'error': 'Provide restaurant name or menu items'}), 400

    # Build the prompt
    items_str = ''
    if items:
        items_str = '\n'.join(f'- {item}' for item in items[:10])
    else:
        items_str = '(suggest 5 popular macro-friendly options)'

    remaining_str = (
        f"{remaining.get('calories', '?')} cal, "
        f"{remaining.get('protein', '?')}g protein, "
        f"{remaining.get('carbs', '?')}g carbs, "
        f"{remaining.get('fat', '?')}g fat"
    )

    prompt = f"""You are a fitness nutrition expert. Estimate macros for restaurant menu items.

Restaurant: {restaurant or 'Unknown'}
Menu items to estimate:
{items_str}

Client's remaining macros today: {remaining_str}
Client's goal: {goal}

Return ONLY a valid JSON object:
{{
  "restaurant": "{restaurant or 'Unknown'}",
  "estimates": [
    {{
      "name": "Dish name",
      "calories": <integer>,
      "protein": <integer grams>,
      "carbs": <integer grams>,
      "fat": <integer grams>,
      "fiber": <integer grams>,
      "portion_note": "Standard portion size assumption",
      "macro_fit_score": <1-10, how well it fits remaining macros>,
      "tip": "One sentence modification tip to improve macros"
    }}
  ],
  "best_pick": {{
    "name": "Best dish name",
    "reason": "Why this is the best choice for the client's remaining macros and goal"
  }},
  "general_tips": ["Tip for eating at this type of restaurant"]
}}

Rules:
- Estimate realistic portion sizes for restaurant servings (typically larger than home-cooked)
- protein*4 + carbs*4 + fat*9 must be within 15% of stated calories
- macro_fit_score considers how well the dish fits remaining macros and goal
- Best pick should minimize excess calories while maximizing protein for the goal
- Include practical modification tips (e.g., "ask for sauce on the side")"""

    try:
        result = call_llm_json(prompt, max_tokens=3000)
        if isinstance(result, dict) and 'estimates' in result:
            return jsonify(result)
        return jsonify({'error': 'Invalid LLM response format'}), 500
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        logger.error('Restaurant estimate failed: %s', e, exc_info=True)
        return jsonify({'error': f'Estimation failed: {e}'}), 500


# Built-in common restaurant macro database for offline/free estimates
_COMMON_DISHES = {
    'grilled chicken breast': {'calories': 350, 'protein': 45, 'carbs': 5, 'fat': 12},
    'chicken caesar salad': {'calories': 550, 'protein': 38, 'carbs': 20, 'fat': 35},
    'grilled salmon': {'calories': 450, 'protein': 42, 'carbs': 8, 'fat': 25},
    'steak and vegetables': {'calories': 600, 'protein': 50, 'carbs': 15, 'fat': 35},
    'chicken burrito bowl': {'calories': 650, 'protein': 40, 'carbs': 65, 'fat': 22},
    'turkey sandwich': {'calories': 450, 'protein': 30, 'carbs': 40, 'fat': 18},
    'grilled chicken sandwich': {'calories': 500, 'protein': 35, 'carbs': 42, 'fat': 20},
    'fish tacos': {'calories': 480, 'protein': 28, 'carbs': 45, 'fat': 20},
    'margherita pizza slice': {'calories': 280, 'protein': 12, 'carbs': 30, 'fat': 12},
    'greek salad': {'calories': 320, 'protein': 12, 'carbs': 15, 'fat': 24},
    'pad thai': {'calories': 550, 'protein': 22, 'carbs': 65, 'fat': 20},
    'chicken stir fry': {'calories': 450, 'protein': 35, 'carbs': 35, 'fat': 18},
    'burger and fries': {'calories': 900, 'protein': 35, 'carbs': 75, 'fat': 50},
    'pasta bolognese': {'calories': 650, 'protein': 28, 'carbs': 70, 'fat': 28},
    'sushi roll (6 pcs)': {'calories': 350, 'protein': 18, 'carbs': 45, 'fat': 10},
    'poke bowl': {'calories': 500, 'protein': 35, 'carbs': 55, 'fat': 15},
    'chicken wings (8 pcs)': {'calories': 700, 'protein': 45, 'carbs': 10, 'fat': 50},
    'protein shake': {'calories': 250, 'protein': 30, 'carbs': 20, 'fat': 5},
    'acai bowl': {'calories': 450, 'protein': 8, 'carbs': 70, 'fat': 15},
    'egg white omelette': {'calories': 250, 'protein': 30, 'carbs': 5, 'fat': 10},
}


@tracker_bp.route('/restaurant-quick', methods=['POST'])
def restaurant_quick_estimate():
    """Quick macro estimate from built-in database (no LLM needed).

    Fuzzy-matches dish names against common restaurant items.
    Falls back to per-100g estimates for unknown items.
    """
    data = request.get_json() or {}
    items = data.get('items', [])
    remaining = data.get('remaining_macros', {})

    if not items:
        return jsonify({'error': 'Provide menu items to estimate'}), 400

    estimates = []
    for item_name in items[:10]:
        name_lower = item_name.lower().strip()

        # Try exact or fuzzy match
        match = None
        for dish, macros in _COMMON_DISHES.items():
            if dish in name_lower or name_lower in dish:
                match = {'name': item_name, **macros, 'source': 'database', 'matched': dish}
                break

        if not match:
            # Check for keywords
            for dish, macros in _COMMON_DISHES.items():
                keywords = dish.split()
                if sum(1 for k in keywords if k in name_lower) >= len(keywords) * 0.5:
                    match = {'name': item_name, **macros, 'source': 'database', 'matched': dish}
                    break

        if not match:
            # Generic estimate based on meal type keywords
            if any(w in name_lower for w in ('salad', 'greens')):
                match = {'name': item_name, 'calories': 350, 'protein': 15, 'carbs': 20, 'fat': 22, 'source': 'estimate'}
            elif any(w in name_lower for w in ('burger', 'pizza', 'fries', 'fried')):
                match = {'name': item_name, 'calories': 700, 'protein': 25, 'carbs': 60, 'fat': 40, 'source': 'estimate'}
            elif any(w in name_lower for w in ('chicken', 'turkey', 'grilled')):
                match = {'name': item_name, 'calories': 450, 'protein': 38, 'carbs': 20, 'fat': 18, 'source': 'estimate'}
            elif any(w in name_lower for w in ('fish', 'salmon', 'tuna', 'shrimp')):
                match = {'name': item_name, 'calories': 400, 'protein': 35, 'carbs': 15, 'fat': 18, 'source': 'estimate'}
            elif any(w in name_lower for w in ('pasta', 'rice', 'noodle')):
                match = {'name': item_name, 'calories': 550, 'protein': 20, 'carbs': 65, 'fat': 18, 'source': 'estimate'}
            else:
                match = {'name': item_name, 'calories': 500, 'protein': 25, 'carbs': 45, 'fat': 22, 'source': 'fallback'}

        # Compute macro fit score
        if remaining.get('calories'):
            cal_fit = max(0, 10 - abs(match['calories'] - remaining.get('calories', 500)) / 100)
            prot_bonus = min(match.get('protein', 0) / max(remaining.get('protein', 40), 1) * 3, 3)
            match['macro_fit_score'] = round(min(cal_fit + prot_bonus, 10), 1)
        else:
            match['macro_fit_score'] = 5

        estimates.append(match)

    # Best pick
    best = max(estimates, key=lambda e: e.get('macro_fit_score', 0))

    return jsonify({
        'estimates': estimates,
        'best_pick': {
            'name': best['name'],
            'reason': f"Best macro fit with {best.get('macro_fit_score', 0)}/10 score",
        },
    })
