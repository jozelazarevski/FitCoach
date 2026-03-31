"""Tests for backend.validation — Pydantic model validation."""

from backend.validation import (
    validate_generated_recipe,
    validate_meal_plan,
    validate_suggestion_response,
)


# --- validate_suggestion_response ---

def test_validate_suggestion_valid():
    """Valid suggestion response should return a SuggestLLMResponse."""
    data = {
        "top_pick_reason": "Great for muscle building",
        "suggestions": [
            {
                "name": "Grilled Chicken",
                "calories": 400,
                "protein": 35,
                "carbs": 30,
                "fat": 12,
            }
        ],
    }
    result = validate_suggestion_response(data)
    assert result is not None
    assert len(result.suggestions) == 1
    assert result.suggestions[0].name == "Grilled Chicken"


def test_validate_suggestion_invalid_returns_none():
    """Invalid data (missing required fields) should return None."""
    # Empty suggestions list violates min_length=1
    result = validate_suggestion_response({"suggestions": []})
    assert result is None

    # Completely wrong structure
    result = validate_suggestion_response({"bad": "data"})
    assert result is None


def test_validate_suggestion_missing_optional_fields():
    """Optional fields should get defaults."""
    data = {
        "suggestions": [
            {"name": "Salad", "calories": 200, "protein": 10, "carbs": 20, "fat": 8}
        ]
    }
    result = validate_suggestion_response(data)
    assert result is not None
    assert result.top_pick_reason == ""
    assert result.suggestions[0].cuisine == "International"


# --- validate_generated_recipe ---

def test_validate_generated_recipe_valid():
    """Valid generated recipe should return a GeneratedRecipe."""
    data = {
        "name": "Protein Pancakes",
        "ingredients": ["oats", "eggs", "banana"],
        "steps": ["Mix ingredients.", "Cook on griddle."],
        "calories": 350,
        "protein": 25,
        "carbs": 40,
        "fat": 8,
    }
    result = validate_generated_recipe(data)
    assert result is not None
    assert result.name == "Protein Pancakes"
    assert len(result.ingredients) == 3


def test_validate_generated_recipe_invalid():
    """Missing required fields should return None."""
    # No ingredients
    result = validate_generated_recipe(
        {"name": "Bad", "ingredients": [], "steps": ["x"], "calories": 100,
         "protein": 10, "carbs": 10, "fat": 5}
    )
    assert result is None

    # No steps
    result = validate_generated_recipe(
        {"name": "Bad", "ingredients": ["x"], "steps": [], "calories": 100,
         "protein": 10, "carbs": 10, "fat": 5}
    )
    assert result is None


def test_validate_generated_recipe_out_of_range():
    """Out-of-range values should return None."""
    result = validate_generated_recipe(
        {"name": "Bad", "ingredients": ["x"], "steps": ["x"],
         "calories": -10, "protein": 10, "carbs": 10, "fat": 5}
    )
    assert result is None


# --- validate_meal_plan ---

def test_validate_meal_plan_valid():
    """Valid meal plan should return a MealPlanResponse."""
    data = {
        "plan": [
            {
                "day": "Monday",
                "meals": [
                    {
                        "type": "breakfast",
                        "name": "Oatmeal",
                        "calories": 300,
                        "protein": 10,
                        "carbs": 50,
                        "fat": 8,
                    },
                    {
                        "type": "lunch",
                        "name": "Chicken Salad",
                        "calories": 450,
                        "protein": 35,
                        "carbs": 25,
                        "fat": 20,
                    },
                ],
            }
        ]
    }
    result = validate_meal_plan(data)
    assert result is not None
    assert len(result.plan) == 1
    assert result.plan[0].day == "Monday"
    assert len(result.plan[0].meals) == 2


def test_validate_meal_plan_invalid():
    """Invalid meal plan should return None."""
    # Empty plan
    result = validate_meal_plan({"plan": []})
    assert result is None

    # Missing meals
    result = validate_meal_plan({"plan": [{"day": "Monday", "meals": []}]})
    assert result is None

    # Wrong structure entirely
    result = validate_meal_plan({"not_a_plan": True})
    assert result is None
