"""
Tag Engine - Computes 200+ tags across 20+ dimensions for recipes.
Ported from the standalone tagging script for SQLite integration.
"""

CUISINE_KEYWORDS = {
    "thai": {"cuisine": "Thai", "region": "Southeast Asia", "country": "Thailand"},
    "pad": {"cuisine": "Thai", "region": "Southeast Asia", "country": "Thailand"},
    "basil chicken": {"cuisine": "Thai", "region": "Southeast Asia", "country": "Thailand"},
    "korean": {"cuisine": "Korean", "region": "East Asia", "country": "South Korea"},
    "bulgogi": {"cuisine": "Korean", "region": "East Asia", "country": "South Korea"},
    "gochujang": {"cuisine": "Korean", "region": "East Asia", "country": "South Korea"},
    "bibimbap": {"cuisine": "Korean", "region": "East Asia", "country": "South Korea"},
    "japanese": {"cuisine": "Japanese", "region": "East Asia", "country": "Japan"},
    "teriyaki": {"cuisine": "Japanese", "region": "East Asia", "country": "Japan"},
    "miso": {"cuisine": "Japanese", "region": "East Asia", "country": "Japan"},
    "poke": {"cuisine": "Japanese", "region": "East Asia", "country": "Japan"},
    "chinese": {"cuisine": "Chinese", "region": "East Asia", "country": "China"},
    "szechuan": {"cuisine": "Chinese", "region": "East Asia", "country": "China"},
    "stir-fry": {"cuisine": "Chinese", "region": "East Asia", "country": "China"},
    "stir fry": {"cuisine": "Chinese", "region": "East Asia", "country": "China"},
    "hoisin": {"cuisine": "Chinese", "region": "East Asia", "country": "China"},
    "vietnamese": {"cuisine": "Vietnamese", "region": "Southeast Asia", "country": "Vietnam"},
    "indonesian": {"cuisine": "Indonesian", "region": "Southeast Asia", "country": "Indonesia"},
    "indian": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "tikka": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "masala": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "dal": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "paneer": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "garam": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "curry": {"cuisine": "Indian", "region": "South Asia", "country": "India"},
    "middle eastern": {"cuisine": "Middle Eastern", "region": "Middle East", "country": "Lebanon"},
    "shawarma": {"cuisine": "Middle Eastern", "region": "Middle East", "country": "Lebanon"},
    "tahini": {"cuisine": "Middle Eastern", "region": "Middle East", "country": "Lebanon"},
    "lebanese": {"cuisine": "Lebanese", "region": "Middle East", "country": "Lebanon"},
    "persian": {"cuisine": "Persian", "region": "Middle East", "country": "Iran"},
    "turkish": {"cuisine": "Turkish", "region": "Middle East", "country": "Turkey"},
    "kofta": {"cuisine": "Middle Eastern", "region": "Middle East", "country": "Turkey"},
    "shakshuka": {"cuisine": "Israeli", "region": "Middle East", "country": "Israel"},
    "mediterranean": {"cuisine": "Mediterranean", "region": "Mediterranean", "country": "Greece"},
    "greek": {"cuisine": "Greek", "region": "Mediterranean", "country": "Greece"},
    "tzatziki": {"cuisine": "Greek", "region": "Mediterranean", "country": "Greece"},
    "italian": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "parmesan": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "pesto": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "bolognese": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "risotto": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "caprese": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "tuscan": {"cuisine": "Italian", "region": "Southern Europe", "country": "Italy"},
    "french": {"cuisine": "French", "region": "Western Europe", "country": "France"},
    "provençal": {"cuisine": "French", "region": "Western Europe", "country": "France"},
    "béarnaise": {"cuisine": "French", "region": "Western Europe", "country": "France"},
    "spanish": {"cuisine": "Spanish", "region": "Southern Europe", "country": "Spain"},
    "romesco": {"cuisine": "Spanish", "region": "Southern Europe", "country": "Spain"},
    "mexican": {"cuisine": "Mexican", "region": "Central America", "country": "Mexico"},
    "taco": {"cuisine": "Mexican", "region": "Central America", "country": "Mexico"},
    "fajita": {"cuisine": "Mexican", "region": "Central America", "country": "Mexico"},
    "burrito": {"cuisine": "Mexican", "region": "Central America", "country": "Mexico"},
    "salsa verde": {"cuisine": "Mexican", "region": "Central America", "country": "Mexico"},
    "southwestern": {"cuisine": "Tex-Mex", "region": "North America", "country": "USA"},
    "tex-mex": {"cuisine": "Tex-Mex", "region": "North America", "country": "USA"},
    "cajun": {"cuisine": "Cajun", "region": "North America", "country": "USA"},
    "caribbean": {"cuisine": "Caribbean", "region": "Caribbean", "country": "Jamaica"},
    "jerk": {"cuisine": "Caribbean", "region": "Caribbean", "country": "Jamaica"},
    "hawaiian": {"cuisine": "Hawaiian", "region": "Pacific", "country": "USA"},
    "chimichurri": {"cuisine": "Argentinian", "region": "South America", "country": "Argentina"},
    "brazilian": {"cuisine": "Brazilian", "region": "South America", "country": "Brazil"},
    "peruvian": {"cuisine": "Peruvian", "region": "South America", "country": "Peru"},
    "moroccan": {"cuisine": "Moroccan", "region": "North Africa", "country": "Morocco"},
    "harissa": {"cuisine": "North African", "region": "North Africa", "country": "Tunisia"},
    "ethiopian": {"cuisine": "Ethiopian", "region": "East Africa", "country": "Ethiopia"},
    "bbq": {"cuisine": "American BBQ", "region": "North America", "country": "USA"},
    "classic": {"cuisine": "American", "region": "North America", "country": "USA"},
    "rustic": {"cuisine": "European", "region": "Europe", "country": "France"},
}

CUISINE_INGREDIENTS = {
    "soy sauce": ("East Asian", "Asia"),
    "tamari": ("Japanese", "Japan"),
    "fish sauce": ("Thai", "Thailand"),
    "coconut milk": ("Thai", "Thailand"),
    "red curry paste": ("Thai", "Thailand"),
    "gochujang": ("Korean", "South Korea"),
    "miso paste": ("Japanese", "Japan"),
    "hoisin sauce": ("Chinese", "China"),
    "tamarind paste": ("Thai", "Thailand"),
    "rice vinegar": ("East Asian", "Asia"),
    "sesame oil": ("East Asian", "Asia"),
    "garam masala": ("Indian", "India"),
    "turmeric": ("Indian", "India"),
    "cumin": ("Middle Eastern", "Middle East"),
    "harissa paste": ("North African", "Tunisia"),
    "tahini": ("Middle Eastern", "Lebanon"),
    "feta cheese": ("Greek", "Greece"),
    "halloumi": ("Cypriot", "Cyprus"),
    "parmesan cheese": ("Italian", "Italy"),
    "mozzarella cheese": ("Italian", "Italy"),
    "ricotta cheese": ("Italian", "Italy"),
    "paneer": ("Indian", "India"),
    "tortilla": ("Mexican", "Mexico"),
    "corn tortilla": ("Mexican", "Mexico"),
    "pita bread": ("Middle Eastern", "Lebanon"),
    "naan bread": ("Indian", "India"),
    "chimichurri": ("Argentinian", "Argentina"),
    "bbq sauce": ("American", "USA"),
    "sriracha": ("Thai", "Thailand"),
    "salsa": ("Mexican", "Mexico"),
}


def detect_cuisine(recipe):
    """Detect cuisine from recipe name and ingredients."""
    name_lower = recipe["name"].lower()

    for keyword, info in CUISINE_KEYWORDS.items():
        if keyword in name_lower:
            return info

    ingredients = recipe.get("ingredients", [])
    ing_items = []
    for ing in ingredients:
        if isinstance(ing, dict):
            ing_items.append(ing.get("item", "").lower())
        elif isinstance(ing, str):
            ing_items.append(ing.lower())

    cuisine_votes = {}
    for item in ing_items:
        for ing_key, (cuisine, country) in CUISINE_INGREDIENTS.items():
            if ing_key.lower() in item:
                cuisine_votes[cuisine] = cuisine_votes.get(cuisine, 0) + 1

    if cuisine_votes:
        top = max(cuisine_votes, key=cuisine_votes.get)
        for keyword, info in CUISINE_KEYWORDS.items():
            if info["cuisine"].lower() == top.lower():
                return info
        return {"cuisine": top, "region": "International", "country": "International"}

    category = recipe.get("category", "general")
    defaults = {
        "fish": {"cuisine": "Mediterranean", "region": "Mediterranean", "country": "Greece"},
        "seafood": {"cuisine": "Mediterranean", "region": "Mediterranean", "country": "Italy"},
    }
    return defaults.get(category, {"cuisine": "International", "region": "International", "country": "International"})


def compute_tags(recipe):
    """Compute 200+ tags across 20+ dimensions.

    Accepts recipe dicts with either:
    - Structured ingredients: [{"item": "chicken", "grams": 200}, ...]
    - String ingredients: ["200g chicken breast", ...]
    """
    cal = recipe.get("calories", 0)
    prot = recipe.get("protein", 0)
    carbs = recipe.get("carbs", 0)
    fat = recipe.get("fat", 0)
    fiber = recipe.get("fiber", 0)
    sugar = recipe.get("sugar", 0)
    total_time = recipe.get("total_time_min", 0)
    prep_time = recipe.get("prep_time_min", 0)
    cook_time = recipe.get("cook_time_min", 0)
    servings = recipe.get("servings", 1) or 1
    allergens = set(recipe.get("allergens", []))
    category = recipe.get("category", "general")
    name_lower = recipe.get("name", "").lower()
    meal_type = recipe.get("meal_type", "any")

    # Build ingredient string for keyword matching
    ingredients = recipe.get("ingredients", [])
    ing_items = []
    total_grams = 0
    for ing in ingredients:
        if isinstance(ing, dict):
            ing_items.append(ing.get("item", "").lower())
            total_grams += ing.get("grams", 100)
        elif isinstance(ing, str):
            ing_items.append(ing.lower())
            total_grams += 100  # estimate per string ingredient
    ing_str = " ".join(ing_items)

    equipment = recipe.get("equipment", [])
    equip = [e.lower() for e in equipment] if equipment else []

    total_macro_cal = max((prot * 4) + (carbs * 4) + (fat * 9), 1)
    prot_pct = (prot * 4) / total_macro_cal * 100
    carb_pct = (carbs * 4) / total_macro_cal * 100
    fat_pct = (fat * 9) / total_macro_cal * 100

    tags = {}

    # --- 1. GOAL-BASED ---
    goal = []
    if prot >= 30 and cal <= 500: goal.append("cutting")
    if prot >= 25 and cal <= 600: goal.append("fat_loss")
    if cal >= 500 and prot >= 30: goal.append("bulking")
    if cal >= 600 and prot >= 35: goal.append("lean_bulk")
    if 400 <= cal <= 600 and prot >= 25: goal.append("maintenance")
    if 25 <= prot_pct <= 40 and 30 <= carb_pct <= 50: goal.append("recomp")
    if carbs >= 40 and prot >= 20 and fat <= 15: goal.append("pre_workout")
    if prot >= 30 and carbs >= 20: goal.append("post_workout")
    if prot >= 35: goal.append("muscle_building")
    if carbs >= 50 and cal >= 450: goal.append("endurance_fuel")
    if prot >= 40 and cal <= 400: goal.append("competition_prep")
    if cal >= 550: goal.append("off_season")
    if cal >= 600 and prot >= 30 and carbs >= 40: goal.append("aggressive_bulk")
    if prot >= 25 and 350 <= cal <= 500: goal.append("reverse_diet")
    tags["goal"] = goal

    # --- 2. TIMING ---
    timing = []
    if total_time <= 10: timing.append("under_10_min")
    if total_time <= 15: timing.append("under_15_min")
    if total_time <= 20: timing.append("under_20_min")
    if total_time <= 30: timing.append("under_30_min")
    if total_time <= 45: timing.append("under_45_min")
    if total_time <= 60: timing.append("under_60_min")
    if total_time > 60: timing.append("over_60_min")
    if total_time > 120: timing.append("slow_cook")
    if prep_time <= 5: timing.append("minimal_prep")
    if prep_time <= 10: timing.append("quick_prep")
    if cook_time == 0: timing.append("no_cook")
    if cook_time <= 10: timing.append("flash_cook")
    if cook_time <= 15: timing.append("quick_cook")
    if cook_time >= 60: timing.append("long_cook")
    tags["timing"] = timing

    # --- 3. COOKING STYLE ---
    style = []
    if len(equip) <= 1: style.append("one_pan")
    if "wok" in equip: style.append("wok_cooking")
    if "grill" in equip or "grill pan" in equip: style.append("grilling")
    if any(e in equip for e in ["oven", "baking dish", "sheet pan"]): style.append("oven_baking")
    if "dutch oven" in equip: style.append("dutch_oven")
    if "sheet pan" in equip: style.append("sheet_pan")
    if recipe.get("meal_prep_friendly"): style.append("batch_cook")
    if recipe.get("meal_prep_friendly"): style.append("meal_prep")
    if cook_time == 0: style.append("raw")
    if total_time > 120: style.append("slow_cooked")

    for method in ["grilled", "baked", "roasted", "steamed", "poached", "braised",
                   "seared", "pan-seared", "stir-fried", "blackened", "smoked",
                   "air-fried", "broiled", "crusted"]:
        if method in name_lower:
            style.append(method.replace("-", "_"))
    tags["cooking_style"] = list(set(style))

    # --- 4. LIFESTYLE ---
    lifestyle = []
    if total_time <= 30 and len(equip) <= 2: lifestyle.append("weeknight_quick")
    if total_time > 60: lifestyle.append("weekend_project")
    if recipe.get("meal_prep_friendly") and servings >= 4: lifestyle.append("office_lunch")
    if recipe.get("meal_prep_friendly"): lifestyle.append("freezer_friendly")
    if recipe.get("meal_prep_friendly"): lifestyle.append("leftover_friendly")
    if servings <= 2 and total_time <= 30: lifestyle.append("solo_cooking")
    if servings >= 4: lifestyle.append("family_friendly")
    if servings >= 6: lifestyle.append("party_batch")
    if category in ["fish", "seafood"] or "steak" in name_lower: lifestyle.append("date_night")
    if total_time <= 15: lifestyle.append("desk_meal")
    if cook_time == 0 or (total_time <= 20 and len(equip) <= 1): lifestyle.append("travel_friendly")
    tags["lifestyle"] = lifestyle

    # --- 5. MACRO PROFILE ---
    macro_profile = []
    if 25 <= prot_pct <= 35 and 35 <= carb_pct <= 50 and 20 <= fat_pct <= 35: macro_profile.append("balanced_macros")
    if carb_pct >= 55 and fat_pct <= 25: macro_profile.append("high_carb_low_fat")
    if fat_pct >= 50 and carb_pct <= 20: macro_profile.append("high_fat_low_carb")
    if 20 <= prot < 30: macro_profile.append("moderate_protein")
    if prot >= 30: macro_profile.append("high_protein")
    if prot >= 40: macro_profile.append("very_high_protein")
    if prot >= 50: macro_profile.append("ultra_high_protein")
    if fat <= 5: macro_profile.append("very_low_fat")
    if fat <= 10: macro_profile.append("low_fat")
    if carbs <= 10: macro_profile.append("very_low_carb")
    if carbs <= 20: macro_profile.append("low_carb")
    if sugar <= 3: macro_profile.append("very_low_sugar")
    if sugar <= 5: macro_profile.append("low_sugar")
    if sugar >= 15: macro_profile.append("high_sugar")
    if fiber >= 5: macro_profile.append("good_fiber")
    if fiber >= 8: macro_profile.append("high_fiber")
    if fiber >= 12: macro_profile.append("very_high_fiber")
    if cal <= 200: macro_profile.append("very_low_calorie")
    if cal <= 300: macro_profile.append("low_calorie")
    if cal <= 400: macro_profile.append("moderate_calorie")
    if cal >= 500: macro_profile.append("high_calorie")
    if cal >= 700: macro_profile.append("very_high_calorie")
    if prot_pct >= 40: macro_profile.append("protein_dominant")
    if carb_pct >= 55: macro_profile.append("carb_dominant")
    if fat_pct >= 50: macro_profile.append("fat_dominant")
    if carbs <= 15 and fat_pct >= 60: macro_profile.append("keto_friendly")
    tags["macro_profile"] = macro_profile

    # --- 6. CALORIE BRACKET ---
    if cal < 200: tags["calorie_bracket"] = "under_200"
    elif cal < 300: tags["calorie_bracket"] = "200_to_300"
    elif cal < 400: tags["calorie_bracket"] = "300_to_400"
    elif cal < 500: tags["calorie_bracket"] = "400_to_500"
    elif cal < 600: tags["calorie_bracket"] = "500_to_600"
    elif cal < 700: tags["calorie_bracket"] = "600_to_700"
    else: tags["calorie_bracket"] = "700_plus"

    # --- 7. PROTEIN BRACKET ---
    if prot < 10: tags["protein_bracket"] = "under_10g"
    elif prot < 20: tags["protein_bracket"] = "10_to_20g"
    elif prot < 30: tags["protein_bracket"] = "20_to_30g"
    elif prot < 40: tags["protein_bracket"] = "30_to_40g"
    elif prot < 50: tags["protein_bracket"] = "40_to_50g"
    else: tags["protein_bracket"] = "50g_plus"

    # --- 8. MICRONUTRIENT ESTIMATES ---
    micro = []
    if any(x in ing_str for x in ["spinach", "lentil", "beef", "lamb", "tofu", "tempeh", "seitan", "kale", "quinoa"]): micro.append("iron_rich")
    if any(x in ing_str for x in ["salmon", "mackerel", "sardine", "chia", "flax", "hemp", "walnut"]): micro.append("omega_3_rich")
    if any(x in ing_str for x in ["cheese", "yogurt", "milk", "kale", "tofu", "almond"]): micro.append("calcium_rich")
    if any(x in ing_str for x in ["bell pepper", "lemon", "lime", "orange", "tomato", "broccoli", "kale", "strawberr"]): micro.append("vitamin_c_rich")
    if any(x in ing_str for x in ["beef", "lamb", "shrimp", "pumpkin seed", "chickpea", "lentil"]): micro.append("zinc_rich")
    if any(x in ing_str for x in ["spinach", "almond", "cashew", "quinoa", "black bean", "avocado", "dark chocolate"]): micro.append("magnesium_rich")
    if any(x in ing_str for x in ["chicken", "turkey", "salmon", "tuna", "egg", "nutritional yeast"]): micro.append("b_vitamin_rich")
    if any(x in ing_str for x in ["sweet potato", "carrot", "spinach", "kale", "butternut"]): micro.append("vitamin_a_rich")
    if any(x in ing_str for x in ["banana", "sweet potato", "potato", "avocado", "spinach", "bean"]): micro.append("potassium_rich")
    if any(x in ing_str for x in ["berr", "turmeric", "ginger", "garlic", "spinach", "kale", "beet", "tomato", "pomegranate"]): micro.append("antioxidant_rich")
    if any(x in ing_str for x in ["yogurt", "miso", "tempeh", "kimchi", "sauerkraut"]): micro.append("probiotic")
    if any(x in ing_str for x in ["garlic", "onion", "leek", "asparagus", "banana", "oat"]): micro.append("prebiotic")
    if any(x in ing_str for x in ["bone broth", "chicken skin", "pork skin"]): micro.append("collagen_source")
    tags["micronutrients"] = micro

    # --- 9. HEALTH BENEFIT ---
    health = []
    if "omega_3_rich" in micro and fat_pct <= 45: health.append("heart_healthy")
    if sugar <= 8 and fiber >= 3: health.append("blood_sugar_friendly")
    if "calcium_rich" in micro: health.append("bone_health")
    if "omega_3_rich" in micro or any(x in ing_str for x in ["walnut", "blueberr", "salmon", "avocado"]): health.append("brain_food")
    if "vitamin_c_rich" in micro or "antioxidant_rich" in micro: health.append("immune_boosting")
    if prot >= 25 and "iron_rich" in micro: health.append("recovery_focused")
    if any(x in ing_str for x in ["turmeric", "ginger", "salmon", "olive oil", "berr"]): health.append("anti_inflammatory")
    if "probiotic" in micro or "prebiotic" in micro: health.append("gut_friendly")
    if "vitamin_c_rich" in micro or "omega_3_rich" in micro or "antioxidant_rich" in micro: health.append("skin_health")
    if any(x in ing_str for x in ["cucumber", "watermelon", "zucchini", "lettuce", "celery"]): health.append("hydrating")
    if any(x in ing_str for x in ["banana", "potato", "coconut", "spinach"]): health.append("electrolyte_rich")
    if fat <= 15 and fiber >= 3: health.append("low_cholesterol")
    tags["health"] = health

    # --- 10. DIETARY COMPLIANCE ---
    dietary = list(recipe.get("diet", []))
    if "gluten" not in allergens: dietary.append("gluten_free")
    if "dairy" not in allergens: dietary.append("dairy_free")
    if "soy" not in allergens: dietary.append("soy_free")
    if "tree_nuts" not in allergens and "peanuts" not in allergens: dietary.append("nut_free")
    if "egg" not in allergens: dietary.append("egg_free")
    if "shellfish" not in allergens and "fish" not in allergens: dietary.append("seafood_free")
    if "sesame" not in allergens: dietary.append("sesame_free")

    if "gluten" not in allergens and "dairy" not in allergens and sugar <= 5 and \
       not any(x in ing_str for x in ["bean", "lentil", "pea", "corn", "rice", "oat", "quinoa", "soy"]):
        dietary.append("paleo")
    if "gluten" not in allergens and "dairy" not in allergens and sugar <= 3 and \
       not any(x in ing_str for x in ["soy", "corn", "peanut"]):
        dietary.append("whole30_compliant")
    # Pescatarian = eats fish but no other meat. Fish/seafood recipes qualify,
    # as do vegetarian recipes (they're meat-free). Vegan is stricter, skip.
    if category in ["fish", "seafood"]:
        dietary.append("pescatarian")
    elif "vegetarian" in dietary and "vegan" not in dietary:
        dietary.append("pescatarian")
    if any(x in ing_str for x in ["olive oil", "fish", "tomato", "garlic", "lemon"]) and fat_pct <= 45:
        dietary.append("mediterranean_diet")
    if sugar <= 3 and not any(x in ing_str for x in ["honey", "maple", "sugar", "syrup"]):
        dietary.append("refined_sugar_free")
    if category in ["red_meat", "poultry", "fish", "seafood"] and carbs <= 5:
        dietary.append("carnivore_friendly")
    tags["dietary"] = list(set(dietary))

    # --- 11. SATIETY ---
    satiety = []
    if prot >= 25 and fiber >= 5: satiety.append("high_satiety")
    if prot >= 20 and fat >= 10 and fiber >= 3: satiety.append("very_filling")
    if fiber >= 5 or fat >= 15: satiety.append("slow_digesting")
    if carbs >= 30 and fat <= 8: satiety.append("fast_digesting")
    if sugar <= 5 and fiber >= 3: satiety.append("blood_sugar_stable")
    if cal <= 300 and (fiber >= 3 or prot >= 20): satiety.append("light_and_satisfying")
    tags["satiety"] = satiety

    # --- 12. TEXTURE & EXPERIENCE ---
    texture = []
    if any(x in ing_str for x in ["nut", "seed", "crouton", "breadcrumb", "granola"]): texture.append("crunchy")
    if any(x in ing_str for x in ["cream", "yogurt", "avocado", "ricotta", "coconut milk"]): texture.append("creamy")
    if any(x in ing_str for x in ["rice", "pasta", "noodle", "bread"]): texture.append("hearty")
    if any(x in name_lower for x in ["salad", "bowl", "fresh"]): texture.append("light")
    if any(x in name_lower for x in ["soup", "stew", "curry", "brais"]): texture.append("warming")
    if any(x in name_lower for x in ["salad", "poke", "ceviche"]): texture.append("refreshing")
    if any(x in ing_str for x in ["chili", "sriracha", "gochujang", "jalapeño", "harissa", "red pepper flake", "cayenne"]):
        texture.append("spicy")
    else:
        texture.append("mild")
    if any(x in ing_str for x in ["miso", "soy sauce", "mushroom", "parmesan", "tomato paste"]): texture.append("umami")
    if any(x in ing_str for x in ["lemon", "lime", "vinegar"]): texture.append("tangy")
    if any(x in ing_str for x in ["honey", "maple", "fruit", "berr", "banana"]): texture.append("sweet")
    if any(x in name_lower for x in ["crispy", "crusted", "fried", "seared"]): texture.append("crispy")
    tags["texture_experience"] = list(set(texture))

    # --- 13. PROTEIN SOURCE ---
    prot_source = []
    if category == "poultry": prot_source.append("poultry_protein")
    if category == "red_meat": prot_source.append("red_meat_protein")
    if category == "fish": prot_source.append("fish_protein")
    if category == "seafood": prot_source.append("shellfish_protein")
    if category in ("poultry", "red_meat", "fish", "seafood"): prot_source.append("animal_protein")
    if any(x in ing_str for x in ["tofu", "tempeh", "seitan", "bean", "lentil", "chickpea", "edamame", "pea protein"]): prot_source.append("plant_protein")
    if "egg" in ing_str: prot_source.append("egg_protein")
    if any(x in ing_str for x in ["cheese", "yogurt", "milk", "ricotta", "cottage"]): prot_source.append("dairy_protein")
    if any(x in ing_str for x in ["protein powder", "pea protein"]): prot_source.append("supplement_protein")
    if category in ("poultry", "red_meat", "fish", "seafood") or any(x in ing_str for x in ["egg", "quinoa", "soy", "tofu", "tempeh"]):
        prot_source.append("complete_protein")
    if any(x in ing_str for x in ["salmon", "tuna", "mackerel", "sardine"]): prot_source.append("omega_3_protein")
    if any(x in ing_str for x in ["chicken breast", "turkey breast", "cod", "tilapia", "shrimp", "egg white"]): prot_source.append("lean_protein")
    tags["protein_source"] = list(set(prot_source))

    # --- 14. SEASONAL ---
    seasonal = []
    if any(x in ing_str for x in ["asparagus", "pea", "artichoke", "radish", "mint"]): seasonal.append("spring")
    if any(x in ing_str for x in ["tomato", "zucchini", "corn", "bell pepper", "cucumber", "basil", "berry", "mango", "avocado"]): seasonal.append("summer")
    if any(x in ing_str for x in ["pumpkin", "butternut", "apple", "cranberr", "sweet potato", "brussels", "sage"]): seasonal.append("autumn")
    if any(x in ing_str for x in ["root", "potato", "cabbage", "kale", "squash", "citrus", "rosemary"]): seasonal.append("winter")
    if "warming" in texture: seasonal.append("soup_season")
    if "grilling" in style or "grilled" in style: seasonal.append("bbq_season")
    if not seasonal: seasonal.append("year_round")
    tags["seasonal"] = seasonal

    # --- 15. COST ESTIMATE ---
    protein_cost_factor = 1.0
    if category in ("fish", "seafood"): protein_cost_factor = 2.0
    elif category == "red_meat": protein_cost_factor = 1.5
    if any(x in ing_str for x in ["lobster", "scallop", "tenderloin", "ribeye", "duck", "bison", "venison", "swordfish", "halibut", "burrata", "truffle"]):
        protein_cost_factor = 2.5
    est_cost = (total_grams / max(servings, 1) * 0.008) * protein_cost_factor
    if est_cost < 3: tags["cost"] = "budget_friendly"
    elif est_cost < 6: tags["cost"] = "moderate_cost"
    elif est_cost < 10: tags["cost"] = "premium"
    else: tags["cost"] = "luxury"
    tags["est_cost_per_serving"] = str(round(est_cost, 2))

    # --- 16. PORTION SIZE ---
    portion = []
    if servings == 1: portion.append("single_serving")
    if servings == 2: portion.append("couple_sized")
    if servings >= 4: portion.append("family_sized")
    if servings >= 6: portion.append("party_batch")
    if servings <= 2: portion.append("small_batch")
    portion.append("scalable")
    tags["portion"] = portion

    # --- 17. COACHING CONTEXT ---
    coaching = []
    num_ingredients = len(ingredients)
    if total_time <= 20 and num_ingredients <= 8: coaching.append("beginner_cook")
    if num_ingredients <= 6: coaching.append("simple_ingredients")
    if num_ingredients >= 12: coaching.append("complex_recipe")
    if recipe.get("difficulty") == "easy" and total_time <= 30: coaching.append("intro_to_cooking")
    if recipe.get("meal_prep_friendly") and servings >= 4: coaching.append("first_meal_prep")
    if prot >= 30 and cal <= 400: coaching.append("plateau_breaker")
    if prot >= 25 and carbs >= 30 and fiber >= 5: coaching.append("metabolic_boost")
    if cal <= 400 and not any(x in ing_str for x in ["chili", "sriracha", "cayenne", "jalapeño", "coffee", "caffeine"]):
        coaching.append("sleep_friendly")
    if carbs >= 30 and cal >= 350 and meal_type == "breakfast": coaching.append("morning_energy")
    if prot >= 20 and fiber >= 3 and cal <= 400 and meal_type == "lunch": coaching.append("afternoon_slump_buster")
    if cal <= 500 and prot >= 20 and meal_type == "dinner": coaching.append("evening_wind_down")
    if "electrolyte_rich" in health and prot >= 15: coaching.append("hangover_recovery")
    if "warming" in texture and prot >= 15 and "vitamin_c_rich" in micro: coaching.append("sick_day_comfort")
    if fiber >= 5 and prot >= 15 and cal <= 400: coaching.append("stress_eating_redirect")
    if cal <= 300 and prot >= 15: coaching.append("snack_replacement")
    tags["coaching"] = coaching

    # --- 18. INGREDIENT COUNT ---
    tags["ingredient_count"] = str(num_ingredients)
    if num_ingredients <= 5: tags["ingredient_complexity"] = "minimal"
    elif num_ingredients <= 8: tags["ingredient_complexity"] = "simple"
    elif num_ingredients <= 12: tags["ingredient_complexity"] = "moderate"
    else: tags["ingredient_complexity"] = "complex"

    # --- 19. ENERGY DENSITY ---
    total_weight = total_grams / max(servings, 1)
    if total_weight > 0:
        energy_density = cal / (total_weight / 100)
        if energy_density < 100: tags["energy_density"] = "very_low"
        elif energy_density < 200: tags["energy_density"] = "low"
        elif energy_density < 300: tags["energy_density"] = "moderate"
        else: tags["energy_density"] = "high"

    # --- 20. TIME BRACKET ---
    if total_time <= 15: tags["time_bracket"] = "express"
    elif total_time <= 30: tags["time_bracket"] = "quick"
    elif total_time <= 45: tags["time_bracket"] = "standard"
    elif total_time <= 60: tags["time_bracket"] = "involved"
    elif total_time <= 120: tags["time_bracket"] = "lengthy"
    else: tags["time_bracket"] = "project"

    return tags
