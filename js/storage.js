const Store = {
  KEY: 'fitcoach_data',
  _cache: null,
  _cacheRaw: null,

  _defaults() {
    return {
      profile: {
        name: '',
        weight: 0,
        height: 0,
        age: 0,
        gender: 'male',
        activityLevel: 'moderate',
        goal: 'fat_loss',
        tdee: 0,
        macros: { calories: 0, protein: 0, carbs: 0, fat: 0 },
        customMacros: false,
        apiProvider: 'anthropic',
        unit: 'metric',
        healthConditions: [],
        dietaryPreferences: {
          dietaryStyle: [],
          liked: [],
          disliked: []
        }
      },
      logs: {},
      preferences: {
        liked: [],
        disliked: []
      },
      bodyLog: [],
      workouts: {},
      water: {},
      pantry: [],
      mealPlans: {}
    };
  },

  load() {
    try {
      const raw = localStorage.getItem(this.KEY);
      if (!raw) return this._defaults();
      // Return cached version if localStorage hasn't changed
      if (this._cache && raw === this._cacheRaw) return this._cache;
      const data = JSON.parse(raw);
      const defaults = this._defaults();
      this._cache = {
        ...defaults, ...data,
        profile: {
          ...defaults.profile,
          ...data.profile,
          dietaryPreferences: {
            ...defaults.profile.dietaryPreferences,
            ...(data.profile?.dietaryPreferences || {})
          }
        }
      };
      this._cacheRaw = raw;
      return this._cache;
    } catch {
      return this._defaults();
    }
  },

  _syncTimer: null,

  save(data) {
    const raw = JSON.stringify(data);
    localStorage.setItem(this.KEY, raw);
    // Update cache directly — avoid re-parsing on next load()
    this._cache = data;
    this._cacheRaw = raw;
    // Debounced sync to server (5s after last save)
    if (typeof Auth !== 'undefined' && Auth.isLoggedIn()) {
      clearTimeout(this._syncTimer);
      this._syncTimer = setTimeout(() => Auth.syncData(), 5000);
    }
  },

  getProfile() {
    return this.load().profile;
  },

  saveProfile(profile) {
    const data = this.load();
    data.profile = { ...data.profile, ...profile };
    this.save(data);
  },

  getTodayKey() {
    return new Date().toISOString().split('T')[0];
  },

  getTodayMeals() {
    const data = this.load();
    const key = this.getTodayKey();
    return data.logs[key]?.meals || [];
  },

  addMeal(meal, dateKey) {
    const data = this.load();
    const key = dateKey || this.getTodayKey();
    if (!data.logs[key]) data.logs[key] = { meals: [] };

    data.logs[key].meals.push(meal);
    this.save(data);
  },

  deleteMeal(index, dateKey) {
    const data = this.load();
    const key = dateKey || this.getTodayKey();
    if (data.logs[key]?.meals) {
      data.logs[key].meals.splice(index, 1);
      this.save(data);
    }
  },

  getDayMeals(dateKey) {
    const data = this.load();
    return data.logs[dateKey]?.meals || [];
  },

  getAllDays() {
    const data = this.load();
    return Object.keys(data.logs).sort().reverse();
  },

  getDayTotals(dateKey) {
    const meals = this.getDayMeals(dateKey);
    const totals = { calories: 0, protein: 0, carbs: 0, fat: 0, sugar_natural: 0, sugar_processed: 0, fiber: 0 };
    meals.forEach(m => {
      totals.calories += m.total?.calories || 0;
      totals.protein += m.total?.protein || 0;
      totals.carbs += m.total?.carbs || 0;
      totals.fat += m.total?.fat || 0;
      totals.sugar_natural += m.total?.sugar_natural || 0;
      totals.sugar_processed += m.total?.sugar_processed || 0;
      totals.fiber += m.total?.fiber || 0;
    });
    return totals;
  },

  getTodayTotals() {
    return this.getDayTotals(this.getTodayKey());
  },

  exportData() {
    const data = this.load();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fitcoach-backup-${this.getTodayKey()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },

  importData(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => {
        try {
          const data = JSON.parse(e.target.result);
          if (data.profile && data.logs) {
            this.save(data);
            resolve();
          } else {
            reject(new Error('Invalid backup file'));
          }
        } catch {
          reject(new Error('Invalid JSON file'));
        }
      };
      reader.readAsText(file);
    });
  },

  isProfileComplete() {
    const p = this.getProfile();
    return p.weight > 0 && p.height > 0 && p.age > 0;
  },

  getPreferences() {
    const data = this.load();
    return data.preferences || { liked: [], disliked: [] };
  },

  addPreference(type, food) {
    const data = this.load();
    if (!data.preferences) data.preferences = { liked: [], disliked: [] };
    const list = data.preferences[type];
    const normalized = food.toLowerCase().trim();
    if (!list.some(f => f.toLowerCase() === normalized)) {
      list.push(food.trim());
      if (list.length > 50) list.shift();
    }
    // Remove from opposite list if present
    const opposite = type === 'liked' ? 'disliked' : 'liked';
    data.preferences[opposite] = data.preferences[opposite].filter(
      f => f.toLowerCase() !== normalized
    );
    this.save(data);
  },

  removePreference(type, food) {
    const data = this.load();
    if (!data.preferences) return;
    const normalized = food.toLowerCase().trim();
    data.preferences[type] = data.preferences[type].filter(
      f => f.toLowerCase() !== normalized
    );
    this.save(data);
  },

  getWeekAverage() {
    const data = this.load();
    const today = new Date();
    const totals = { calories: 0, protein: 0, carbs: 0, fat: 0, days: 0 };
    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const meals = data.logs[key]?.meals || [];
      if (meals.length > 0) {
        meals.forEach(m => {
          totals.calories += m.total?.calories || 0;
          totals.protein += m.total?.protein || 0;
          totals.carbs += m.total?.carbs || 0;
          totals.fat += m.total?.fat || 0;
        });
        totals.days++;
      }
    }
    if (totals.days === 0) return null;
    return {
      calories: Math.round(totals.calories / totals.days),
      protein: Math.round(totals.protein / totals.days),
      carbs: Math.round(totals.carbs / totals.days),
      fat: Math.round(totals.fat / totals.days),
      days: totals.days
    };
  },

  // === BODY LOG (weight, body fat) ===
  addBodyEntry(entry) {
    const data = this.load();
    if (!data.bodyLog) data.bodyLog = [];
    data.bodyLog.push({ date: this.getTodayKey(), time: new Date().toISOString(), ...entry });
    this.save(data);
  },

  getBodyLog() {
    const data = this.load();
    return (data.bodyLog || []).sort((a, b) => a.date.localeCompare(b.date));
  },

  getLatestBody() {
    const log = this.getBodyLog();
    return log.length > 0 ? log[log.length - 1] : null;
  },

  deleteBodyEntry(index) {
    const data = this.load();
    if (data.bodyLog) { data.bodyLog.splice(index, 1); this.save(data); }
  },

  // === WORKOUTS ===
  addWorkout(workout) {
    const data = this.load();
    if (!data.workouts) data.workouts = {};
    const key = this.getTodayKey();
    if (!data.workouts[key]) data.workouts[key] = [];
    data.workouts[key].push({ time: new Date().toISOString(), ...workout });
    this.save(data);
  },

  getTodayWorkouts() {
    const data = this.load();
    return (data.workouts || {})[this.getTodayKey()] || [];
  },

  getDayWorkouts(dateKey) {
    const data = this.load();
    return (data.workouts || {})[dateKey] || [];
  },

  getTodayWorkoutCalories() {
    return this.getTodayWorkouts().reduce((sum, w) => sum + (w.caloriesBurned || 0), 0);
  },

  deleteWorkout(index) {
    const data = this.load();
    const key = this.getTodayKey();
    if (data.workouts?.[key]) { data.workouts[key].splice(index, 1); this.save(data); }
  },

  // === WATER ===
  getWater(dateKey) {
    const data = this.load();
    return (data.water || {})[dateKey || this.getTodayKey()] || 0;
  },

  addWater(ml) {
    const data = this.load();
    if (!data.water) data.water = {};
    const key = this.getTodayKey();
    data.water[key] = (data.water[key] || 0) + ml;
    this.save(data);
  },

  setWater(ml) {
    const data = this.load();
    if (!data.water) data.water = {};
    data.water[this.getTodayKey()] = Math.max(0, ml);
    this.save(data);
  },

  // === PANTRY ===
  getPantry() {
    const data = this.load();
    return data.pantry || [];
  },

  addPantryItem(item) {
    const data = this.load();
    if (!data.pantry) data.pantry = [];
    const normalized = item.toLowerCase().trim();
    if (!data.pantry.some(p => p.toLowerCase() === normalized)) {
      data.pantry.push(item.trim());
      this.save(data);
    }
  },

  removePantryItem(item) {
    const data = this.load();
    if (!data.pantry) return;
    data.pantry = data.pantry.filter(p => p.toLowerCase() !== item.toLowerCase().trim());
    this.save(data);
  },

  // === MEAL PLANS ===
  saveMealPlan(weekKey, plan) {
    const data = this.load();
    if (!data.mealPlans) data.mealPlans = {};
    data.mealPlans[weekKey] = plan;
    this.save(data);
  },

  getMealPlan(weekKey) {
    const data = this.load();
    return (data.mealPlans || {})[weekKey] || null;
  },

  // === MEAL FEELINGS ===
  addMealFeeling(dateKey, mealIndex, feeling) {
    const data = this.load();
    if (!data.mealFeelings) data.mealFeelings = {};
    if (!data.mealFeelings[dateKey]) data.mealFeelings[dateKey] = {};
    data.mealFeelings[dateKey][mealIndex] = {
      ...feeling,
      timestamp: new Date().toISOString()
    };
    this.save(data);
  },

  getMealFeeling(dateKey, mealIndex) {
    const data = this.load();
    return data.mealFeelings?.[dateKey]?.[mealIndex] || null;
  },

  getDayFeelings(dateKey) {
    const data = this.load();
    return data.mealFeelings?.[dateKey] || {};
  },

  getRecentFeelingPatterns() {
    const data = this.load();
    const feelings = data.mealFeelings || {};
    const patterns = [];
    const today = new Date();

    // Collect last 14 days of feelings paired with meal data
    for (let i = 0; i < 14; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const dayFeelings = feelings[key] || {};
      const dayMeals = data.logs[key]?.meals || [];

      Object.entries(dayFeelings).forEach(([idx, feeling]) => {
        const meal = dayMeals[parseInt(idx)];
        if (meal && feeling) {
          const foods = meal.items?.map(it => it.name.toLowerCase()) || [];
          patterns.push({
            foods,
            energy: feeling.energy,
            digestion: feeling.digestion,
            mood: feeling.mood,
            bloating: feeling.bloating || false,
            description: meal.description || ''
          });
        }
      });
    }
    return patterns;
  },

  getFeelingInsights() {
    const patterns = this.getRecentFeelingPatterns();
    if (patterns.length < 3) return null;

    // Find foods that correlate with negative feelings
    const foodScores = {};
    patterns.forEach(p => {
      const score = (p.energy === 'high' ? 1 : p.energy === 'low' ? -1 : 0) +
                    (p.digestion === 'good' ? 1 : p.digestion === 'bad' ? -1 : 0) +
                    (p.mood === 'good' ? 1 : p.mood === 'bad' ? -1 : 0) +
                    (p.bloating ? -1 : 0);
      p.foods.forEach(food => {
        if (!foodScores[food]) foodScores[food] = { total: 0, count: 0 };
        foodScores[food].total += score;
        foodScores[food].count++;
      });
    });

    const problematic = [];
    const beneficial = [];
    Object.entries(foodScores).forEach(([food, data]) => {
      if (data.count < 2) return;
      const avg = data.total / data.count;
      if (avg <= -0.5) problematic.push({ food, avgScore: avg, count: data.count });
      if (avg >= 0.5) beneficial.push({ food, avgScore: avg, count: data.count });
    });

    problematic.sort((a, b) => a.avgScore - b.avgScore);
    beneficial.sort((a, b) => b.avgScore - a.avgScore);

    return {
      totalEntries: patterns.length,
      problematic: problematic.slice(0, 5),
      beneficial: beneficial.slice(0, 5)
    };
  }
};
