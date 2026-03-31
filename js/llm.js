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

      // Gather recent meal history via MealHistory intelligence
      const mealCtx = typeof MealHistory !== 'undefined'
        ? MealHistory.getSuggestionContext(5)
        : { recent_meal_names: [], recent_cuisines: [], recent_protein_sources: [] };
      const recentMealNames = mealCtx.recent_meal_names;
      const recentCuisines = mealCtx.recent_cuisines;
      const recentProteinSources = mealCtx.recent_protein_sources;
      const data = Store.load();
      const todayKey = Store.getTodayKey();

      // Count meals already eaten today to compute adaptive fraction
      const todayMeals = data.logs[todayKey]?.meals || [];
      const mealsEatenToday = todayMeals.length;

      // Workout data with timestamps for pre/post-workout targeting
      const todayWorkoutCals = Store.getTodayWorkoutCalories();
      const todayWorkouts = Store.getTodayWorkouts();
      const now = Date.now();
      const hasRecentWorkout = todayWorkouts.some(w => {
        const wTime = new Date(w.time);
        return (now - wTime.getTime()) < 3 * 60 * 60 * 1000;
      });
      // Detect if there's an upcoming workout (within next 2h) based on patterns
      const hasUpcomingWorkout = todayWorkouts.length === 0 && Store.getTodayWorkoutCalories() === 0;
      // Check yesterday's workout for recovery day detection
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayKey = yesterday.toISOString().split('T')[0];
      const yesterdayWorkouts = Store.getDayWorkouts ? Store.getDayWorkouts(yesterdayKey) : [];
      const isRecoveryDay = yesterdayWorkouts.length > 0 && todayWorkouts.length === 0;

      // Body trend for plateau detection — use more data points
      const bodyLog = Store.getBodyLog();
      let weightTrend = 'stable';
      let weightChangeRate = 0;
      if (bodyLog.length >= 3) {
        const recent = bodyLog.slice(-5);
        const first = recent[0].weight;
        const last = recent[recent.length - 1].weight;
        const diff = last - first;
        const days = Math.max(1, (new Date(recent[recent.length - 1].date) - new Date(recent[0].date)) / 86400000);
        weightChangeRate = (diff / days) * 7; // kg per week
        if (Math.abs(diff) < 0.3 && recent.length >= 3) weightTrend = 'plateau';
        else if (diff > 0) weightTrend = 'gaining';
        else weightTrend = 'losing';
      }

      // Weekly macro averages for trajectory correction
      const weekAvg = Store.getWeekAverage();
      const weeklyMacroTrend = {};
      if (weekAvg && weekAvg.days >= 3) {
        weeklyMacroTrend.avg_calories = weekAvg.calories;
        weeklyMacroTrend.avg_protein = weekAvg.protein;
        weeklyMacroTrend.avg_carbs = weekAvg.carbs;
        weeklyMacroTrend.avg_fat = weekAvg.fat;
        weeklyMacroTrend.days_tracked = weekAvg.days;
        weeklyMacroTrend.target_calories = profile.macros.calories;
        weeklyMacroTrend.target_protein = profile.macros.protein;
        weeklyMacroTrend.target_carbs = profile.macros.carbs;
        weeklyMacroTrend.target_fat = profile.macros.fat;
      }

      // Hydration data
      const todayWater = Store.getWater ? Store.getWater(Store.getTodayKey()) : 0;
      const waterTarget = (profile.weight || 70) * 33; // ml per day

      // User experience level (days with logged meals)
      const allDays = Store.getAllDays();
      const daysWithLogs = allDays.length;

      // Feeling insights — foods that agree/disagree with user
      const feelingInsights = Store.getFeelingInsights();
      let problematicFoods = [];
      let beneficialFoods = [];
      if (feelingInsights) {
        problematicFoods = feelingInsights.problematic.map(p => p.food);
        beneficialFoods = feelingInsights.beneficial.map(p => p.food);
      }

      // Fiber and sugar tracking
      const remainingFull = {
        ...remaining,
        fiber: Math.max(0, 25 - (todayTotals.fiber || 0)),
        sugar_processed: todayTotals.sugar_processed || 0,
        sugar_natural: todayTotals.sugar_natural || 0
      };

      // Time since last meal (hunger signal)
      let minutesSinceLastMeal = null;
      if (todayMeals.length > 0) {
        const lastMeal = todayMeals[todayMeals.length - 1];
        if (lastMeal.time) {
          minutesSinceLastMeal = Math.round((now - new Date(lastMeal.time).getTime()) / 60000);
        }
      }

      const res = await fetch(`${this.backendUrl}/api/recipes/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meal_types: Array.isArray(mealTypes) ? mealTypes : [mealTypes],
          diet_filters: dietFilters || [],
          dietary_preferences: profile.dietaryPreferences?.dietaryStyle || [],
          goal: profile.goal || '',
          remaining: remainingFull,
          liked: prefs.liked || [],
          disliked: prefs.disliked || [],
          hour_of_day: new Date().getHours(),
          day_of_week: new Date().getDay(),
          recent_meal_names: recentMealNames,
          recent_cuisines: recentCuisines,
          recent_protein_sources: recentProteinSources,
          meals_eaten_today: mealsEatenToday,
          health_conditions: profile.healthConditions || [],
          activity_level: profile.activityLevel || 'moderate',
          gender: profile.gender || '',
          age: profile.age || 0,
          pantry: Store.getPantry(),
          workout_calories_today: todayWorkoutCals,
          has_recent_workout: hasRecentWorkout,
          is_recovery_day: isRecoveryDay,
          weight_trend: weightTrend,
          weight_change_rate: weightChangeRate,
          weekly_macro_trend: weeklyMacroTrend,
          water_ml: todayWater,
          water_target_ml: waterTarget,
          days_with_logs: daysWithLogs,
          minutes_since_last_meal: minutesSinceLastMeal,
          problematic_foods: problematicFoods,
          beneficial_foods: beneficialFoods,
          cuisine_frequency: mealCtx.cuisine_frequency || {},
          protein_frequency: mealCtx.protein_frequency || {},
          meal_patterns: mealCtx.patterns || {},
          variety_score: mealCtx.variety_score || 0,
          missing_proteins: mealCtx.missing_proteins || [],
          top_foods: mealCtx.top_foods || [],
        })
      });

      if (!res.ok) return null;
      const result = await res.json();
      if (result.suggestions && result.suggestions.length > 0) {
        return result;
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

  async parseFoodImage(base64Image) {
    const res = await fetch(`${this.backendUrl}/api/recipes/parse-food-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: base64Image })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to analyze food image. Please try again.');
    }
    return await res.json();
  },

  async parseFood(description) {
    const res = await fetch(`${this.backendUrl}/api/recipes/parse-food`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to parse food data. Please try again.');
    }
    return await res.json();
  },

  async getCoachSuggestion(mealTypes, dietFilters = [], customRequest = '') {
    // Try DB-based suggestions first
    const backendResult = await this._tryBackendSuggest(mealTypes, dietFilters, customRequest);
    if (backendResult && backendResult.suggestions && backendResult.suggestions.length > 0) {
      return backendResult;
    }

    // Fallback: generate suggestions via LLM
    const llmResult = await this._tryLLMSuggest(mealTypes, dietFilters, customRequest);
    if (llmResult) return llmResult;

    throw new Error('No recipes available. Add your Anthropic API key in the admin panel.');
  },

  async _tryLLMSuggest(mealTypes, dietFilters, customRequest) {
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
      const mealCtx = typeof MealHistory !== 'undefined'
        ? MealHistory.getSuggestionContext(5)
        : {};

      const res = await fetch(`${this.backendUrl}/api/recipes/suggest-llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meal_types: Array.isArray(mealTypes) ? mealTypes : [mealTypes],
          diet_filters: dietFilters || [],
          dietary_preferences: profile.dietaryPreferences?.dietaryStyle || [],
          goal: profile.goal || '',
          remaining,
          liked: prefs.liked || [],
          disliked: prefs.disliked || [],
          hour_of_day: new Date().getHours(),
          recent_meal_names: mealCtx.recent_meal_names || [],
          recent_cuisines: mealCtx.recent_cuisines || [],
          recent_protein_sources: mealCtx.recent_protein_sources || [],
          meal_patterns: mealCtx.patterns || {},
          top_foods: mealCtx.top_foods || [],
        })
      });

      if (!res.ok) return null;
      const result = await res.json();
      if (result.suggestions && result.suggestions.length > 0) {
        return result;
      }
    } catch {
      // LLM endpoint not available
    }
    return null;
  },

  async generateRecipe(suggestion, dietFilters = []) {
    // Try DB first if we have an ID
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

    // Fallback: generate full recipe via LLM
    return this._generateRecipeLLM(suggestion, dietFilters);
  },

  async _generateRecipeLLM(suggestion, dietFilters) {
    const res = await fetch(`${this.backendUrl}/api/recipes/generate-llm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: suggestion.name,
        calories: suggestion.calories,
        protein: suggestion.protein,
        carbs: suggestion.carbs,
        fat: suggestion.fat,
        cuisine: suggestion.cuisine || '',
        category: suggestion.category || '',
        diet_filters: dietFilters || []
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to generate recipe. Check your LLM configuration.');
    }

    return await res.json();
  },

  async getGapAdvice() {
    const profile = Store.getProfile();
    const totals = Store.getTodayTotals();
    const remaining = {
      calories: Math.max(0, profile.macros.calories - totals.calories),
      protein: Math.max(0, profile.macros.protein - totals.protein),
      carbs: Math.max(0, profile.macros.carbs - totals.carbs),
      fat: Math.max(0, profile.macros.fat - totals.fat)
    };
    const todayMeals = Store.getTodayMeals();
    const mealsLog = todayMeals.map(m => m.description || m.items?.map(i => i.name).join(', ')).join('; ');

    const res = await fetch(`${this.backendUrl}/api/recipes/gap-advice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        remaining,
        totals,
        profile: {
          gender: profile.gender,
          age: profile.age,
          weight: profile.weight,
          unit: profile.unit === 'metric' ? 'kg' : 'lbs',
          goal: profile.goal,
          calories: profile.macros.calories,
          protein: profile.macros.protein,
          carbs: profile.macros.carbs,
          fat: profile.macros.fat,
        },
        meals_log: mealsLog,
        hour: new Date().getHours(),
        health_conditions: profile.healthConditions || [],
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to get advice. Please try again.');
    }
    return await res.json();
  }
};
