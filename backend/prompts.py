"""Prompt versioning system for LLM prompts.

All prompts used by the application are centralized here with version tracking.
This enables A/B testing, rollback, and audit trails for prompt changes.
"""

PROMPT_VERSION = '1.0.0'

SUGGEST_RECIPES = {
    'version': '1.0.0',
    'template': """You are an elite fitness nutrition coach. Suggest exactly 5 meal recipes for a client.

Context:
- Meal type: {meal_types}
- Goal: {goal}
- Remaining macros today: {remaining_calories} cal, {remaining_protein}g protein, {remaining_carbs}g carbs, {remaining_fat}g fat
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
      "meal_type": "{first_meal_type}",
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
- For {goal}: {goal_guidance}""",
}

GENERATE_RECIPE = {
    'version': '1.0.0',
    'template': """Generate a complete recipe for: "{name}"

Target macros per serving: {calories} cal, {protein}g protein, {carbs}g carbs, {fat}g fat
{cuisine_line}
{category_line}
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
- Macros must be realistic for the ingredients listed""",
}

MEAL_PLAN = {
    'version': '1.0.0',
    'template': """Create a 7-day meal plan for a fitness-focused client.

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
- Make meals practical and appetizing""",
}


def get_goal_guidance(goal):
    """Return macro guidance string for a given fitness goal."""
    if goal in ('fat_loss', 'cutting'):
        return 'high protein, low cal'
    elif goal in ('bulking', 'muscle_building'):
        return 'high protein, high carbs'
    return 'balanced macros'


def render_suggest_prompt(*, meal_types, goal, remaining, diet_filters, liked, disliked, hour):
    """Render the suggest-llm prompt from versioned template."""
    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'
    liked_str = ', '.join(liked[:5]) if liked else 'none'
    disliked_str = ', '.join(disliked[:5]) if disliked else 'none'

    return SUGGEST_RECIPES['template'].format(
        meal_types=', '.join(meal_types),
        goal=goal,
        remaining_calories=remaining.get('calories', 2000),
        remaining_protein=remaining.get('protein', 40),
        remaining_carbs=remaining.get('carbs', 50),
        remaining_fat=remaining.get('fat', 20),
        diet_str=diet_str,
        liked_str=liked_str,
        disliked_str=disliked_str,
        hour=hour,
        first_meal_type=meal_types[0] if meal_types else 'dinner',
        goal_guidance=get_goal_guidance(goal),
    )


def render_generate_prompt(*, name, calories, protein, carbs, fat, cuisine='', category='', diet_filters=None):
    """Render the generate-llm prompt from versioned template."""
    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'

    return GENERATE_RECIPE['template'].format(
        name=name,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        cuisine_line=f'Cuisine: {cuisine}' if cuisine else '',
        category_line=f'Category: {category}' if category else '',
        diet_str=diet_str,
    )


def render_meal_plan_prompt(*, goal, target_cal, target_prot, diet_filters=None):
    """Render the meal-plan-llm prompt from versioned template."""
    diet_str = ', '.join(diet_filters) if diet_filters else 'no restrictions'

    return MEAL_PLAN['template'].format(
        goal=goal,
        target_cal=target_cal,
        target_prot=target_prot,
        diet_str=diet_str,
    )
