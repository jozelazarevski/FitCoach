"""
Seed the database with a starter set of recipes (no API key needed).
These are hand-crafted recipes covering the major categories, cuisines, and meal types.

Usage:
    python -m backend.seed_recipes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import init_db
from backend.models import insert_recipe, insert_tags
from backend.tag_engine import detect_cuisine, compute_tags

SEED_RECIPES = [
    # === BREAKFAST ===
    {
        "name": "Greek Yogurt Power Bowl with Berries and Granola",
        "description": "High-protein breakfast bowl with Greek yogurt, mixed berries, and crunchy granola",
        "category": "vegetarian", "meal_type": "breakfast", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 0, "total_time_min": 5, "servings": 1,
        "calories": 380, "protein": 28, "carbs": 45, "fat": 10, "fiber": 6, "sugar": 18,
        "ingredients": ["200g Greek yogurt", "80g mixed berries", "30g granola", "1 tbsp honey", "1 tbsp chia seeds", "5 almonds"],
        "steps": ["Add Greek yogurt to a bowl", "Top with mixed berries", "Sprinkle granola and chia seeds", "Drizzle honey and add almonds"],
        "tips": "Swap granola for oats if watching sugar. Add protein powder for 40g+ protein.",
        "equipment": ["bowl"], "allergens": ["dairy", "tree_nuts", "gluten"], "diet": ["vegetarian", "high_protein"],
        "meal_prep_friendly": False
    },
    {
        "name": "Spinach and Feta Egg White Omelette",
        "description": "Light, protein-rich omelette with spinach, feta, and cherry tomatoes",
        "category": "vegetarian", "meal_type": "breakfast", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 8, "total_time_min": 13, "servings": 1,
        "calories": 240, "protein": 30, "carbs": 6, "fat": 10, "fiber": 2, "sugar": 3,
        "ingredients": ["6 egg whites", "30g feta cheese", "50g spinach", "6 cherry tomatoes", "1 tsp olive oil", "salt and pepper"],
        "steps": ["Heat olive oil in non-stick pan", "Sauté spinach until wilted", "Pour in egg whites, cook until edges set", "Add feta and tomatoes, fold and serve"],
        "tips": "Perfect cutting meal - 30g protein under 250 calories.",
        "equipment": ["pan"], "allergens": ["egg", "dairy"], "diet": ["vegetarian", "high_protein", "low_carb", "gluten_free"],
        "meal_prep_friendly": False
    },
    {
        "name": "Overnight Oats with Banana and Peanut Butter",
        "description": "No-cook make-ahead breakfast with oats, banana, and peanut butter",
        "category": "vegetarian", "meal_type": "breakfast", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 0, "total_time_min": 5, "servings": 1,
        "calories": 450, "protein": 18, "carbs": 62, "fat": 16, "fiber": 8, "sugar": 20,
        "ingredients": ["60g rolled oats", "200ml milk", "1 banana", "2 tbsp peanut butter", "1 tbsp chia seeds", "1 tsp cinnamon"],
        "steps": ["Combine oats, milk, chia seeds, and cinnamon in a jar", "Refrigerate overnight (6+ hours)", "Top with sliced banana and peanut butter before serving"],
        "tips": "Great pre-workout breakfast 1-2 hours before training. Complex carbs for sustained energy.",
        "equipment": ["jar"], "allergens": ["dairy", "gluten", "peanuts"], "diet": ["vegetarian"],
        "meal_prep_friendly": True
    },
    {
        "name": "Turkish Menemen (Scrambled Eggs with Peppers)",
        "description": "Turkish-style scrambled eggs with peppers, tomatoes, and spices",
        "category": "vegetarian", "meal_type": "breakfast", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 12, "total_time_min": 17, "servings": 2,
        "calories": 280, "protein": 18, "carbs": 12, "fat": 18, "fiber": 3, "sugar": 6,
        "ingredients": ["4 eggs", "2 tomatoes", "1 green pepper", "1 onion", "2 tbsp olive oil", "1 tsp paprika", "salt and pepper", "fresh parsley"],
        "steps": ["Dice peppers, onions, and tomatoes", "Sauté onions and peppers in olive oil until soft", "Add tomatoes and paprika, cook 5 min", "Crack eggs into the mixture, stir gently until just set", "Garnish with parsley"],
        "tips": "Serve with whole grain bread to add carbs for a complete breakfast.",
        "equipment": ["pan"], "allergens": ["egg"], "diet": ["vegetarian", "gluten_free", "dairy_free"],
        "meal_prep_friendly": False
    },

    # === LUNCH - POULTRY ===
    {
        "name": "Grilled Chicken Caesar Salad Bowl",
        "description": "Classic Caesar salad with grilled chicken breast, parmesan, and homemade dressing",
        "category": "poultry", "meal_type": "lunch", "difficulty": "easy",
        "prep_time_min": 10, "cook_time_min": 12, "total_time_min": 22, "servings": 1,
        "calories": 420, "protein": 42, "carbs": 12, "fat": 22, "fiber": 4, "sugar": 2,
        "ingredients": ["180g chicken breast", "100g romaine lettuce", "20g parmesan cheese", "30g croutons", "1 tbsp olive oil", "1 tbsp lemon juice", "1 tsp Dijon mustard", "1 garlic clove", "salt and pepper"],
        "steps": ["Season chicken with salt, pepper, and olive oil", "Grill chicken 6 min per side until cooked through", "Chop romaine and place in bowl", "Whisk olive oil, lemon juice, mustard, and garlic for dressing", "Slice chicken, place on salad", "Top with parmesan and croutons, drizzle dressing"],
        "tips": "42g protein and filling - ideal for fat loss lunch. Skip croutons for lower carb.",
        "equipment": ["grill pan", "bowl"], "allergens": ["dairy", "gluten"], "diet": ["high_protein"],
        "meal_prep_friendly": True
    },
    {
        "name": "Thai Basil Chicken Stir-Fry",
        "description": "Quick Thai stir-fry with chicken, basil, and chili over jasmine rice",
        "category": "poultry", "meal_type": "lunch", "difficulty": "medium",
        "prep_time_min": 10, "cook_time_min": 12, "total_time_min": 22, "servings": 2,
        "calories": 480, "protein": 36, "carbs": 42, "fat": 16, "fiber": 3, "sugar": 5,
        "ingredients": ["300g chicken thigh", "100g jasmine rice", "2 tbsp soy sauce", "1 tbsp fish sauce", "1 tbsp oyster sauce", "3 garlic cloves", "2 Thai chilis", "1 cup fresh basil", "1 tbsp oil"],
        "steps": ["Cook rice according to package", "Slice chicken into bite-sized pieces", "Heat oil in wok over high heat", "Stir-fry garlic and chilis 30 seconds", "Add chicken, cook 5-6 min until golden", "Add sauces, toss to coat", "Remove from heat, fold in basil leaves", "Serve over rice"],
        "tips": "Balanced macros for maintenance. Use chicken breast for lower fat.",
        "equipment": ["wok", "pot"], "allergens": ["soy", "fish"], "diet": ["dairy_free"],
        "meal_prep_friendly": True
    },
    {
        "name": "Mexican Chicken Burrito Bowl",
        "description": "Loaded burrito bowl with seasoned chicken, black beans, rice, and fresh salsa",
        "category": "poultry", "meal_type": "lunch", "difficulty": "medium",
        "prep_time_min": 15, "cook_time_min": 15, "total_time_min": 30, "servings": 2,
        "calories": 520, "protein": 40, "carbs": 55, "fat": 14, "fiber": 10, "sugar": 4,
        "ingredients": ["250g chicken breast", "100g brown rice", "100g black beans", "1 avocado", "2 tomatoes", "1 lime", "1 tsp cumin", "1 tsp paprika", "1 tsp garlic powder", "50g corn", "fresh cilantro", "salt"],
        "steps": ["Cook rice", "Season chicken with cumin, paprika, garlic powder, and salt", "Grill or pan-fry chicken 6 min per side", "Dice tomatoes, mash half the avocado with lime juice", "Assemble bowls: rice, beans, corn, sliced chicken", "Top with salsa, avocado, and cilantro"],
        "tips": "10g fiber keeps you full. Perfect post-workout with the carb-protein combo.",
        "equipment": ["pan", "pot"], "allergens": [], "diet": ["high_protein", "gluten_free", "dairy_free"],
        "meal_prep_friendly": True
    },

    # === LUNCH - FISH ===
    {
        "name": "Mediterranean Salmon Bowl with Quinoa",
        "description": "Omega-3 rich salmon with quinoa, cucumber, tomatoes, and tahini dressing",
        "category": "fish", "meal_type": "lunch", "difficulty": "medium",
        "prep_time_min": 10, "cook_time_min": 15, "total_time_min": 25, "servings": 1,
        "calories": 520, "protein": 38, "carbs": 40, "fat": 22, "fiber": 6, "sugar": 4,
        "ingredients": ["150g salmon fillet", "80g quinoa", "1 cucumber", "6 cherry tomatoes", "30g kalamata olives", "2 tbsp tahini", "1 lemon", "1 tbsp olive oil", "fresh dill", "salt and pepper"],
        "steps": ["Cook quinoa according to package", "Season salmon with olive oil, salt, pepper", "Pan-sear salmon 4 min per side", "Dice cucumber and halve tomatoes", "Mix tahini with lemon juice and water for dressing", "Assemble bowl: quinoa, vegetables, flaked salmon", "Drizzle tahini dressing and garnish with dill"],
        "tips": "Omega-3 from salmon + complete protein from quinoa. Brain and heart food.",
        "equipment": ["pan", "pot"], "allergens": ["fish", "sesame"], "diet": ["gluten_free", "dairy_free", "high_protein"],
        "meal_prep_friendly": True
    },
    {
        "name": "Japanese Miso-Glazed Cod with Steamed Vegetables",
        "description": "Delicate white fish with sweet miso glaze served with steamed broccoli and rice",
        "category": "fish", "meal_type": "lunch", "difficulty": "medium",
        "prep_time_min": 10, "cook_time_min": 15, "total_time_min": 25, "servings": 1,
        "calories": 380, "protein": 35, "carbs": 38, "fat": 8, "fiber": 4, "sugar": 8,
        "ingredients": ["150g cod fillet", "2 tbsp white miso paste", "1 tbsp mirin", "1 tsp sesame oil", "80g rice", "100g broccoli", "1 tsp sesame seeds", "1 green onion"],
        "steps": ["Mix miso, mirin, and sesame oil into a glaze", "Coat cod in miso glaze, marinate 10 min", "Cook rice and steam broccoli", "Broil cod 4-5 min per side until caramelized", "Plate rice, broccoli, and glazed cod", "Garnish with sesame seeds and green onion"],
        "tips": "Low-fat, high-protein choice perfect for cutting. Only 8g fat.",
        "equipment": ["oven", "pot"], "allergens": ["fish", "soy", "sesame"], "diet": ["high_protein", "dairy_free"],
        "meal_prep_friendly": False
    },

    # === DINNER - RED MEAT ===
    {
        "name": "Korean Bulgogi Beef Rice Bowl",
        "description": "Marinated Korean beef with rice, pickled vegetables, and gochujang",
        "category": "red_meat", "meal_type": "dinner", "difficulty": "medium",
        "prep_time_min": 15, "cook_time_min": 10, "total_time_min": 25, "servings": 2,
        "calories": 550, "protein": 38, "carbs": 52, "fat": 20, "fiber": 3, "sugar": 10,
        "ingredients": ["300g beef sirloin", "100g rice", "3 tbsp soy sauce", "1 tbsp sesame oil", "2 tbsp brown sugar", "3 garlic cloves", "1 tbsp ginger", "1 tbsp gochujang", "1 carrot", "1 cucumber", "sesame seeds", "green onions"],
        "steps": ["Thinly slice beef against the grain", "Mix soy sauce, sesame oil, sugar, garlic, ginger for marinade", "Marinate beef 10+ minutes", "Cook rice", "Quick-pickle carrot and cucumber in rice vinegar", "Sear beef in hot pan 2-3 min per side", "Assemble bowls with rice, beef, pickled veggies", "Top with gochujang, sesame seeds, green onions"],
        "tips": "Great bulking meal. Add an extra rice portion for aggressive bulk.",
        "equipment": ["pan", "pot"], "allergens": ["soy", "sesame"], "diet": ["dairy_free"],
        "meal_prep_friendly": True
    },
    {
        "name": "Italian Herb-Crusted Steak with Roasted Vegetables",
        "description": "Pan-seared steak with Italian herbs, served with roasted sweet potato and broccoli",
        "category": "red_meat", "meal_type": "dinner", "difficulty": "medium",
        "prep_time_min": 10, "cook_time_min": 25, "total_time_min": 35, "servings": 1,
        "calories": 520, "protein": 42, "carbs": 32, "fat": 24, "fiber": 6, "sugar": 8,
        "ingredients": ["200g sirloin steak", "150g sweet potato", "100g broccoli", "1 tbsp olive oil", "1 tsp rosemary", "1 tsp thyme", "2 garlic cloves", "salt and pepper"],
        "steps": ["Preheat oven to 200C", "Cube sweet potato, toss with olive oil and herbs", "Roast sweet potato 20 min, add broccoli last 10 min", "Season steak with rosemary, thyme, garlic, salt, pepper", "Sear steak in hot pan 3-4 min per side for medium-rare", "Rest 5 minutes, slice and serve with roasted vegetables"],
        "tips": "Solid maintenance dinner. Iron and B12 from beef supports recovery.",
        "equipment": ["pan", "oven", "sheet pan"], "allergens": [], "diet": ["gluten_free", "dairy_free", "high_protein", "paleo"],
        "meal_prep_friendly": False
    },

    # === DINNER - VEGAN ===
    {
        "name": "Indian Chickpea Tikka Masala",
        "description": "Creamy spiced chickpea curry with coconut milk, served over basmati rice",
        "category": "vegan", "meal_type": "dinner", "difficulty": "medium",
        "prep_time_min": 10, "cook_time_min": 25, "total_time_min": 35, "servings": 3,
        "calories": 420, "protein": 16, "carbs": 55, "fat": 15, "fiber": 10, "sugar": 6,
        "ingredients": ["400g chickpeas (canned)", "200ml coconut milk", "200g crushed tomatoes", "1 onion", "3 garlic cloves", "1 tbsp ginger", "2 tsp garam masala", "1 tsp turmeric", "1 tsp cumin", "150g basmati rice", "1 tbsp oil", "fresh cilantro"],
        "steps": ["Cook rice", "Sauté onion, garlic, ginger in oil", "Add spices, toast 1 minute", "Add tomatoes and coconut milk, simmer 10 min", "Add drained chickpeas, simmer 10 more min", "Serve over rice, garnish with cilantro"],
        "tips": "High fiber keeps you full. Add tofu for extra protein if bulking.",
        "equipment": ["pot", "pan"], "allergens": [], "diet": ["vegan", "gluten_free", "dairy_free"],
        "meal_prep_friendly": True
    },
    {
        "name": "Black Bean and Sweet Potato Tacos",
        "description": "Mexican-inspired vegan tacos with spiced black beans, roasted sweet potato, and avocado",
        "category": "vegan", "meal_type": "dinner", "difficulty": "easy",
        "prep_time_min": 10, "cook_time_min": 20, "total_time_min": 30, "servings": 2,
        "calories": 440, "protein": 15, "carbs": 60, "fat": 16, "fiber": 14, "sugar": 8,
        "ingredients": ["200g black beans (canned)", "1 large sweet potato", "4 corn tortillas", "1 avocado", "1 lime", "1 tsp cumin", "1 tsp smoked paprika", "1 tbsp olive oil", "fresh cilantro", "hot sauce"],
        "steps": ["Preheat oven to 200C", "Cube sweet potato, toss with oil, cumin, paprika", "Roast 20 min until tender", "Heat black beans with a pinch of cumin", "Warm tortillas", "Assemble: tortilla, beans, sweet potato, sliced avocado", "Squeeze lime, add cilantro and hot sauce"],
        "tips": "14g fiber for great satiety. Perfect weeknight dinner, ready in 30 min.",
        "equipment": ["oven", "sheet pan"], "allergens": [], "diet": ["vegan", "gluten_free", "dairy_free"],
        "meal_prep_friendly": True
    },

    # === SNACKS ===
    {
        "name": "Protein Energy Balls (No-Bake)",
        "description": "Quick no-bake protein balls with oats, peanut butter, and dark chocolate",
        "category": "vegetarian", "meal_type": "snack", "difficulty": "easy",
        "prep_time_min": 10, "cook_time_min": 0, "total_time_min": 10, "servings": 6,
        "calories": 180, "protein": 10, "carbs": 20, "fat": 8, "fiber": 3, "sugar": 8,
        "ingredients": ["100g rolled oats", "60g peanut butter", "40g honey", "30g protein powder", "20g dark chocolate chips", "1 tbsp chia seeds"],
        "steps": ["Mix all ingredients in a bowl until combined", "Refrigerate 15 minutes", "Roll into 12 balls (2 per serving)", "Store in fridge for up to 1 week"],
        "tips": "Perfect pre-workout snack 30-45 min before training. Easy to batch prep.",
        "equipment": ["bowl"], "allergens": ["peanuts", "gluten", "dairy"], "diet": ["vegetarian"],
        "meal_prep_friendly": True
    },
    {
        "name": "Cottage Cheese and Cucumber Bites",
        "description": "High-protein snack with cottage cheese, cucumber, everything bagel seasoning",
        "category": "vegetarian", "meal_type": "snack", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 0, "total_time_min": 5, "servings": 1,
        "calories": 150, "protein": 20, "carbs": 6, "fat": 5, "fiber": 1, "sugar": 4,
        "ingredients": ["150g cottage cheese", "1 cucumber", "1 tsp everything bagel seasoning", "cherry tomatoes"],
        "steps": ["Slice cucumber into rounds", "Top each with a spoonful of cottage cheese", "Sprinkle everything bagel seasoning", "Add halved cherry tomatoes"],
        "tips": "20g protein for 150 cal - incredible protein density for a snack.",
        "equipment": [], "allergens": ["dairy", "sesame"], "diet": ["vegetarian", "high_protein", "gluten_free", "low_carb"],
        "meal_prep_friendly": False
    },

    # === PRE/POST WORKOUT ===
    {
        "name": "Banana Oat Protein Pancakes",
        "description": "Fluffy protein pancakes made with banana, oats, and protein powder",
        "category": "vegetarian", "meal_type": "pre_workout", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 10, "total_time_min": 15, "servings": 1,
        "calories": 420, "protein": 30, "carbs": 55, "fat": 8, "fiber": 5, "sugar": 16,
        "ingredients": ["1 banana", "50g rolled oats", "30g protein powder", "2 egg whites", "1 tsp baking powder", "1 tsp cinnamon", "cooking spray"],
        "steps": ["Blend banana, oats, protein powder, egg whites, baking powder, and cinnamon", "Heat pan with cooking spray over medium heat", "Pour 1/4 cup batter per pancake", "Cook 2-3 min per side until golden", "Serve with a drizzle of honey or fresh berries"],
        "tips": "Perfect 60-90 min before lifting. Complex carbs + protein for sustained energy.",
        "equipment": ["pan", "blender"], "allergens": ["egg", "gluten", "dairy"], "diet": ["vegetarian", "high_protein"],
        "meal_prep_friendly": True
    },
    {
        "name": "Post-Workout Chicken and Rice Recovery Bowl",
        "description": "Simple, fast-digesting chicken and white rice with teriyaki glaze",
        "category": "poultry", "meal_type": "post_workout", "difficulty": "easy",
        "prep_time_min": 5, "cook_time_min": 15, "total_time_min": 20, "servings": 1,
        "calories": 480, "protein": 40, "carbs": 52, "fat": 10, "fiber": 2, "sugar": 8,
        "ingredients": ["180g chicken breast", "120g white rice", "2 tbsp teriyaki sauce", "1 tsp sesame seeds", "50g steamed broccoli", "1 green onion"],
        "steps": ["Cook white rice", "Grill or pan-sear chicken breast", "Steam broccoli", "Slice chicken, arrange over rice with broccoli", "Drizzle teriyaki sauce", "Top with sesame seeds and sliced green onion"],
        "tips": "White rice (fast carbs) + lean chicken = optimal post-workout recovery window meal.",
        "equipment": ["pan", "pot"], "allergens": ["soy", "sesame"], "diet": ["high_protein", "dairy_free"],
        "meal_prep_friendly": True
    },

    # === MORE CUISINES ===
    {
        "name": "Moroccan Lamb Tagine with Couscous",
        "description": "Slow-braised lamb with apricots, almonds, and warm spices over fluffy couscous",
        "category": "red_meat", "meal_type": "dinner", "difficulty": "hard",
        "prep_time_min": 20, "cook_time_min": 90, "total_time_min": 110, "servings": 4,
        "calories": 580, "protein": 35, "carbs": 52, "fat": 24, "fiber": 5, "sugar": 12,
        "ingredients": ["500g lamb shoulder", "100g dried apricots", "30g almonds", "200g couscous", "1 onion", "3 garlic cloves", "2 tsp cumin", "2 tsp cinnamon", "1 tsp turmeric", "400g crushed tomatoes", "2 tbsp olive oil", "fresh mint", "salt and pepper"],
        "steps": ["Cut lamb into chunks, season with spices", "Sear lamb in olive oil until browned", "Add onion and garlic, cook 3 min", "Add tomatoes, apricots, 1 cup water", "Cover and simmer 90 min until lamb is tender", "Prepare couscous with boiling water", "Serve tagine over couscous, top with almonds and mint"],
        "tips": "Weekend project meal. Makes 4 servings - great for meal prep.",
        "equipment": ["dutch oven"], "allergens": ["tree_nuts", "gluten"], "diet": ["dairy_free"],
        "meal_prep_friendly": True
    },
    {
        "name": "Vietnamese Pho with Tofu",
        "description": "Fragrant Vietnamese noodle soup with tofu, fresh herbs, and rice noodles",
        "category": "vegan", "meal_type": "dinner", "difficulty": "medium",
        "prep_time_min": 15, "cook_time_min": 30, "total_time_min": 45, "servings": 2,
        "calories": 350, "protein": 18, "carbs": 45, "fat": 10, "fiber": 4, "sugar": 4,
        "ingredients": ["200g firm tofu", "150g rice noodles", "1L vegetable broth", "2 star anise", "1 cinnamon stick", "3 cloves", "2 tbsp soy sauce", "1 tbsp ginger", "100g bean sprouts", "fresh basil", "1 lime", "1 jalapeño", "hoisin sauce"],
        "steps": ["Toast star anise, cinnamon, and cloves in dry pot", "Add broth, ginger, soy sauce - simmer 20 min", "Press and cube tofu, pan-fry until golden", "Cook rice noodles according to package", "Strain broth, divide noodles into bowls", "Ladle broth over noodles, top with tofu", "Serve with bean sprouts, basil, lime, jalapeño"],
        "tips": "Warming and hydrating. Great for recovery days or when feeling under the weather.",
        "equipment": ["pot", "pan"], "allergens": ["soy", "gluten"], "diet": ["vegan", "dairy_free"],
        "meal_prep_friendly": False
    },
    {
        "name": "Greek Grilled Chicken Souvlaki Plate",
        "description": "Marinated chicken skewers with tzatziki, Greek salad, and warm pita",
        "category": "poultry", "meal_type": "dinner", "difficulty": "medium",
        "prep_time_min": 15, "cook_time_min": 12, "total_time_min": 27, "servings": 2,
        "calories": 480, "protein": 42, "carbs": 30, "fat": 20, "fiber": 3, "sugar": 4,
        "ingredients": ["300g chicken breast", "2 tbsp olive oil", "2 tbsp lemon juice", "2 tsp oregano", "3 garlic cloves", "150g Greek yogurt", "1 cucumber", "1 tomato", "30g feta cheese", "2 pita breads", "red onion", "kalamata olives"],
        "steps": ["Cube chicken, marinate in olive oil, lemon, oregano, garlic", "Make tzatziki: grate cucumber into yogurt, add garlic and dill", "Thread chicken onto skewers", "Grill 3-4 min per side", "Make salad: tomato, cucumber, onion, olives, feta", "Warm pita, serve with skewers, tzatziki, and salad"],
        "tips": "Mediterranean diet classic. Great balance of protein, healthy fats, and carbs.",
        "equipment": ["grill", "bowl"], "allergens": ["dairy", "gluten"], "diet": ["high_protein", "mediterranean"],
        "meal_prep_friendly": True
    },
    {
        "name": "Cajun Shrimp and Cauliflower Rice",
        "description": "Spicy Cajun shrimp over low-carb cauliflower rice with bell peppers",
        "category": "seafood", "meal_type": "dinner", "difficulty": "easy",
        "prep_time_min": 10, "cook_time_min": 12, "total_time_min": 22, "servings": 1,
        "calories": 320, "protein": 35, "carbs": 14, "fat": 14, "fiber": 5, "sugar": 5,
        "ingredients": ["200g shrimp", "200g cauliflower rice", "1 bell pepper", "1 tbsp olive oil", "2 tsp Cajun seasoning", "1 garlic clove", "1 lemon", "fresh parsley"],
        "steps": ["Season shrimp with Cajun seasoning", "Heat oil, sauté bell pepper 3 min", "Add shrimp, cook 2-3 min per side", "In same pan, cook cauliflower rice 4 min", "Plate cauliflower rice, top with shrimp and peppers", "Squeeze lemon, garnish with parsley"],
        "tips": "Only 14g carbs - perfect for keto or low-carb cutting. High protein density.",
        "equipment": ["pan"], "allergens": ["shellfish"], "diet": ["high_protein", "low_carb", "gluten_free", "dairy_free", "keto"],
        "meal_prep_friendly": True
    },
    {
        "name": "Ethiopian Lentil Stew (Misir Wot)",
        "description": "Hearty spiced red lentil stew with berbere spice blend",
        "category": "vegan", "meal_type": "dinner", "difficulty": "easy",
        "prep_time_min": 10, "cook_time_min": 30, "total_time_min": 40, "servings": 4,
        "calories": 310, "protein": 18, "carbs": 48, "fat": 6, "fiber": 12, "sugar": 4,
        "ingredients": ["200g red lentils", "1 onion", "3 garlic cloves", "1 tbsp ginger", "2 tbsp tomato paste", "2 tsp berbere spice", "1 tsp cumin", "1 tsp turmeric", "1 tbsp olive oil", "700ml water", "salt"],
        "steps": ["Sauté diced onion in olive oil until golden", "Add garlic, ginger, cook 1 min", "Add spices and tomato paste, stir 1 min", "Add lentils and water, bring to boil", "Reduce heat, simmer 25-30 min until thick", "Season with salt, serve with injera or rice"],
        "tips": "12g fiber per serving! Budget-friendly plant protein that's freezer-ready.",
        "equipment": ["pot"], "allergens": [], "diet": ["vegan", "gluten_free", "dairy_free"],
        "meal_prep_friendly": True
    },
    {
        "name": "Japanese Teriyaki Salmon with Edamame Rice",
        "description": "Glazed teriyaki salmon with fluffy rice mixed with edamame and sesame",
        "category": "fish", "meal_type": "dinner", "difficulty": "medium",
        "prep_time_min": 10, "cook_time_min": 15, "total_time_min": 25, "servings": 1,
        "calories": 540, "protein": 40, "carbs": 48, "fat": 20, "fiber": 4, "sugar": 10,
        "ingredients": ["150g salmon fillet", "100g rice", "50g edamame", "3 tbsp soy sauce", "2 tbsp mirin", "1 tbsp honey", "1 tsp ginger", "1 tsp sesame seeds", "1 green onion", "1 tsp sesame oil"],
        "steps": ["Cook rice, mix in edamame when done", "Mix soy sauce, mirin, honey, ginger for teriyaki sauce", "Pan-sear salmon skin-side down 4 min", "Flip, pour teriyaki sauce over, cook 3 more min", "Plate edamame rice, top with glazed salmon", "Garnish with sesame seeds and green onion"],
        "tips": "Omega-3 + complete protein. Great for brain health and muscle recovery.",
        "equipment": ["pan", "pot"], "allergens": ["fish", "soy", "sesame"], "diet": ["dairy_free", "high_protein"],
        "meal_prep_friendly": True
    },
]


def seed_database():
    """Insert seed recipes with full tagging."""
    init_db()
    count = 0
    for recipe_data in SEED_RECIPES:
        # Detect cuisine
        cuisine_info = detect_cuisine(recipe_data)
        recipe_data['cuisine'] = cuisine_info['cuisine']
        recipe_data['country_of_origin'] = cuisine_info['country']
        recipe_data['region'] = cuisine_info['region']

        if recipe_data.get('total_time_min', 0) == 0:
            recipe_data['total_time_min'] = recipe_data.get('prep_time_min', 0) + recipe_data.get('cook_time_min', 0)

        recipe_id = insert_recipe(recipe_data)
        tags = compute_tags(recipe_data)
        insert_tags(recipe_id, tags)
        count += 1
        print(f"  [{count}] {recipe_data['name']} -> {cuisine_info['cuisine']} ({len(tags)} tag dimensions)")

    print(f"\nSeeded {count} recipes with full tagging.")
    print("Run 'python app.py' to start the server.")


if __name__ == '__main__':
    seed_database()
