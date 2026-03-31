"""Tests for backend.tag_engine — cuisine detection and deterministic tags."""

from backend.tag_engine import compute_deterministic_tags, detect_cuisine


def test_detect_cuisine_thai():
    """Recipe with 'Thai' in name should be detected as Thai cuisine."""
    recipe = {"name": "Thai Basil Chicken", "ingredients": [], "category": "chicken"}
    result = detect_cuisine(recipe)
    assert result["cuisine"] == "Thai"
    assert result["country"] == "Thailand"


def test_detect_cuisine_italian_keyword():
    """Recipe with Italian keyword in name should be detected."""
    recipe = {"name": "Classic Risotto", "ingredients": [], "category": "general"}
    result = detect_cuisine(recipe)
    assert result["cuisine"] == "Italian"


def test_detect_cuisine_from_ingredients():
    """Cuisine detection via ingredient keywords when name has no match."""
    recipe = {
        "name": "Spicy Bowl",
        "ingredients": [{"item": "gochujang", "grams": 30}],
        "category": "general",
    }
    result = detect_cuisine(recipe)
    assert result["cuisine"] == "Korean"


def test_detect_cuisine_default():
    """No matching keywords returns International."""
    recipe = {"name": "Plain Salad", "ingredients": ["lettuce"], "category": "general"}
    result = detect_cuisine(recipe)
    assert result["cuisine"] == "International"


def test_deterministic_tags_macro_profile_high_protein():
    """High-protein recipe should get high_protein macro_profile tag."""
    recipe = {
        "name": "Grilled Chicken",
        "calories": 400,
        "protein": 45,
        "carbs": 20,
        "fat": 12,
        "fiber": 3,
        "sugar": 2,
        "total_time_min": 25,
        "prep_time_min": 10,
        "cook_time_min": 15,
        "servings": 1,
        "ingredients": [{"item": "chicken breast", "grams": 200}],
        "category": "chicken",
        "meal_type": "lunch",
    }
    tags = compute_deterministic_tags(recipe)
    assert "macro_profile" in tags
    assert "high_protein" in tags["macro_profile"]
    assert "very_high_protein" in tags["macro_profile"]


def test_deterministic_tags_timing():
    """Timing tags should reflect total_time_min."""
    recipe = {
        "name": "Quick Snack",
        "calories": 200,
        "protein": 10,
        "carbs": 20,
        "fat": 8,
        "total_time_min": 8,
        "prep_time_min": 5,
        "cook_time_min": 3,
        "servings": 1,
        "ingredients": ["apple", "peanut butter"],
        "category": "snack",
        "meal_type": "snack",
    }
    tags = compute_deterministic_tags(recipe)
    assert "timing" in tags
    assert "under_10_min" in tags["timing"]
    assert "under_15_min" in tags["timing"]


def test_deterministic_tags_calorie_bracket():
    """Calorie brackets should be tagged correctly."""
    recipe = {
        "name": "Light Salad",
        "calories": 250,
        "protein": 15,
        "carbs": 20,
        "fat": 10,
        "total_time_min": 10,
        "prep_time_min": 10,
        "cook_time_min": 0,
        "servings": 1,
        "ingredients": ["lettuce", "tomato"],
        "category": "salad",
        "meal_type": "lunch",
    }
    tags = compute_deterministic_tags(recipe)
    assert "calorie_bracket" in tags
    # calorie_bracket is a string like "200_to_300"
    bracket = tags["calorie_bracket"]
    assert "200" in bracket or "250" in bracket or "300" in bracket
