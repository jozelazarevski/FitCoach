const LLM = {
  // Backend API base URL (empty = same origin)
  backendUrl: '',
  _backendAvailable: null,

  // Check if the backend server is running
  async checkBackend() {
    if (this._backendAvailable !== null) return this._backendAvailable;
    try {
      const res = await fetch(`${this.backendUrl}/api/health`, { signal: AbortSignal.timeout(2000) });
      if (res.ok) {
        const data = await res.json();
        this._backendAvailable = data.status === 'ok';
        return this._backendAvailable;
      }
    } catch {}
    this._backendAvailable = false;
    return false;
  },

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
    const backendResult = await this._tryBackendSuggest(mealTypes, dietFilters, customRequest);
    if (backendResult) return backendResult;
    throw new Error('No matching recipes found in the database. Try adding more recipes via the admin panel or adjusting your filters.');
  },

  async generateRecipe(suggestion, dietFilters = []) {
    if (suggestion.id) {
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
    throw new Error('Recipe not found in database. Add more recipes via the admin panel.');
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
