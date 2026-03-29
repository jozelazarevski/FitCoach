"""
Recipe Generator - Batch generates 5000+ recipes using Claude API.
Stores in SQLite with full tagging. Resumable via generation_queue.

Usage:
    python -m backend.recipe_generator [--batch-size 10] [--resume BATCH_ID]
"""

import json
import time
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ANTHROPIC_API_KEY, RECIPES_PER_API_CALL, MAX_RETRIES, OLLAMA_BASE_URL, OLLAMA_MODEL
from backend.db import get_db, use_db, init_db
from backend.models import insert_recipe
from backend.tag_engine import detect_cuisine, compute_tags, compute_deterministic_tags

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import requests as _requests
except ImportError:
    _requests = None

# Recipe generation matrix
CUISINES = [
    "Italian", "Mexican", "Thai", "Japanese", "Indian", "Greek", "Mediterranean",
    "Korean", "Chinese", "Vietnamese", "Middle Eastern", "Moroccan", "French",
    "American", "Caribbean", "Ethiopian", "Peruvian", "Brazilian", "Turkish",
    "Spanish"
]

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "pre_workout", "post_workout"]

CATEGORIES = [
    "poultry", "red_meat", "fish", "seafood", "vegan", "vegetarian"
]

GOALS = [
    "fat_loss", "muscle_building", "maintenance", "bulking", "cutting", "endurance"
]

DIFFICULTIES = ["easy", "medium", "hard"]

PROMPT_TEMPLATE = """Generate exactly {count} unique {cuisine} {category} recipes suitable for {meal_type}.
Each recipe should align with a {goal} nutritional goal and be {difficulty} difficulty.

Return ONLY a valid JSON array. Each recipe object must have these exact fields:
{{
  "name": "Descriptive recipe name mentioning the cuisine style",
  "description": "One sentence describing the dish",
  "category": "{category}",
  "meal_type": "{meal_type}",
  "difficulty": "{difficulty}",
  "prep_time_min": <integer minutes>,
  "cook_time_min": <integer minutes>,
  "total_time_min": <integer total minutes>,
  "servings": <integer 1-6>,
  "calories": <integer per serving>,
  "protein": <integer grams per serving>,
  "carbs": <integer grams per serving>,
  "fat": <integer grams per serving>,
  "fiber": <integer grams per serving>,
  "sugar": <integer grams per serving>,
  "ingredients": [
    {{"item": "ingredient name", "amount": "200g", "grams": 200}},
    ...
  ],
  "steps": ["Step 1...", "Step 2...", ...],
  "tips": "One fitness coaching tip about this meal",
  "equipment": ["pan", "oven", ...],
  "allergens": ["dairy", "gluten", ...],
  "diet": ["high_protein", ...],
  "meal_prep_friendly": true/false,
  "tags": {{
    "goal": ["fat_loss", "cutting", ...],
    "cooking_style": ["grilling", "one_pan", ...],
    "lifestyle": ["weeknight_quick", "meal_prep", ...],
    "micronutrients": ["iron_rich", "omega_3_rich", ...],
    "health": ["heart_healthy", "anti_inflammatory", ...],
    "dietary": ["gluten_free", "dairy_free", "paleo", ...],
    "satiety": ["high_satiety", "slow_digesting", ...],
    "texture_experience": ["spicy", "creamy", "umami", ...],
    "protein_source": ["poultry_protein", "plant_protein", ...],
    "seasonal": ["summer", "winter", "year_round", ...],
    "coaching": ["beginner_cook", "plateau_breaker", ...]
  }}
}}

Tag value reference (pick ALL that apply for each recipe):
- goal: cutting, fat_loss, bulking, lean_bulk, maintenance, recomp, pre_workout, post_workout, muscle_building, endurance_fuel, competition_prep, off_season, aggressive_bulk, reverse_diet
- cooking_style: one_pan, wok_cooking, grilling, oven_baking, dutch_oven, sheet_pan, batch_cook, meal_prep, raw, slow_cooked, grilled, baked, roasted, steamed, poached, braised, seared, pan_seared, stir_fried, blackened, smoked, air_fried, broiled, crusted
- lifestyle: weeknight_quick, weekend_project, office_lunch, freezer_friendly, leftover_friendly, solo_cooking, family_friendly, party_batch, date_night, desk_meal, travel_friendly
- micronutrients: iron_rich, omega_3_rich, calcium_rich, vitamin_c_rich, zinc_rich, magnesium_rich, b_vitamin_rich, vitamin_a_rich, potassium_rich, antioxidant_rich, probiotic, prebiotic, collagen_source
- health: heart_healthy, blood_sugar_friendly, bone_health, brain_food, immune_boosting, recovery_focused, anti_inflammatory, gut_friendly, skin_health, hydrating, electrolyte_rich, low_cholesterol
- dietary: vegan, vegetarian, gluten_free, dairy_free, soy_free, nut_free, egg_free, seafood_free, sesame_free, paleo, whole30_compliant, pescatarian, mediterranean_diet, refined_sugar_free, carnivore_friendly, keto, low_carb, high_protein
- satiety: high_satiety, very_filling, slow_digesting, fast_digesting, blood_sugar_stable, light_and_satisfying
- texture_experience: crunchy, creamy, hearty, light, warming, refreshing, spicy, mild, umami, tangy, sweet, crispy
- protein_source: poultry_protein, red_meat_protein, fish_protein, shellfish_protein, animal_protein, plant_protein, egg_protein, dairy_protein, supplement_protein, complete_protein, omega_3_protein, lean_protein
- seasonal: spring, summer, autumn, winter, soup_season, bbq_season, year_round
- coaching: beginner_cook, simple_ingredients, complex_recipe, intro_to_cooking, first_meal_prep, plateau_breaker, metabolic_boost, sleep_friendly, morning_energy, afternoon_slump_buster, evening_wind_down, hangover_recovery, sick_day_comfort, stress_eating_redirect, snack_replacement

Rules:
- CRITICAL: Macro math must be consistent. protein*4 + carbs*4 + fat*9 must be within 10% of stated calories
- {goal_guidance}
- Every ingredient must have exact gram measurements in the "grams" field (integer)
- Include 6-15 ingredients per recipe
- Allergens from: gluten, dairy, egg, soy, tree_nuts, peanuts, fish, shellfish, sesame
- Diet tags from: vegan, vegetarian, high_protein, low_carb, keto, paleo, gluten_free, dairy_free
- Equipment examples: pan, oven, grill, wok, blender, sheet pan, dutch oven, pot
- Make recipes practical and delicious with real cooking techniques
- VARY the recipes - different proteins, vegetables, cooking methods, flavor profiles
- Names should be appetizing and specific (not generic like "Chicken Dish #3")
- Tags MUST be accurate. Only include tags that truly apply based on the recipe's ingredients, macros, and characteristics
- For {category}: {category_instruction}
- Return ONLY the JSON array, no markdown fences or explanation"""

GOAL_GUIDANCE = {
    "fat_loss": "Calories 300-500, protein 25-45g, moderate carbs, low fat. Focus on lean proteins and vegetables",
    "muscle_building": "Calories 400-700, protein 35-55g, moderate-high carbs. Focus on complete proteins",
    "maintenance": "Calories 400-600, protein 25-40g, balanced macros. Focus on variety and nutrients",
    "bulking": "Calories 500-800, protein 30-50g, high carbs. Include calorie-dense whole foods",
    "cutting": "Calories 250-450, protein 30-50g, very low fat, moderate carbs. Maximum protein density",
    "endurance": "Calories 400-650, protein 20-35g, high carbs 50-80g. Focus on sustained energy"
}


def build_generation_plan(batch_size=RECIPES_PER_API_CALL):
    """Build the full matrix of prompt combinations for 5000+ recipes."""
    plan = []

    # Define which categories are valid for each diet type
    ANIMAL_CATEGORIES = {"poultry", "red_meat", "fish", "seafood"}
    PLANT_CATEGORIES = {"vegan", "vegetarian"}

    for cuisine in CUISINES:
        for meal_type in MEAL_TYPES:
            for category in CATEGORIES:
                for goal in GOALS:
                    # Skip impossible combos
                    # Vegan/vegetarian can't be animal protein categories
                    if category in PLANT_CATEGORIES and False:
                        pass  # category IS the diet, no conflict
                    # Fish/seafood for breakfast only in Japanese cuisine
                    if category in ("fish", "seafood") and meal_type == "breakfast" and cuisine not in ("Japanese",):
                        continue
                    # Red meat breakfast only in American/Brazilian/Turkish
                    if category == "red_meat" and meal_type == "breakfast" and cuisine not in ("American", "Brazilian", "Turkish"):
                        continue
                    # Snack + endurance doesn't make sense
                    if meal_type == "snack" and goal == "endurance":
                        continue
                    # Vegan + bulking/aggressive bulk is uncommon but valid; skip cutting snacks
                    if category == "vegan" and goal == "cutting" and meal_type == "snack":
                        continue
                    # Skip some low-value combos to reduce from ~4000 to ~3000 prompts
                    # Not every cuisine has seafood dishes
                    if category == "seafood" and cuisine in ("Ethiopian", "Peruvian", "Turkish"):
                        continue

                    difficulty = DIFFICULTIES[len(plan) % 3]
                    prompt_key = f"{cuisine}_{meal_type}_{category}_{goal}_{difficulty}"
                    plan.append({
                        "prompt_key": prompt_key,
                        "cuisine": cuisine,
                        "meal_type": meal_type,
                        "category": category,
                        "goal": goal,
                        "difficulty": difficulty,
                        "count": batch_size
                    })

    return plan


def create_batch(plan, batch_id=None):
    """Create a generation batch in the database."""
    if not batch_id:
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"

    total = sum(p["count"] for p in plan)
    with use_db() as db:
        db.execute("""
            INSERT OR IGNORE INTO generation_jobs (batch_id, total_planned, status, parameters)
            VALUES (?, ?, 'running', ?)
        """, (batch_id, total, json.dumps({"recipes_per_call": plan[0]["count"] if plan else 10})))

        for item in plan:
            db.execute("""
                INSERT OR IGNORE INTO generation_queue (batch_id, prompt_key, status)
                VALUES (?, ?, 'pending')
            """, (batch_id, item["prompt_key"]))

        db.commit()
    return batch_id


def _build_prompt(prompt_info):
    """Build the generation prompt from prompt_info dict."""
    goal_guide = GOAL_GUIDANCE.get(prompt_info["goal"], "Balanced macros")
    cat = prompt_info["category"]
    if cat == "vegan":
        cat_instruction = "use ONLY plant-based ingredients, no animal products"
    elif cat == "vegetarian":
        cat_instruction = "use ONLY vegetarian ingredients, no meat/fish"
    else:
        cat_instruction = f"feature {cat} as the main protein"
    return PROMPT_TEMPLATE.format(
        count=prompt_info["count"],
        cuisine=prompt_info["cuisine"],
        category=prompt_info["category"],
        meal_type=prompt_info["meal_type"],
        goal=prompt_info["goal"],
        difficulty=prompt_info["difficulty"],
        goal_guidance=goal_guide,
        category_instruction=cat_instruction
    )


def _extract_json(text):
    """Extract JSON array from LLM response text."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    # Try to find JSON array if there's surrounding text
    if not text.startswith("["):
        start = text.find("[")
        if start != -1:
            text = text[start:]
    if not text.endswith("]"):
        end = text.rfind("]")
        if end != -1:
            text = text[:end + 1]
    recipes = json.loads(text)
    if not isinstance(recipes, list):
        recipes = [recipes]
    return recipes


def generate_recipes_batch(client, prompt_info, model=None):
    """Call Claude API to generate a batch of recipes."""
    prompt = _build_prompt(prompt_info)

    response = client.messages.create(
        model=model or "claude-haiku-4-5-20251001",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    return _extract_json(text)


def generate_recipes_batch_ollama(base_url, model, prompt_info):
    """Call Ollama API to generate a batch of recipes."""
    if not _requests:
        raise ImportError("pip install requests  (needed for Ollama)")

    prompt = _build_prompt(prompt_info)

    resp = _requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 16000,
                "temperature": 0.7,
            }
        },
        timeout=300
    )
    resp.raise_for_status()
    text = resp.json().get("response", "")
    return _extract_json(text)


def _merge_tags(llm_tags, deterministic_tags):
    """Merge LLM-generated tags with deterministic math-based tags.

    Deterministic tags (brackets, timing, macro_profile, etc.) always win
    since they're computed from exact numbers. LLM tags are used for
    knowledge-based dimensions (micronutrients, health, texture, etc.).
    """
    merged = {}
    # Start with LLM tags
    for dim, values in llm_tags.items():
        if isinstance(values, list):
            merged[dim] = list(values)
        else:
            merged[dim] = values
    # Deterministic tags overwrite (they're always correct)
    for dim, values in deterministic_tags.items():
        merged[dim] = values
    return merged


def process_and_store(recipes_raw, prompt_info, batch_id):
    """Process raw recipe data, merge LLM + deterministic tags, store atomically."""
    stored_ids = []
    for recipe_data in recipes_raw:
        # Ensure required fields
        recipe_data.setdefault("category", prompt_info["category"])
        recipe_data.setdefault("meal_type", prompt_info["meal_type"])
        recipe_data.setdefault("difficulty", prompt_info["difficulty"])
        recipe_data["source"] = "generated"
        recipe_data["generation_batch"] = batch_id

        # Detect cuisine
        cuisine_info = detect_cuisine(recipe_data)
        recipe_data["cuisine"] = cuisine_info["cuisine"]
        recipe_data["country_of_origin"] = cuisine_info["country"]
        recipe_data["region"] = cuisine_info["region"]

        # Ensure numeric fields
        for field in ("calories", "protein", "carbs", "fat", "fiber", "sugar",
                      "prep_time_min", "cook_time_min", "total_time_min", "servings"):
            recipe_data[field] = int(recipe_data.get(field, 0) or 0)

        if recipe_data["total_time_min"] == 0:
            recipe_data["total_time_min"] = recipe_data["prep_time_min"] + recipe_data["cook_time_min"]

        # Build tags: LLM-generated + deterministic supplement
        llm_tags = recipe_data.pop("tags", None) or {}
        if llm_tags:
            # LLM provided tags — supplement with deterministic math-based tags
            det_tags = compute_deterministic_tags(recipe_data)
            tags = _merge_tags(llm_tags, det_tags)
        else:
            # Fallback: no LLM tags (older prompt or parse failure) — use full tag engine
            tags = compute_tags(recipe_data)

        # Atomic insert: recipe + tags in one transaction
        recipe_id = insert_recipe(recipe_data, tags_dict=tags)
        stored_ids.append(recipe_id)

    return stored_ids


def run_generation(batch_id=None, batch_size=RECIPES_PER_API_CALL, max_items=None, provider=None, model=None):
    """Main generation loop. Resumable via batch_id.

    Args:
        provider: 'anthropic' (default) or 'ollama'
        model: model name override (e.g. 'claude-sonnet-4-6', 'llama3.1')
    """
    init_db()

    from backend.api.admin import get_active_api_key

    # Determine provider
    if not provider:
        # Check if ollama key/config exists in DB, else default to anthropic
        ollama_data = get_active_api_key('ollama')
        if ollama_data:
            provider = 'ollama'
        else:
            provider = 'anthropic'

    client = None
    ollama_url = None
    ollama_model = None
    claude_model = None

    if provider == 'ollama':
        if not _requests:
            print("ERROR: pip install requests  (needed for Ollama)")
            return
        # Get Ollama config from DB or env
        key_data = get_active_api_key('ollama')
        ollama_url = (key_data or {}).get('api_key', '') or OLLAMA_BASE_URL
        ollama_model = model or (key_data or {}).get('model', '') or OLLAMA_MODEL
        # Verify Ollama is reachable
        try:
            check = _requests.get(f"{ollama_url}/api/tags", timeout=5)
            check.raise_for_status()
            models = [m['name'] for m in check.json().get('models', [])]
            if not any(ollama_model in m for m in models):
                print(f"WARNING: Model '{ollama_model}' not found. Available: {', '.join(models)}")
                print("Will attempt anyway (Ollama may pull it automatically)...")
            print(f"Using Ollama at {ollama_url} with model {ollama_model}")
        except Exception as e:
            print(f"ERROR: Cannot reach Ollama at {ollama_url}: {e}")
            print("Make sure Ollama is running: ollama serve")
            return
    else:
        if not anthropic:
            print("ERROR: pip install anthropic")
            return
        # Try DB-stored key first (from admin panel), then env var
        api_key = None
        key_data = get_active_api_key('anthropic')
        if key_data:
            api_key = key_data['api_key']
            print("Using API key from database")
        if not api_key:
            api_key = ANTHROPIC_API_KEY
            if api_key:
                print("Using API key from environment")

        if not api_key:
            print("ERROR: No API key found. Set ANTHROPIC_API_KEY env var or add one via admin panel.")
            return

        client = anthropic.Anthropic(api_key=api_key)
        # Resolve Claude model: explicit param > DB-stored model > default
        claude_model = model or (key_data or {}).get('model', '') or "claude-haiku-4-5-20251001"
        print(f"Using Claude model: {claude_model}")

    # Build or resume plan
    plan = build_generation_plan(batch_size)

    if max_items:
        plan = plan[:max_items]

    if not batch_id:
        batch_id = create_batch(plan)
        print(f"Created batch: {batch_id}")
        print(f"Total prompts: {len(plan)}")
        print(f"Expected recipes: {sum(p['count'] for p in plan)}")
    else:
        print(f"Resuming batch: {batch_id}")

    # Get pending items
    with use_db() as db:
        pending = db.execute(
            "SELECT prompt_key FROM generation_queue WHERE batch_id = ? AND status = 'pending' ORDER BY id",
            (batch_id,)
        ).fetchall()

    pending_keys = {r["prompt_key"] for r in pending}
    plan = [p for p in plan if p["prompt_key"] in pending_keys]

    print(f"Pending prompts: {len(plan)}")

    completed = 0
    failed = 0

    for i, prompt_info in enumerate(plan):
        key = prompt_info["prompt_key"]
        print(f"\n[{i+1}/{len(plan)}] {key}")

        for attempt in range(MAX_RETRIES):
            try:
                if provider == 'ollama':
                    recipes_raw = generate_recipes_batch_ollama(ollama_url, ollama_model, prompt_info)
                else:
                    recipes_raw = generate_recipes_batch(client, prompt_info, model=claude_model)
                stored_ids = process_and_store(recipes_raw, prompt_info, batch_id)

                # Update queue
                with use_db() as db:
                    db.execute(
                        "UPDATE generation_queue SET status = 'completed', recipe_ids = ?, attempts = ? WHERE batch_id = ? AND prompt_key = ?",
                        (json.dumps(stored_ids), attempt + 1, batch_id, key)
                    )
                    db.execute(
                        "UPDATE generation_jobs SET completed = completed + ?, updated_at = CURRENT_TIMESTAMP WHERE batch_id = ?",
                        (len(stored_ids), batch_id)
                    )
                    db.commit()

                completed += len(stored_ids)
                print(f"  Stored {len(stored_ids)} recipes (total: {completed})")
                break

            except json.JSONDecodeError as e:
                print(f"  Attempt {attempt+1} JSON error: {e}")
                if attempt == MAX_RETRIES - 1:
                    _mark_failed(batch_id, key, str(e), attempt + 1)
                    failed += 1

            except Exception as e:
                print(f"  Attempt {attempt+1} error: {e}")
                if attempt == MAX_RETRIES - 1:
                    _mark_failed(batch_id, key, str(e), attempt + 1)
                    failed += 1
                else:
                    wait = 2 ** (attempt + 1)
                    print(f"  Retrying in {wait}s...")
                    time.sleep(wait)

        # Rate limiting - pause between API calls
        time.sleep(0.5)

    # Finalize
    with use_db() as db:
        status = "completed" if failed == 0 else "completed_with_errors"
        db.execute(
            "UPDATE generation_jobs SET status = ?, failed = ?, updated_at = CURRENT_TIMESTAMP WHERE batch_id = ?",
            (status, failed, batch_id)
        )
        db.commit()
        total_in_db = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]

    print(f"\n{'='*50}")
    print(f"Generation complete!")
    print(f"  Batch: {batch_id}")
    print(f"  New recipes: {completed}")
    print(f"  Failed prompts: {failed}")
    print(f"  Total recipes in DB: {total_in_db}")


def _mark_failed(batch_id, key, error, attempts):
    with use_db() as db:
        db.execute(
            "UPDATE generation_queue SET status = 'failed', error_message = ?, attempts = ? WHERE batch_id = ? AND prompt_key = ?",
            (error, attempts, batch_id, key)
        )
        db.execute(
            "UPDATE generation_jobs SET failed = failed + 1, updated_at = CURRENT_TIMESTAMP WHERE batch_id = ?",
            (batch_id,)
        )
        db.commit()


def get_generation_status(batch_id=None):
    """Get status of generation jobs."""
    with use_db() as db:
        if batch_id:
            job = db.execute("SELECT * FROM generation_jobs WHERE batch_id = ?", (batch_id,)).fetchone()
            if not job:
                return None
            pending = db.execute(
                "SELECT COUNT(*) FROM generation_queue WHERE batch_id = ? AND status = 'pending'", (batch_id,)
            ).fetchone()[0]
            completed = db.execute(
                "SELECT COUNT(*) FROM generation_queue WHERE batch_id = ? AND status = 'completed'", (batch_id,)
            ).fetchone()[0]
            failed_items = db.execute(
                "SELECT prompt_key, error_message FROM generation_queue WHERE batch_id = ? AND status = 'failed'", (batch_id,)
            ).fetchall()
            return {
                "batch_id": job["batch_id"],
                "status": job["status"],
                "total_planned": job["total_planned"],
                "completed_prompts": completed,
                "pending_prompts": pending,
                "failed_prompts": len(failed_items),
                "failed_details": [{"key": f["prompt_key"], "error": f["error_message"]} for f in failed_items],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"]
            }
        else:
            jobs = db.execute("SELECT * FROM generation_jobs ORDER BY created_at DESC").fetchall()
            return [{"batch_id": j["batch_id"], "status": j["status"],
                     "total_planned": j["total_planned"], "completed": j["completed"],
                     "failed": j["failed"], "created_at": j["created_at"]} for j in jobs]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate recipes with LLM (Claude or Ollama)")
    parser.add_argument("--batch-size", type=int, default=RECIPES_PER_API_CALL,
                       help="Recipes per API call")
    parser.add_argument("--resume", type=str, help="Resume a batch by ID")
    parser.add_argument("--max-items", type=int, help="Limit number of prompt combinations (for testing)")
    parser.add_argument("--status", type=str, help="Check status of a batch")
    parser.add_argument("--provider", type=str, choices=["anthropic", "ollama"],
                       help="LLM provider: anthropic (default) or ollama")
    parser.add_argument("--model", type=str,
                       help="Model name (e.g. claude-sonnet-4-6, llama3.1, mistral)")
    args = parser.parse_args()

    if args.status:
        status = get_generation_status(args.status)
        print(json.dumps(status, indent=2))
    else:
        run_generation(
            batch_id=args.resume,
            batch_size=args.batch_size,
            max_items=args.max_items,
            provider=args.provider,
            model=args.model
        )
