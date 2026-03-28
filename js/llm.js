const LLM = {
  // Backend API base URL (empty = same origin)
  backendUrl: '',

  // Try to fetch suggestions from the backend recipe database first
  async _tryBackendSuggest(mealTypes, dietFilters, customRequest) {
    try {
      const profile = Store.getProfile();
      const todayTotals = Store.getTodayTotals();
      const remaining = {
        calories: Math.max(0, profile.macros.calories - todayTotals.calories),
        protein: Math.max(0, profile.macros.protein - todayTotals.protein),
        carbs: Math.max(0, profile.macros.carbs - todayTotals.carbs),
        fat: Math.max(0, profile.macros.fat - todayTotals.fat)
      };
      const prefs = Store.getPreferences();

      const res = await fetch(`${this.backendUrl}/api/recipes/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meal_types: Array.isArray(mealTypes) ? mealTypes : [mealTypes],
          diet_filters: dietFilters || [],
          goal: profile.goal || '',
          remaining,
          liked: prefs.liked || [],
          disliked: prefs.disliked || []
        })
      });

      if (!res.ok) return null;
      const data = await res.json();
      if (data.suggestions && data.suggestions.length > 0) {
        return data;
      }
    } catch {
      // Backend not available, fall through to LLM
    }
    return null;
  },

  // Fetch a full recipe from the backend database by ID
  async _fetchBackendRecipe(recipeId) {
    try {
      const res = await fetch(`${this.backendUrl}/api/recipes/${recipeId}`);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  async call(messages, profile, maxTokens = 1500) {
    if (profile.apiProvider === 'anthropic') {
      return this._callClaude(messages, profile.apiKey, maxTokens);
    }
    return this._callOpenAI(messages, profile.apiKey, maxTokens);
  },

  async _callOpenAI(messages, apiKey, maxTokens = 1500) {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages,
        temperature: 0.3,
        max_tokens: maxTokens
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `OpenAI API error: ${res.status}`);
    }

    const data = await res.json();
    return data.choices[0].message.content;
  },

  async _callClaude(messages, apiKey, maxTokens = 1500) {
    const systemMsg = messages.find(m => m.role === 'system')?.content || '';
    const userMsgs = messages.filter(m => m.role !== 'system');

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true'
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: maxTokens,
        system: systemMsg,
        messages: userMsgs.map(m => ({ role: m.role, content: m.content }))
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `Claude API error: ${res.status}`);
    }

    const data = await res.json();
    return data.content[0].text;
  },

  async parseFoodImage(base64Image) {
    const profile = Store.getProfile();
    if (!profile.apiKey) throw new Error('Please set your API key in Settings');

    const systemPrompt = `You are a nutrition expert. Analyze the food in this image and estimate macros for each item you can see.
Reply with ONLY valid JSON in this exact format, no other text:
{
  "items": [
    {"name": "food name", "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar_natural": 0, "sugar_processed": 0, "fiber": 0}
  ],
  "total": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar_natural": 0, "sugar_processed": 0, "fiber": 0}
}
Rules:
- Identify ALL food items visible in the image
- Estimate portion sizes visually
- Be accurate with calorie and macro estimates
- Round all numbers to integers
- If you can't identify something, make your best estimate and note it in the name
- sugar_natural = sugars from fruit, dairy, honey, whole foods
- sugar_processed = sugars from added/refined sources (white sugar, HFCS, syrups, candy, soda, packaged foods)
- If unsure, classify as processed`;

    let response;
    if (profile.apiProvider === 'anthropic') {
      const mediaType = base64Image.startsWith('/9j/') ? 'image/jpeg' : 'image/png';
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': profile.apiKey,
          'anthropic-version': '2023-06-01',
          'anthropic-dangerous-direct-browser-access': 'true'
        },
        body: JSON.stringify({
          model: 'claude-haiku-4-5-20251001',
          max_tokens: 1500,
          system: systemPrompt,
          messages: [{
            role: 'user',
            content: [
              { type: 'image', source: { type: 'base64', media_type: mediaType, data: base64Image } },
              { type: 'text', text: 'Analyze this food image and estimate the macros for everything you see.' }
            ]
          }]
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error?.message || `Claude API error: ${res.status}`);
      }
      const data = await res.json();
      response = data.content[0].text;
    } else {
      const res = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${profile.apiKey}`
        },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: [
              { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${base64Image}` } },
              { type: 'text', text: 'Analyze this food image and estimate the macros for everything you see.' }
            ]}
          ],
          temperature: 0.3,
          max_tokens: 1500
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error?.message || `OpenAI API error: ${res.status}`);
      }
      const data = await res.json();
      response = data.choices[0].message.content;
    }

    const cleaned = response.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    try {
      const parsed = JSON.parse(cleaned);
      if (!parsed.items || !Array.isArray(parsed.items)) throw new Error('Invalid format');
      parsed.total = parsed.items.reduce((acc, item) => ({
        calories: acc.calories + (item.calories || 0),
        protein: acc.protein + (item.protein || 0),
        carbs: acc.carbs + (item.carbs || 0),
        fat: acc.fat + (item.fat || 0),
        sugar_natural: acc.sugar_natural + (item.sugar_natural || 0),
        sugar_processed: acc.sugar_processed + (item.sugar_processed || 0),
        fiber: acc.fiber + (item.fiber || 0)
      }), { calories: 0, protein: 0, carbs: 0, fat: 0, sugar_natural: 0, sugar_processed: 0, fiber: 0 });
      return parsed;
    } catch {
      throw new Error('Failed to analyze food image. Please try again.');
    }
  },

  async parseFood(description) {
    const profile = Store.getProfile();
    if (!profile.apiKey) throw new Error('Please set your API key in Settings');

    const messages = [
      {
        role: 'system',
        content: `You are a nutrition expert. Parse the user's food description into individual items with estimated macros.
Reply with ONLY valid JSON in this exact format, no other text:
{
  "items": [
    {"name": "food name", "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar_natural": 0, "sugar_processed": 0, "fiber": 0}
  ],
  "total": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar_natural": 0, "sugar_processed": 0, "fiber": 0}
}
Rules:
- Estimate portions if not specified (use typical serving sizes)
- Be accurate with calorie and macro estimates based on standard nutritional data
- Round all numbers to integers
- Include ALL items mentioned
- If a quantity is mentioned, calculate for that quantity
- sugar_natural = sugars from fruit, dairy, honey, whole foods
- sugar_processed = sugars from added/refined sources (white sugar, HFCS, syrups, candy, soda, packaged foods)
- If unsure, classify as processed`
      },
      {
        role: 'user',
        content: description
      }
    ];

    const response = await this.call(messages, profile);
    const cleaned = response.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

    try {
      const parsed = JSON.parse(cleaned);
      if (!parsed.items || !Array.isArray(parsed.items)) throw new Error('Invalid format');
      // Recalculate total from items
      parsed.total = parsed.items.reduce((acc, item) => ({
        calories: acc.calories + (item.calories || 0),
        protein: acc.protein + (item.protein || 0),
        carbs: acc.carbs + (item.carbs || 0),
        fat: acc.fat + (item.fat || 0),
        sugar_natural: acc.sugar_natural + (item.sugar_natural || 0),
        sugar_processed: acc.sugar_processed + (item.sugar_processed || 0),
        fiber: acc.fiber + (item.fiber || 0)
      }), { calories: 0, protein: 0, carbs: 0, fat: 0, sugar_natural: 0, sugar_processed: 0, fiber: 0 });
      return parsed;
    } catch {
      throw new Error('Failed to parse food data. Please try again.');
    }
  },

  async getCoachSuggestion(mealTypes, dietFilters = [], customRequest = '') {
    // Try backend database first (no API key needed)
    const backendResult = await this._tryBackendSuggest(mealTypes, dietFilters, customRequest);
    if (backendResult) return backendResult;

    // Fallback to LLM generation
    const profile = Store.getProfile();
    if (!profile.apiKey) throw new Error('Please set your API key in Settings');

    const todayTotals = Store.getTodayTotals();
    const todayMeals = Store.getTodayMeals();
    const weekAvg = Store.getWeekAverage();
    const prefs = Store.getPreferences();
    const remaining = {
      calories: Math.max(0, profile.macros.calories - todayTotals.calories),
      protein: Math.max(0, profile.macros.protein - todayTotals.protein),
      carbs: Math.max(0, profile.macros.carbs - todayTotals.carbs),
      fat: Math.max(0, profile.macros.fat - todayTotals.fat)
    };

    const mealTypeLabels = {
      breakfast: 'breakfast',
      lunch: 'lunch',
      snack: 'snack',
      dinner: 'dinner',
      pre_workout: 'pre-workout meal',
      post_workout: 'post-workout meal'
    };
    // Support both single string and array
    const types = Array.isArray(mealTypes) ? mealTypes : [mealTypes];
    const mealLabel = types.map(t => mealTypeLabels[t] || t).join(' + ');

    const goalDescriptions = {
      fat_loss: 'losing fat while preserving muscle. Prioritize protein and satiety.',
      aggressive_fat_loss: 'aggressive fat loss. Very high protein, low-calorie dense foods.',
      muscle_gain: 'building muscle. Ensure adequate protein and caloric surplus.',
      lean_bulk: 'lean bulking. Clean calorie surplus with high protein.',
      maintain: 'maintaining current weight. Balanced nutrition.',
      recomp: 'body recomposition. High protein, slight deficit, nutrient timing matters.'
    };

    const mealsLog = todayMeals.map(m => m.description || m.items?.map(i => i.name).join(', ')).join('; ');

    // Build recent history (last 3 days, excluding today) for variety
    const recentHistory = [];
    for (let i = 1; i <= 3; i++) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const dayMeals = Store.getDayMeals(key);
      if (dayMeals.length > 0) {
        const foods = dayMeals.map(m => m.description || m.items?.map(it => it.name).join(', ')).join('; ');
        recentHistory.push(`${key}: ${foods}`);
      }
    }

    let prefsText = '';
    if (prefs.liked.length > 0) {
      prefsText += `\nFoods the client LIKES (prefer these or similar): ${prefs.liked.join(', ')}`;
    }
    if (prefs.disliked.length > 0) {
      prefsText += `\nFoods the client DISLIKES (NEVER suggest these or very similar dishes): ${prefs.disliked.join(', ')}`;
    }

    const dietFilterLabels = {
      vegan: 'Vegan (no animal products)',
      vegetarian: 'Vegetarian (no meat/fish)',
      keto: 'Keto (very low carb, high fat)',
      low_carb: 'Low Carb',
      high_protein: 'High Protein focus',
      paleo: 'Paleo (no grains, dairy, legumes)',
      gluten_free: 'Gluten Free',
      dairy_free: 'Dairy Free',
      mediterranean: 'Mediterranean diet style',
      whole30: 'Whole30 compliant'
    };

    let dietText = '';
    const filters = Array.isArray(dietFilters) ? dietFilters : [];
    if (filters.length > 0) {
      dietText = `\nDietary requirements (MUST follow): ${filters.map(f => dietFilterLabels[f] || f).join(', ')}`;
    }

    let customText = '';
    if (customRequest) {
      customText = `\nAdditional client request: ${customRequest}`;
    }

    const healthLabels = {
      diabetes_t2: 'Type 2 Diabetes (low glycemic, limit sugar/refined carbs, steady blood sugar)',
      diabetes_t1: 'Type 1 Diabetes (consistent carb portions, low glycemic)',
      prediabetes: 'Prediabetes (reduce sugar, favor complex carbs, high fiber)',
      insulin_resistance: 'Insulin Resistance (low glycemic, minimize refined carbs/sugar, high fiber)',
      high_cholesterol: 'High Cholesterol (limit saturated fat, no trans fat, favor omega-3, high fiber)',
      high_triglycerides: 'High Triglycerides (limit sugar/alcohol/refined carbs, omega-3 rich)',
      high_blood_pressure: 'High Blood Pressure (low sodium <1500mg/day, DASH diet principles, potassium-rich foods)',
      heart_disease: 'Heart Disease (heart-healthy fats, low sodium, high fiber, omega-3)',
      pcos: 'PCOS (anti-inflammatory, low glycemic, balanced insulin response)',
      hypothyroid: 'Hypothyroidism (selenium, zinc, avoid excess soy/cruciferous raw, iodine-aware)',
      hyperthyroid: 'Hyperthyroidism (calcium-rich, calorie-dense, avoid excess iodine)',
      hashimoto: "Hashimoto's (anti-inflammatory, gluten-aware, selenium-rich, avoid excess iodine)",
      ibs: 'IBS (low FODMAP friendly, easy to digest, avoid common triggers)',
      ibd_crohn: "Crohn's Disease (low residue during flares, easy to digest, avoid high fiber raw foods during flares)",
      ibd_colitis: 'Ulcerative Colitis (low residue during flares, avoid dairy if trigger, cooked vegetables preferred)',
      celiac: 'Celiac Disease (strictly gluten-free, no wheat/barley/rye)',
      kidney_disease: 'Kidney Disease (limit sodium, potassium, phosphorus; moderate protein)',
      gout: 'Gout (low purine, limit red meat/organ meats/shellfish, hydration focus)',
      anemia: 'Iron Deficiency Anemia (iron-rich foods, vitamin C for absorption, avoid calcium with iron meals)',
      b12_deficiency: 'B12 Deficiency (B12-rich foods: meat, fish, eggs, fortified foods)',
      osteoporosis: 'Osteoporosis (calcium-rich, vitamin D, magnesium, limit caffeine/sodium)',
      lactose_intolerant: 'Lactose Intolerant (dairy-free or lactose-free alternatives)',
      fatty_liver: 'Fatty Liver (no alcohol, low sugar/fructose, high fiber, healthy fats)',
      acid_reflux: 'Acid Reflux/GERD (avoid spicy, citrus, tomato, caffeine, fatty fried foods; smaller portions)',
      gallbladder: 'Gallbladder Issues (low fat meals, avoid fried/greasy foods, small frequent meals)',
      food_allergies: 'Food Allergies (carefully avoid all allergens, check ingredients)',
      nut_allergy: 'Nut Allergy (strictly no tree nuts or peanuts in any form)',
      shellfish_allergy: 'Shellfish Allergy (no shrimp, crab, lobster, mussels, clams)',
      egg_allergy: 'Egg Allergy (no eggs or egg-containing ingredients)',
      soy_allergy: 'Soy Allergy (no soy, tofu, tempeh, soy sauce, edamame)',
      arthritis: 'Arthritis (anti-inflammatory: omega-3, turmeric, avoid excess sugar/processed foods)',
      fibromyalgia: 'Fibromyalgia (anti-inflammatory, magnesium-rich, avoid artificial sweeteners/MSG)',
      endometriosis: 'Endometriosis (anti-inflammatory, omega-3, limit red meat/dairy, favor vegetables)',
      sleep_apnea: 'Sleep Apnea (weight management focus, anti-inflammatory, avoid heavy late meals)',
      anxiety_depression: 'Anxiety/Depression (omega-3, magnesium, B vitamins, gut-friendly, limit caffeine/sugar)',
      migraine: 'Migraines (avoid triggers: aged cheese, alcohol, MSG, nitrates; magnesium-rich)',
      autoimmune: 'Autoimmune Disorder (anti-inflammatory, consider AIP protocol, avoid processed foods)',
    };

    let healthText = '';
    const conditions = profile.healthConditions || [];
    if (conditions.length > 0) {
      healthText = `\nHEALTH CONDITIONS (CRITICAL - meals MUST be safe and beneficial for these):\n${conditions.map(c => '- ' + (healthLabels[c] || c + ' (tailor diet to be safe and beneficial for this condition)')).join('\n')}`;
    }

    const messages = [
      {
        role: 'system',
        content: `You are an elite fitness nutrition coach. Your client has specific goals, macro targets, dietary needs, and food preferences you MUST respect.
Reply with ONLY valid JSON in this exact format:
{
  "top_pick_reason": "2-3 sentence explanation of why option #1 is the BEST choice for this client right now, referencing their specific remaining macros, goal, and recent meals",
  "suggestions": [
    {
      "rank": 1,
      "name": "Meal name",
      "description": "Brief description with portions",
      "why": "One sentence on why this ranks here",
      "calories": 0, "protein": 0, "carbs": 0, "fat": 0
    }
  ]
}
Rules:
- Suggest exactly 5 options covering: ${mealLabel}
- RANK them 1-5 by how well they fit the client's current needs (remaining macros, goal, variety, preferences)
- #1 = best pick right now. Include a clear "why" for each option explaining its ranking
- The top_pick_reason should be personal and specific: reference actual numbers (e.g. "You still need 45g protein and only have 300cal left, so this lean option is ideal")
- Each suggestion should help hit remaining macro targets
- STRICTLY follow any dietary requirements (vegan, keto, etc.) - never violate them
- NEVER suggest foods the client has marked as disliked or very similar alternatives
- Favor foods similar to what the client has liked in the past
- Be specific with portions (e.g., "200g chicken breast" not just "chicken")
- Prioritize whole foods and practical meals
- Consider the client's gender and age for nutritional needs (e.g., iron for women, calcium considerations, age-appropriate portions)
- AVOID repeating meals the client ate in the last few days - suggest VARIETY
- If the client had fish recently, suggest other protein sources. Same for any repeated food.
- Tailor suggestions to the selected meal types: ${mealLabel}
- If multiple meal types are selected, distribute options across types
- If the client has health conditions, EVERY suggestion MUST be safe and beneficial for those conditions. This is non-negotiable.
- For diabetes: favor low glycemic foods. For high cholesterol: limit saturated fat. For high BP: keep sodium very low. Etc.
- Honor any additional custom instructions from the client`
      },
      {
        role: 'user',
        content: `Client profile:
- Gender: ${profile.gender}, Age: ${profile.age}
- Goal: ${goalDescriptions[profile.goal] || 'general fitness'}
- Weight: ${profile.weight}${profile.unit === 'metric' ? 'kg' : 'lbs'}, Height: ${profile.height}${profile.unit === 'metric' ? 'cm' : 'in'}
- Daily targets: ${profile.macros.calories}cal / ${profile.macros.protein}g protein / ${profile.macros.carbs}g carbs / ${profile.macros.fat}g fat

Today so far:
- Eaten: ${todayTotals.calories}cal / ${todayTotals.protein}g P / ${todayTotals.carbs}g C / ${todayTotals.fat}g F
- Remaining: ${remaining.calories}cal / ${remaining.protein}g P / ${remaining.carbs}g C / ${remaining.fat}g F
- Meals eaten today: ${mealsLog || 'Nothing yet'}
${weekAvg ? `- 7-day average: ${weekAvg.calories}cal / ${weekAvg.protein}g P / ${weekAvg.carbs}g C / ${weekAvg.fat}g F` : ''}
${recentHistory.length > 0 ? `\nRecent meals (DO NOT repeat these - suggest variety):\n${recentHistory.join('\n')}` : ''}
${prefsText}${dietText}${healthText}${customText}

Suggest the best ${mealLabel} options to help hit remaining targets. Ensure variety from recent meals, respect all dietary requirements, health conditions, and preferences.`
      }
    ];

    const response = await this.call(messages, profile);
    const cleaned = response.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

    try {
      return JSON.parse(cleaned);
    } catch {
      throw new Error('Failed to get suggestions. Please try again.');
    }
  },

  async generateRecipe(suggestion, dietFilters = []) {
    // If suggestion came from backend DB, fetch the full recipe directly
    if (suggestion.id && suggestion.has_recipe) {
      const dbRecipe = await this._fetchBackendRecipe(suggestion.id);
      if (dbRecipe) {
        return {
          name: dbRecipe.name,
          prep_time: `${dbRecipe.prep_time_min || 0} min`,
          cook_time: `${dbRecipe.cook_time_min || 0} min`,
          servings: String(dbRecipe.servings || 1),
          ingredients: dbRecipe.ingredients || [],
          steps: dbRecipe.steps || [],
          tips: dbRecipe.tips || '',
          calories: dbRecipe.calories,
          protein: dbRecipe.protein,
          carbs: dbRecipe.carbs,
          fat: dbRecipe.fat
        };
      }
    }

    // Fallback to LLM generation
    const profile = Store.getProfile();
    if (!profile.apiKey) throw new Error('Please set your API key in Settings');

    const dietText = dietFilters.length > 0
      ? `\nDietary requirements (MUST follow): ${dietFilters.join(', ')}`
      : '';

    const messages = [
      {
        role: 'system',
        content: `You are a professional chef and fitness nutrition coach. Generate a detailed recipe.
Reply with ONLY valid JSON in this exact format:
{
  "name": "Recipe name",
  "prep_time": "10 min",
  "cook_time": "20 min",
  "servings": "1",
  "ingredients": ["200g chicken breast", "1 tbsp olive oil", "..."],
  "steps": ["Step 1 description", "Step 2 description", "..."],
  "tips": "Optional coach tip about this meal for fitness goals",
  "calories": 0, "protein": 0, "carbs": 0, "fat": 0
}
Rules:
- Use exact gram/ml measurements for ingredients
- Keep steps clear and concise
- Include all seasonings and cooking details
- Macros must match the original suggestion closely
- Respect all dietary restrictions${dietText}`
      },
      {
        role: 'user',
        content: `Generate a full recipe for: ${suggestion.name}
Description: ${suggestion.description}
Target macros: ${suggestion.calories} cal / ${suggestion.protein}g protein / ${suggestion.carbs}g carbs / ${suggestion.fat}g fat`
      }
    ];

    const response = await this.call(messages, profile, 2000);
    const cleaned = response.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

    try {
      return JSON.parse(cleaned);
    } catch {
      throw new Error('Failed to generate recipe. Please try again.');
    }
  },

  async getGapAdvice() {
    const profile = Store.getProfile();
    if (!profile.apiKey) throw new Error('Please set your API key in Settings');

    const totals = Store.getTodayTotals();
    const remaining = {
      calories: Math.max(0, profile.macros.calories - totals.calories),
      protein: Math.max(0, profile.macros.protein - totals.protein),
      carbs: Math.max(0, profile.macros.carbs - totals.carbs),
      fat: Math.max(0, profile.macros.fat - totals.fat)
    };
    const todayMeals = Store.getTodayMeals();
    const mealsLog = todayMeals.map(m => m.description || m.items?.map(i => i.name).join(', ')).join('; ');

    const hour = new Date().getHours();
    const conditions = profile.healthConditions || [];
    let healthNote = '';
    if (conditions.length > 0) {
      healthNote = `\nHealth conditions: ${conditions.join(', ')}. All suggestions must be safe for these.`;
    }

    const messages = [
      {
        role: 'system',
        content: `You are an elite sports nutritionist. The client has macro gaps to fill before the day ends. Suggest a mix of whole food quick options AND supplement options (protein shakes, bars, etc.) to close the gap efficiently.
Reply with ONLY valid JSON, no other text:
{
  "assessment": "1-2 sentence personalized assessment of their current gap situation and urgency",
  "options": [
    {
      "type": "supplement",
      "name": "Option name",
      "description": "Specific product/food with exact portions",
      "calories": 0, "protein": 0, "carbs": 0, "fat": 0,
      "tip": "Optional pro tip"
    }
  ]
}
The "type" field MUST be exactly "supplement" or "food" (no other values).
Rules:
- Provide exactly 5 options, mix of supplements (shakes, bars, powders, BCAAs) and whole foods (quick options like Greek yogurt, eggs, cottage cheese, jerky, etc.)
- Order from most practical/efficient to least
- Be specific: "1 scoop whey isolate (30g) in 250ml water" not just "protein shake"
- For supplements: mention common types (whey, casein, plant-based, collagen) and when each is best
- Consider time of day: late evening = casein, post-workout = whey, etc.
- If client is vegan/dairy-free, suggest plant-based alternatives
- Factor in remaining calorie budget - don't suggest options that blow the calorie target
- If protein gap is small (<15g), suggest food over supplements${healthNote}`
      },
      {
        role: 'user',
        content: `Client: ${profile.gender}, ${profile.age}yo, ${profile.weight}${profile.unit === 'metric' ? 'kg' : 'lbs'}, Goal: ${profile.goal}
Daily targets: ${profile.macros.calories}cal / ${profile.macros.protein}g P / ${profile.macros.carbs}g C / ${profile.macros.fat}g F
Eaten so far: ${totals.calories}cal / ${totals.protein}g P / ${totals.carbs}g C / ${totals.fat}g F
Remaining: ${remaining.calories}cal / ${remaining.protein}g P / ${remaining.carbs}g C / ${remaining.fat}g F
Meals today: ${mealsLog || 'Nothing yet'}
Time now: ${hour}:00

How should they fill the remaining macro gaps most efficiently?`
      }
    ];

    const response = await this.call(messages, profile, 2000);
    const cleaned = response.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

    try {
      return JSON.parse(cleaned);
    } catch {
      throw new Error('Failed to get advice. Please try again.');
    }
  }
};
