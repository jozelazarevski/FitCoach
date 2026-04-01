"""Recipe scraper for FitCoach using free APIs + LLM macro estimation.

Sources:
  - TheMealDB (free API, 300+ recipes with ingredients)
  - LLM estimation for macros (uses backend Anthropic key)

Usage:
    python -m tools.scraper.recipe_scraper --all                          # Scrape ALL recipes from TheMealDB
    python -m tools.scraper.recipe_scraper --search "chicken" --count 20  # Search TheMealDB
    python -m tools.scraper.recipe_scraper --category Seafood --count 10  # By category
    python -m tools.scraper.recipe_scraper --search "pasta" --dry-run     # Preview without DB insert
    python -m tools.scraper.recipe_scraper --output recipes.json --all    # Export to JSON
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

MEALDB_BASE = 'https://www.themealdb.com/api/json/v1/1'


# ── TheMealDB API ───────────────────────────────────────────────────────────

def mealdb_search(query):
    """Search TheMealDB by name."""
    resp = requests.get(f'{MEALDB_BASE}/search.php', params={'s': query}, timeout=10)
    resp.raise_for_status()
    return resp.json().get('meals') or []


def mealdb_by_category(category):
    """List meals in a TheMealDB category (returns summary only)."""
    resp = requests.get(f'{MEALDB_BASE}/filter.php', params={'c': category}, timeout=10)
    resp.raise_for_status()
    return resp.json().get('meals') or []


def mealdb_by_id(meal_id):
    """Get full meal detail by ID."""
    resp = requests.get(f'{MEALDB_BASE}/lookup.php', params={'i': meal_id}, timeout=10)
    resp.raise_for_status()
    meals = resp.json().get('meals') or []
    return meals[0] if meals else None


def mealdb_categories():
    """List all available categories."""
    resp = requests.get(f'{MEALDB_BASE}/categories.php', timeout=10)
    resp.raise_for_status()
    return [c['strCategory'] for c in resp.json().get('categories', [])]


def mealdb_all_by_letter():
    """Fetch ALL recipes by iterating through alphabet."""
    all_meals = []
    seen_ids = set()
    for letter in 'abcdefghijklmnopqrstuvwxyz':
        try:
            resp = requests.get(f'{MEALDB_BASE}/search.php', params={'f': letter}, timeout=10)
            resp.raise_for_status()
            meals = resp.json().get('meals') or []
            for m in meals:
                mid = m.get('idMeal')
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    all_meals.append(m)
            log.info('  Letter %s: %d meals (total: %d)', letter, len(meals), len(all_meals))
        except Exception as e:
            log.warning('  Letter %s failed: %s', letter, e)
        time.sleep(0.3)
    return all_meals


# ── Transform TheMealDB → FitCoach format ───────────────────────────────────

_UNIT_TO_GRAMS = {
    'cup': 240, 'cups': 240, 'tablespoon': 15, 'tablespoons': 15, 'tbsp': 15,
    'teaspoon': 5, 'teaspoons': 5, 'tsp': 5, 'oz': 28, 'ounce': 28, 'ounces': 28,
    'pound': 454, 'pounds': 454, 'lb': 454, 'lbs': 454, 'g': 1, 'gram': 1, 'grams': 1,
    'kg': 1000, 'ml': 1, 'clove': 5, 'cloves': 5, 'slice': 30, 'slices': 30,
    'can': 400, 'bunch': 100, 'head': 500, 'stalk': 60, 'fillet': 170, 'breast': 200,
    'pinch': 1, 'handful': 30, 'sprig': 2, 'sprigs': 2, 'piece': 100,
}

_FRACTION_MAP = {
    '\u00bc': 0.25, '\u00bd': 0.5, '\u00be': 0.75,
    '\u2153': 0.333, '\u2154': 0.667,
}


def _parse_amount(measure_str):
    """Parse a MealDB measure string like '2 cups' into (amount_str, grams)."""
    if not measure_str or not measure_str.strip():
        return '', 100

    text = measure_str.strip()
    for fchar, fval in _FRACTION_MAP.items():
        text = text.replace(fchar, str(fval))

    match = re.match(r'^([\d./]+)\s*(.*)', text)
    if match:
        try:
            num_str = match.group(1)
            if '/' in num_str:
                parts = num_str.split('/')
                qty = float(parts[0]) / float(parts[1])
            else:
                qty = float(num_str)
        except (ValueError, ZeroDivisionError):
            qty = 1.0
        unit_rest = match.group(2).strip().lower()
        # Find unit
        for unit, gperu in _UNIT_TO_GRAMS.items():
            if unit_rest.startswith(unit):
                return measure_str.strip(), max(1, round(qty * gperu))
        # No unit matched, assume grams if small number, pieces if large
        if qty <= 10:
            return measure_str.strip(), max(1, round(qty * 100))
        return measure_str.strip(), max(1, round(qty))
    return measure_str.strip(), 100


def _extract_ingredients(meal):
    """Extract ingredients from TheMealDB meal object."""
    ingredients = []
    for i in range(1, 21):
        item = (meal.get(f'strIngredient{i}') or '').strip()
        measure = (meal.get(f'strMeasure{i}') or '').strip()
        if not item:
            continue
        amount_str, grams = _parse_amount(measure)
        ingredients.append({
            'item': item,
            'amount': amount_str or '1 serving',
            'grams': grams,
        })
    return ingredients


def _parse_steps(instructions):
    """Parse TheMealDB instructions into step list."""
    if not instructions:
        return ['Follow recipe instructions.']
    # Split on newlines or numbered steps
    steps = []
    for line in re.split(r'\r?\n|\. (?=\d)|(?<=\.) (?=[A-Z])', instructions):
        line = line.strip().rstrip('.')
        if len(line) > 10:
            # Remove step numbers
            line = re.sub(r'^(?:STEP\s*)?\d+[\.\)]\s*', '', line)
            if line:
                steps.append(line + '.')
    return steps if steps else [instructions.strip()]


def _detect_category(name, ingredients_text):
    """Detect recipe protein category."""
    text = f'{name} {ingredients_text}'.lower()
    seafood = {'shrimp', 'salmon', 'tuna', 'cod', 'tilapia', 'fish', 'crab', 'lobster',
               'scallop', 'halibut', 'trout', 'bass', 'mackerel', 'sardine', 'prawn',
               'swordfish', 'anchovy', 'clam', 'mussel', 'oyster', 'squid', 'calamari'}
    poultry = {'chicken', 'turkey', 'duck', 'hen'}
    red_meat = {'beef', 'steak', 'pork', 'lamb', 'veal', 'bison', 'venison',
                'bacon', 'ham', 'sausage', 'meatball', 'rib'}
    for kw in seafood:
        if kw in text:
            return 'fish' if kw in {'fish', 'cod', 'tilapia', 'salmon', 'tuna', 'bass', 'trout', 'halibut', 'swordfish', 'mackerel'} else 'seafood'
    for kw in poultry:
        if kw in text:
            return 'poultry'
    for kw in red_meat:
        if kw in text:
            return 'red_meat'
    animal = {'egg', 'cheese', 'milk', 'cream', 'butter', 'yogurt', 'honey'}
    if any(kw in text for kw in animal):
        return 'vegetarian'
    return 'vegan'


def _detect_meal_type(name, mealdb_category):
    """Guess meal type."""
    nl = name.lower()
    cat = (mealdb_category or '').lower()
    if any(w in nl for w in ['breakfast', 'pancake', 'waffle', 'oatmeal', 'omelet', 'granola']):
        return 'breakfast'
    if cat in ('starter', 'side'):
        return 'snack'
    if cat == 'breakfast':
        return 'breakfast'
    if cat == 'dessert':
        return 'snack'
    if any(w in nl for w in ['salad', 'sandwich', 'wrap', 'soup']):
        return 'lunch'
    return 'dinner'


def _detect_allergens(ingredients_text):
    """Detect allergens from ingredient text."""
    t = ingredients_text.lower()
    a = []
    if any(w in t for w in ['milk', 'cream', 'cheese', 'butter', 'yogurt', 'whey']):
        a.append('dairy')
    if any(w in t for w in ['flour', 'bread', 'pasta', 'wheat', 'breadcrumb', 'noodle', 'tortilla']):
        a.append('gluten')
    if any(w in t for w in ['egg ']):
        a.append('egg')
    if any(w in t for w in ['soy sauce', 'soy', 'tofu', 'miso']):
        a.append('soy')
    if any(w in t for w in ['almond', 'walnut', 'pecan', 'cashew', 'pistachio']):
        a.append('tree_nuts')
    if 'peanut' in t:
        a.append('peanuts')
    if any(w in t for w in ['shrimp', 'crab', 'lobster', 'clam', 'mussel', 'oyster']):
        a.append('shellfish')
    if 'sesame' in t:
        a.append('sesame')
    return a


def _detect_diet_tags(category, allergens, calories, protein, carbs, fat):
    """Detect diet tags."""
    tags = []
    if category == 'vegan':
        tags.extend(['vegan', 'vegetarian', 'dairy_free'])
    elif category == 'vegetarian':
        tags.append('vegetarian')
    if 'dairy' not in allergens:
        tags.append('dairy_free')
    if 'gluten' not in allergens:
        tags.append('gluten_free')
    if protein and protein >= 25:
        tags.append('high_protein')
    if carbs and carbs <= 20:
        tags.extend(['low_carb', 'keto'])
    return list(set(tags))


# ── LLM Macro Estimation ───────────────────────────────────────────────────

def _estimate_macros_llm(name, ingredients):
    """Use the backend LLM to estimate macros for a recipe."""
    try:
        from backend.llm_client import call_llm_json
    except ImportError:
        return _estimate_macros_heuristic(ingredients)

    ing_list = ', '.join(f"{i['amount']} {i['item']}" for i in ingredients)
    prompt = f"""Estimate the nutrition per serving for this recipe.
Recipe: {name}
Ingredients: {ing_list}
Assume 4 servings unless clearly a single-serve recipe.

Return ONLY valid JSON:
{{"calories": <int>, "protein": <int>, "carbs": <int>, "fat": <int>, "fiber": <int>, "sugar": <int>, "servings": <int>}}

Rules:
- All values are PER SERVING integers
- Be realistic based on typical cooking of these ingredients
- protein*4 + carbs*4 + fat*9 should roughly equal calories"""

    try:
        result = call_llm_json(prompt, max_tokens=200)
        if isinstance(result, dict) and 'calories' in result:
            return result
    except Exception as e:
        log.warning('LLM estimation failed for %s: %s', name, e)

    return _estimate_macros_heuristic(ingredients)


def _estimate_macros_heuristic(ingredients):
    """Rough heuristic macro estimation from ingredients."""
    # Very rough per-ingredient estimates
    _PROTEIN_FOODS = {'chicken', 'turkey', 'beef', 'pork', 'lamb', 'fish', 'salmon',
                      'tuna', 'shrimp', 'egg', 'tofu', 'lentil', 'bean'}
    _CARB_FOODS = {'rice', 'pasta', 'bread', 'potato', 'flour', 'sugar', 'noodle',
                   'oat', 'corn', 'tortilla'}
    _FAT_FOODS = {'oil', 'butter', 'cream', 'cheese', 'coconut milk', 'avocado', 'nut'}

    total_g = sum(i['grams'] for i in ingredients)
    ings_text = ' '.join(i['item'].lower() for i in ingredients)

    protein = 0
    carbs = 0
    fat = 0
    for ing in ingredients:
        item = ing['item'].lower()
        g = ing['grams']
        if any(p in item for p in _PROTEIN_FOODS):
            protein += g * 0.22
            fat += g * 0.08
            carbs += g * 0.01
        elif any(c in item for c in _CARB_FOODS):
            carbs += g * 0.25
            protein += g * 0.03
            fat += g * 0.01
        elif any(f in item for f in _FAT_FOODS):
            fat += g * 0.5
            protein += g * 0.01
        else:
            # Vegetable/other
            carbs += g * 0.05
            protein += g * 0.02
            fat += g * 0.01

    # Per serving (assume 4)
    servings = 4
    p = max(1, round(protein / servings))
    c = max(1, round(carbs / servings))
    f = max(1, round(fat / servings))
    cal = p * 4 + c * 4 + f * 9

    return {'calories': cal, 'protein': p, 'carbs': c, 'fat': f,
            'fiber': 3, 'sugar': 5, 'servings': servings}


def transform_mealdb(meal, use_llm=True):
    """Transform a TheMealDB meal into FitCoach recipe format."""
    name = (meal.get('strMeal') or '').strip()
    if not name:
        return None

    ingredients = _extract_ingredients(meal)
    if not ingredients:
        return None

    instructions = meal.get('strInstructions', '')
    steps = _parse_steps(instructions)

    ingredients_text = ' '.join(f"{i['item']}" for i in ingredients)
    mealdb_cat = meal.get('strCategory', '')
    category = _detect_category(name, ingredients_text)
    meal_type = _detect_meal_type(name, mealdb_cat)
    allergens = _detect_allergens(ingredients_text)

    # Estimate macros
    if use_llm:
        macros = _estimate_macros_llm(name, ingredients)
    else:
        macros = _estimate_macros_heuristic(ingredients)

    servings = macros.get('servings', 4)
    calories = macros.get('calories', 400)
    protein = macros.get('protein', 20)
    carbs_val = macros.get('carbs', 40)
    fat_val = macros.get('fat', 15)

    total_time = len(steps) * 5 + 10  # rough estimate
    diet_tags = _detect_diet_tags(category, allergens, calories, protein, carbs_val, fat_val)

    return {
        'name': name,
        'description': f"{mealdb_cat} dish - {name}".strip(' -'),
        'category': category,
        'meal_type': meal_type,
        'difficulty': 'easy' if len(steps) <= 4 else 'medium' if len(steps) <= 8 else 'hard',
        'prep_time_min': max(10, len(ingredients) * 2),
        'cook_time_min': max(10, total_time - len(ingredients) * 2),
        'total_time_min': total_time,
        'servings': servings,
        'calories': calories,
        'protein': protein,
        'carbs': carbs_val,
        'fat': fat_val,
        'fiber': macros.get('fiber', 3),
        'sugar': macros.get('sugar', 5),
        'ingredients': ingredients,
        'steps': steps,
        'tips': '',
        'equipment': [],
        'allergens': allergens,
        'diet': diet_tags,
        'meal_prep_friendly': False,
        'source': 'themealdb',
        'generation_batch': f'scraper_mealdb_{date.today().isoformat()}',
    }


# ── Main Pipeline ───────────────────────────────────────────────────────────

def scrape_recipes(mode, query, count, dry_run=False, output_file=None, use_llm=True):
    """Main scraping pipeline."""
    log.info('Fetching recipes from TheMealDB (%s: %s)...', mode, query or 'all')

    raw_meals = []

    if mode == 'all':
        raw_meals = mealdb_all_by_letter()
    elif mode == 'search':
        raw_meals = mealdb_search(query)
    elif mode == 'category':
        # Category endpoint only returns summaries, need to fetch full details
        summaries = mealdb_by_category(query)
        log.info('Found %d meals in category %s, fetching details...', len(summaries), query)
        for i, s in enumerate(summaries[:count]):
            meal = mealdb_by_id(s['idMeal'])
            if meal:
                raw_meals.append(meal)
            if (i + 1) % 10 == 0:
                log.info('  Fetched %d/%d', i + 1, min(len(summaries), count))
            time.sleep(0.3)

    if not raw_meals:
        log.warning('No meals found')
        return []

    log.info('Found %d raw meals, transforming...', len(raw_meals))

    # Dedup check
    existing_names = set()
    if not dry_run:
        try:
            from backend.db import use_db
            with use_db() as db:
                rows = db.execute("SELECT LOWER(name) FROM recipes WHERE status = 'active'").fetchall()
                existing_names = {row[0] for row in rows}
        except Exception:
            pass

    recipes = []
    skipped = 0

    for i, meal in enumerate(raw_meals[:count * 2]):
        if len(recipes) >= count:
            break

        recipe = transform_mealdb(meal, use_llm=use_llm)
        if not recipe:
            continue

        if recipe['name'].lower() in existing_names:
            log.info('  [%d] Skipping duplicate: %s', i + 1, recipe['name'])
            skipped += 1
            continue

        existing_names.add(recipe['name'].lower())
        recipes.append(recipe)
        log.info('  [%d] %s — %d cal, %dg P, %dg C, %dg F (%s)',
                 i + 1, recipe['name'], recipe['calories'], recipe['protein'],
                 recipe['carbs'], recipe['fat'], recipe['category'])

    log.info('\n=== %d recipes ready, %d skipped ===', len(recipes), skipped)

    if dry_run:
        for r in recipes:
            print(f"\n  {r['name']} [{r['category']}] [{r['meal_type']}]")
            print(f"    {r['calories']} cal | {r['protein']}g P | {r['carbs']}g C | {r['fat']}g F")
            print(f"    {len(r['ingredients'])} ingredients, {len(r['steps'])} steps")
        return recipes

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(recipes, f, indent=2, ensure_ascii=False)
        log.info('Saved %d recipes to %s', len(recipes), output_file)
        return recipes

    # Insert into DB
    inserted = 0
    from backend.models import insert_recipe
    from backend.tag_engine import compute_tags, detect_cuisine

    for recipe in recipes:
        try:
            cuisine_info = detect_cuisine(recipe)
            recipe['cuisine'] = cuisine_info.get('cuisine', 'International')
            recipe['country_of_origin'] = cuisine_info.get('country', 'International')
            recipe['region'] = cuisine_info.get('region', 'International')
            tags = compute_tags(recipe)
            recipe_id = insert_recipe(recipe, tags)
            inserted += 1
            log.info('  Inserted #%d: %s', recipe_id, recipe['name'])
        except Exception as e:
            log.error('  Failed to insert %s: %s', recipe['name'], e)

    log.info('\n=== Inserted %d recipes into DB ===', inserted)
    return recipes


def main():
    parser = argparse.ArgumentParser(description='Scrape recipes for FitCoach DB')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--search', type=str, help='Search by name (e.g. "chicken")')
    group.add_argument('--category', type=str, help='TheMealDB category (e.g. Seafood, Chicken, Beef, Vegetarian, Pasta, Dessert)')
    group.add_argument('--all', action='store_true', help='Scrape ALL recipes from TheMealDB (~300)')
    parser.add_argument('--count', type=int, default=50, help='Max recipes (default: 50)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without inserting')
    parser.add_argument('--output', type=str, help='Save to JSON file instead of DB')
    parser.add_argument('--no-llm', action='store_true', help='Use heuristic macros instead of LLM estimation')
    parser.add_argument('--list-categories', action='store_true', help='List available categories and exit')
    args = parser.parse_args()

    if args.list_categories:
        cats = mealdb_categories()
        print('Available categories:', ', '.join(cats))
        return

    if args.all:
        mode, query = 'all', None
        args.count = 999
    elif args.search:
        mode, query = 'search', args.search
    else:
        mode, query = 'category', args.category

    scrape_recipes(mode, query, args.count, dry_run=args.dry_run,
                   output_file=args.output, use_llm=not args.no_llm)


if __name__ == '__main__':
    main()
