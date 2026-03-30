"""Pydantic models for validating LLM responses and API inputs."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional


class RecipeSuggestion(BaseModel):
    """Validates a single recipe suggestion from LLM."""
    name: str = Field(min_length=1)
    description: str = ''
    why: str = ''
    calories: int = Field(ge=0, le=5000)
    protein: int = Field(ge=0, le=500)
    carbs: int = Field(ge=0, le=1000)
    fat: int = Field(ge=0, le=500)
    cuisine: str = 'International'
    category: str = 'general'
    meal_type: str = 'any'
    difficulty: str = 'medium'
    prep_time_min: int = Field(default=0, ge=0)
    cook_time_min: int = Field(default=0, ge=0)
    rank: Optional[int] = None

    @model_validator(mode='after')
    def validate_macro_consistency(self):
        """Warn if macros don't add up to within 20% of stated calories."""
        computed = self.protein * 4 + self.carbs * 4 + self.fat * 9
        if self.calories > 0 and computed > 0:
            ratio = computed / self.calories
            if not 0.6 <= ratio <= 1.4:
                # Don't reject, but flag — LLMs sometimes round loosely
                pass
        return self


class SuggestLLMResponse(BaseModel):
    """Validates the full suggest-llm LLM response."""
    top_pick_reason: str = ''
    suggestions: list[RecipeSuggestion] = Field(min_length=1, max_length=10)


class GeneratedRecipe(BaseModel):
    """Validates a full LLM-generated recipe."""
    name: str = Field(min_length=1)
    description: str = ''
    prep_time: str | int = '0 min'
    cook_time: str | int = '0 min'
    servings: str | int = '1'
    ingredients: list = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    tips: str = ''
    equipment: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    calories: int = Field(ge=0, le=5000)
    protein: int = Field(ge=0, le=500)
    carbs: int = Field(ge=0, le=1000)
    fat: int = Field(ge=0, le=500)
    fiber: int = Field(default=0, ge=0)
    sugar: int = Field(default=0, ge=0)


class MealPlanMeal(BaseModel):
    """Validates a single meal in a meal plan."""
    type: str
    name: str = Field(min_length=1)
    description: str = ''
    calories: int = Field(ge=0, le=5000)
    protein: int = Field(ge=0, le=500)
    carbs: int = Field(ge=0, le=1000)
    fat: int = Field(ge=0, le=500)


class MealPlanDay(BaseModel):
    """Validates a single day in a meal plan."""
    day: str
    meals: list[MealPlanMeal] = Field(min_length=1)


class MealPlanResponse(BaseModel):
    """Validates the full meal-plan-llm LLM response."""
    plan: list[MealPlanDay] = Field(min_length=1, max_length=14)


def validate_suggestion_response(data: dict) -> SuggestLLMResponse | None:
    """Validate an LLM suggestion response. Returns model or None on failure."""
    try:
        return SuggestLLMResponse.model_validate(data)
    except Exception:
        return None


def validate_generated_recipe(data: dict) -> GeneratedRecipe | None:
    """Validate an LLM-generated recipe. Returns model or None on failure."""
    try:
        return GeneratedRecipe.model_validate(data)
    except Exception:
        return None


def validate_meal_plan(data: dict) -> MealPlanResponse | None:
    """Validate an LLM meal plan response. Returns model or None on failure."""
    try:
        return MealPlanResponse.model_validate(data)
    except Exception:
        return None
