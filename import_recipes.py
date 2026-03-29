"""
Import recipes from a JSON file into the FitCoach database.

Usage:
    python import_recipes.py recipes.json
    python import_recipes.py recipes.json --dry-run
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.db import init_db, use_db
from backend.models import insert_recipe
from backend.tag_engine import detect_cuisine, compute_tags, compute_deterministic_tags


def _merge_tags(llm_tags, det_tags):
    merged = dict(llm_tags)
    for dim, values in det_tags.items():
        merged[dim] = values
    return merged


def import_recipes(filepath, dry_run=False):
    init_db()

    with open(filepath, 'r') as f:
        recipes = json.load(f)

    if not isinstance(recipes, list):
        print("ERROR: JSON file must contain an array of recipe objects")
        return

    print(f"Found {len(recipes)} recipes in {filepath}")

    if dry_run:
        # Validate only
        errors = 0
        for i, r in enumerate(recipes):
            missing = [f for f in ('name', 'calories', 'protein', 'carbs', 'fat', 'ingredients', 'steps') if f not in r]
            if missing:
                print(f"  [{i}] {r.get('name', 'UNNAMED')}: missing {', '.join(missing)}")
                errors += 1
        print(f"\nValidation: {len(recipes) - errors} OK, {errors} errors")
        return

    imported = 0
    skipped = 0
    errors = 0

    # Check for existing recipe names to avoid duplicates
    with use_db() as db:
        existing = set(
            row[0] for row in db.execute("SELECT name FROM recipes WHERE status = 'active'").fetchall()
        )

    batch_id = f"import_{os.path.basename(filepath).replace('.json', '')}"

    for i, recipe_data in enumerate(recipes):
        try:
            if not recipe_data.get('name'):
                print(f"  [{i}] Skipped: no name")
                skipped += 1
                continue

            if recipe_data['name'] in existing:
                skipped += 1
                continue

            # Ensure required numeric fields
            for field in ('calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar',
                          'prep_time_min', 'cook_time_min', 'total_time_min', 'servings'):
                recipe_data[field] = int(recipe_data.get(field, 0) or 0)

            if recipe_data['total_time_min'] == 0:
                recipe_data['total_time_min'] = recipe_data['prep_time_min'] + recipe_data['cook_time_min']

            # Detect cuisine if not set
            if not recipe_data.get('cuisine') or recipe_data['cuisine'] == 'International':
                cuisine_info = detect_cuisine(recipe_data)
                recipe_data['cuisine'] = cuisine_info['cuisine']
                recipe_data['country_of_origin'] = cuisine_info['country']
                recipe_data['region'] = cuisine_info['region']

            recipe_data['source'] = 'imported'
            recipe_data['generation_batch'] = batch_id

            # Build tags
            llm_tags = recipe_data.pop('tags', None) or {}
            if llm_tags:
                det_tags = compute_deterministic_tags(recipe_data)
                tags = _merge_tags(llm_tags, det_tags)
            else:
                tags = compute_tags(recipe_data)

            recipe_id = insert_recipe(recipe_data, tags_dict=tags)
            existing.add(recipe_data['name'])
            imported += 1

            if imported % 100 == 0:
                print(f"  Imported {imported}...")

        except Exception as e:
            print(f"  [{i}] Error on '{recipe_data.get('name', '?')}': {e}")
            errors += 1

    with use_db() as db:
        total = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]

    print(f"\nDone!")
    print(f"  Imported: {imported}")
    print(f"  Skipped (duplicates/invalid): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total recipes in DB: {total}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_recipes.py <recipes.json> [--dry-run]")
        sys.exit(1)

    filepath = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    import_recipes(filepath, dry_run=dry_run)
