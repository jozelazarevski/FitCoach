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

from config import ANTHROPIC_API_KEY, RECIPES_PER_API_CALL, MAX_RETRIES
from backend.db import get_db, init_db
from backend.models import insert_recipe, insert_tags
from backend.tag_engine import detect_cuisine, compute_tags

try:
    import anthropic
except ImportError:
    anthropic = None

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
  "meal_prep_friendly": true/false
}}

Rules:
- Use realistic macro numbers (protein + carbs + fat calories should roughly equal total calories)
- {goal_guidance}
- Every ingredient must have exact gram measurements
- Include 6-15 ingredients per recipe
- Allergens from: gluten, dairy, egg, soy, tree_nuts, peanuts, fish, shellfish, sesame
- Diet tags from: vegan, vegetarian, high_protein, low_carb, keto, paleo, gluten_free, dairy_free
- Equipment examples: pan, oven, grill, wok, blender, sheet pan, dutch oven, pot
- Make recipes practical and delicious
- VARY the recipes - different proteins, vegetables, cooking methods, flavor profiles
- Names should be appetizing and specific (not generic)"""

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
    for cuisine in CUISINES:
        for meal_type in MEAL_TYPES:
            for category in CATEGORIES:
                for goal in GOALS:
                    # Skip impossible combos
                    if category in ("vegan", "vegetarian") and goal == "cutting" and meal_type == "snack":
                        continue
                    if category in ("fish", "seafood") and meal_type == "breakfast" and cuisine not in ("Japanese",):
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

    db = get_db()
    total = sum(p["count"] for p in plan)

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
    db.close()
    return batch_id


def generate_recipes_batch(client, prompt_info):
    """Call Claude API to generate a batch of recipes."""
    goal_guide = GOAL_GUIDANCE.get(prompt_info["goal"], "Balanced macros")
    prompt = PROMPT_TEMPLATE.format(
        count=prompt_info["count"],
        cuisine=prompt_info["cuisine"],
        category=prompt_info["category"],
        meal_type=prompt_info["meal_type"],
        goal=prompt_info["goal"],
        difficulty=prompt_info["difficulty"],
        goal_guidance=goal_guide
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    # Extract JSON from response
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    recipes = json.loads(text)
    if not isinstance(recipes, list):
        recipes = [recipes]
    return recipes


def process_and_store(recipes_raw, prompt_info, batch_id):
    """Process raw recipe data, compute tags, store in DB."""
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

        # Insert recipe
        recipe_id = insert_recipe(recipe_data)

        # Compute and insert tags
        tags = compute_tags(recipe_data)
        insert_tags(recipe_id, tags)

        stored_ids.append(recipe_id)

    return stored_ids


def run_generation(batch_id=None, batch_size=RECIPES_PER_API_CALL, max_items=None):
    """Main generation loop. Resumable via batch_id."""
    if not anthropic:
        print("ERROR: pip install anthropic")
        return

    init_db()

    # Try DB-stored key first, then env var
    api_key = ANTHROPIC_API_KEY
    if not api_key:
        from backend.api.admin import get_active_api_key
        key_data = get_active_api_key('anthropic')
        if key_data:
            api_key = key_data['api_key']
            print(f"Using API key from database")

    if not api_key:
        print("ERROR: No API key found. Set ANTHROPIC_API_KEY env var or add one via admin panel.")
        return

    client = anthropic.Anthropic(api_key=api_key)

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
    db = get_db()
    pending = db.execute(
        "SELECT prompt_key FROM generation_queue WHERE batch_id = ? AND status = 'pending' ORDER BY id",
        (batch_id,)
    ).fetchall()
    db.close()

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
                recipes_raw = generate_recipes_batch(client, prompt_info)
                stored_ids = process_and_store(recipes_raw, prompt_info, batch_id)

                # Update queue
                db = get_db()
                db.execute(
                    "UPDATE generation_queue SET status = 'completed', recipe_ids = ?, attempts = ? WHERE batch_id = ? AND prompt_key = ?",
                    (json.dumps(stored_ids), attempt + 1, batch_id, key)
                )
                db.execute(
                    "UPDATE generation_jobs SET completed = completed + ?, updated_at = CURRENT_TIMESTAMP WHERE batch_id = ?",
                    (len(stored_ids), batch_id)
                )
                db.commit()
                db.close()

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
    db = get_db()
    status = "completed" if failed == 0 else "completed_with_errors"
    db.execute(
        "UPDATE generation_jobs SET status = ?, failed = ?, updated_at = CURRENT_TIMESTAMP WHERE batch_id = ?",
        (status, failed, batch_id)
    )
    db.commit()
    total_in_db = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]
    db.close()

    print(f"\n{'='*50}")
    print(f"Generation complete!")
    print(f"  Batch: {batch_id}")
    print(f"  New recipes: {completed}")
    print(f"  Failed prompts: {failed}")
    print(f"  Total recipes in DB: {total_in_db}")


def _mark_failed(batch_id, key, error, attempts):
    db = get_db()
    db.execute(
        "UPDATE generation_queue SET status = 'failed', error_message = ?, attempts = ? WHERE batch_id = ? AND prompt_key = ?",
        (error, attempts, batch_id, key)
    )
    db.execute(
        "UPDATE generation_jobs SET failed = failed + 1, updated_at = CURRENT_TIMESTAMP WHERE batch_id = ?",
        (batch_id,)
    )
    db.commit()
    db.close()


def get_generation_status(batch_id=None):
    """Get status of generation jobs."""
    db = get_db()
    if batch_id:
        job = db.execute("SELECT * FROM generation_jobs WHERE batch_id = ?", (batch_id,)).fetchone()
        if not job:
            db.close()
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
        db.close()
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
        db.close()
        return [{"batch_id": j["batch_id"], "status": j["status"],
                 "total_planned": j["total_planned"], "completed": j["completed"],
                 "failed": j["failed"], "created_at": j["created_at"]} for j in jobs]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate recipes with Claude API")
    parser.add_argument("--batch-size", type=int, default=RECIPES_PER_API_CALL,
                       help="Recipes per API call")
    parser.add_argument("--resume", type=str, help="Resume a batch by ID")
    parser.add_argument("--max-items", type=int, help="Limit number of prompt combinations (for testing)")
    parser.add_argument("--status", type=str, help="Check status of a batch")
    args = parser.parse_args()

    if args.status:
        status = get_generation_status(args.status)
        print(json.dumps(status, indent=2))
    else:
        run_generation(
            batch_id=args.resume,
            batch_size=args.batch_size,
            max_items=args.max_items
        )
