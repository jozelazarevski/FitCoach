"""Retag all recipes in the database with the latest tag engine.

Usage:
    python -m backend.retag                 # Retag all recipes
    python -m backend.retag --missing-only  # Only recipes with no tags
    python -m backend.retag --dry-run       # Preview without writing
    python -m backend.retag --source themealdb  # Only retag specific source
"""

import argparse
import json
import logging
import sys
import time

from backend.db import use_db
from backend.tag_engine import compute_deterministic_tags, compute_tags, detect_cuisine

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def load_recipes(source=None, missing_only=False):
    """Load recipes from DB for retagging."""
    with use_db() as db:
        if missing_only:
            rows = db.execute("""
                SELECT r.* FROM recipes r
                LEFT JOIN recipe_tags rt ON r.id = rt.recipe_id
                WHERE rt.id IS NULL AND r.status = 'active'
            """).fetchall()
        elif source:
            rows = db.execute(
                "SELECT * FROM recipes WHERE status = 'active' AND source = ?", (source,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM recipes WHERE status = 'active'").fetchall()
    return [dict(r) for r in rows]


def recipe_to_tag_input(row):
    """Convert a DB row dict into the format expected by tag engine."""
    for field in ('ingredients', 'steps', 'equipment', 'allergens', 'diet'):
        val = row.get(field, '[]')
        if isinstance(val, str):
            try:
                row[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                row[field] = []
    return row


def retag_all(source=None, missing_only=False, dry_run=False):
    """Retag all recipes in the database."""
    recipes = load_recipes(source=source, missing_only=missing_only)
    total = len(recipes)
    log.info('Found %d recipes to retag%s', total,
             ' (dry run)' if dry_run else '')

    if total == 0:
        log.info('Nothing to do.')
        return

    # Track tag dimension stats
    dim_counts = {}
    updated = 0
    errors = 0
    start = time.time()

    with use_db() as db:
        for i, row in enumerate(recipes):
            try:
                recipe = recipe_to_tag_input(row)
                recipe_id = recipe['id']

                # Compute all tags
                tags = compute_deterministic_tags(recipe)

                # Also update cuisine if missing
                if not recipe.get('cuisine') or recipe['cuisine'] == 'International':
                    cuisine_info = detect_cuisine(recipe)
                    if not dry_run and cuisine_info.get('cuisine', 'International') != 'International':
                        db.execute(
                            "UPDATE recipes SET cuisine = ?, country_of_origin = ?, region = ? WHERE id = ?",
                            (cuisine_info['cuisine'], cuisine_info.get('country', 'International'),
                             cuisine_info.get('region', 'International'), recipe_id)
                        )

                # Also update meal_type based on meal_suitability tags
                meal_suit = tags.get('meal_suitability', [])
                if meal_suit and not dry_run:
                    # Pick the most specific meal type
                    meal_priority = ['breakfast', 'lunch', 'snack', 'dinner']
                    new_meal = 'any'
                    for mp in meal_priority:
                        if f'{mp}_suitable' in meal_suit:
                            new_meal = mp
                            break
                    if new_meal != 'any' and recipe.get('meal_type', 'any') == 'any':
                        db.execute("UPDATE recipes SET meal_type = ? WHERE id = ?",
                                   (new_meal, recipe_id))

                # Track stats
                for dim, values in tags.items():
                    if isinstance(values, list):
                        dim_counts[dim] = dim_counts.get(dim, 0) + len(values)
                    else:
                        dim_counts[dim] = dim_counts.get(dim, 0) + 1

                if not dry_run:
                    # Delete existing tags and reinsert
                    db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
                    for dimension, values in tags.items():
                        if isinstance(values, list):
                            for v in values:
                                db.execute(
                                    "INSERT OR IGNORE INTO recipe_tags (recipe_id, dimension, tag) VALUES (?, ?, ?)",
                                    (recipe_id, dimension, str(v))
                                )
                        elif isinstance(values, (str, int, float)):
                            db.execute(
                                "INSERT OR IGNORE INTO recipe_tags (recipe_id, dimension, tag) VALUES (?, ?, ?)",
                                (recipe_id, dimension, str(values))
                            )

                updated += 1

                # Batch commit every 50
                if not dry_run and updated % 50 == 0:
                    db.commit()

                if (i + 1) % 100 == 0 or (i + 1) == total:
                    elapsed = time.time() - start
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    log.info('  [%d/%d] %.0f recipes/sec', i + 1, total, rate)

            except Exception as e:
                errors += 1
                log.error('  Error retagging recipe #%s (%s): %s',
                          row.get('id', '?'), row.get('name', '?'), e)

        if not dry_run:
            db.commit()

    elapsed = time.time() - start
    log.info('\n=== Retagging complete ===')
    log.info('  Recipes: %d updated, %d errors (%.1fs)', updated, errors, elapsed)
    log.info('\n  Tag dimensions:')
    for dim in sorted(dim_counts.keys()):
        log.info('    %-25s %d tags', dim, dim_counts[dim])

    # Show new dimension highlights
    new_dims = ['meal_suitability', 'flavor_profile', 'prep_style', 'primary_protein', 'equipment_needs']
    log.info('\n  New dimensions:')
    for dim in new_dims:
        log.info('    %-25s %d tags', dim, dim_counts.get(dim, 0))


def main():
    parser = argparse.ArgumentParser(description='Retag all recipes in FitCoach DB')
    parser.add_argument('--missing-only', action='store_true',
                        help='Only retag recipes with no existing tags')
    parser.add_argument('--source', type=str,
                        help='Only retag recipes from a specific source')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without writing to DB')
    args = parser.parse_args()

    retag_all(source=args.source, missing_only=args.missing_only, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
