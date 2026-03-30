const RecipeDB = {
  db: null,
  ready: false,
  _initPromise: null,

  async init() {
    if (this.ready) return;
    if (this._initPromise) return this._initPromise;
    this._initPromise = this._doInit();
    return this._initPromise;
  },

  async _doInit() {
    try {
      const SQL = await initSqlJs({
        locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`
      });
      const response = await fetch('data/recipes.db');
      if (!response.ok) throw new Error('Failed to load recipe database');
      const buffer = await response.arrayBuffer();
      this.db = new SQL.Database(new Uint8Array(buffer));
      this.ready = true;
    } catch (err) {
      this._initPromise = null;
      throw err;
    }
  },

  _transformRow(row) {
    const splitPipe = (val) => val ? val.split('|').map(s => s.trim()).filter(Boolean) : [];

    const items = splitPipe(row.ingredients_items);
    const amounts = splitPipe(row.ingredients_amounts);
    const grams = splitPipe(row.ingredients_grams);
    const ingredients = items.map((item, i) => ({
      item,
      amount: amounts[i] || '',
      grams: grams[i] || ''
    }));

    const steps = [];
    for (let i = 1; i <= 7; i++) {
      const step = row[`step_${i}`];
      if (step) steps.push(step);
    }

    return {
      id: row.id,
      name: row.name,
      cuisine: row.cuisine,
      category: row.category,
      meal_type: row.meal_type,
      difficulty: row.difficulty,
      prep_time_min: row.prep_time_min,
      cook_time_min: row.cook_time_min,
      total_time_min: row.total_time_min,
      servings: row.servings,
      calories: row.calories,
      protein_g: row.protein_g,
      carbs_g: row.carbs_g,
      fat_g: row.fat_g,
      fiber_g: row.fiber_g,
      sugar_g: row.sugar_g,
      description: row.description,
      tips: row.tips,
      meal_prep_friendly: row.meal_prep_friendly === 1,
      allergens: splitPipe(row.allergens),
      diet: splitPipe(row.diet),
      equipment: splitPipe(row.equipment),
      ingredients,
      steps,
      tag_goal: splitPipe(row.tag_goal),
      tag_cooking_style: splitPipe(row.tag_cooking_style),
      tag_lifestyle: splitPipe(row.tag_lifestyle),
      tag_micronutrients: splitPipe(row.tag_micronutrients),
      tag_health: splitPipe(row.tag_health),
      tag_dietary: splitPipe(row.tag_dietary),
      tag_satiety: splitPipe(row.tag_satiety),
      tag_texture: splitPipe(row.tag_texture),
      tag_protein_source: splitPipe(row.tag_protein_source),
      tag_seasonal: splitPipe(row.tag_seasonal),
      tag_coaching: splitPipe(row.tag_coaching)
    };
  },

  _queryRows(sql, params) {
    const stmt = this.db.prepare(sql);
    if (params) stmt.bind(params);
    const rows = [];
    const cols = stmt.getColumnNames();
    while (stmt.step()) {
      const vals = stmt.get();
      const row = {};
      cols.forEach((c, i) => row[c] = vals[i]);
      rows.push(row);
    }
    stmt.free();
    return rows;
  },

  getRecipeById(id) {
    const rows = this._queryRows('SELECT * FROM recipes WHERE id = ?', [id]);
    return rows.length > 0 ? this._transformRow(rows[0]) : null;
  },

  getDistinctValues(column) {
    const allowed = ['cuisine', 'meal_type', 'difficulty', 'category'];
    if (!allowed.includes(column)) return [];
    const rows = this._queryRows(`SELECT DISTINCT ${column} FROM recipes WHERE ${column} != '' ORDER BY ${column}`);
    return rows.map(r => r[column]);
  },

  searchRecipes(filters = {}) {
    const conditions = [];
    const params = [];

    if (filters.mealTypes && filters.mealTypes.length > 0) {
      conditions.push(`meal_type IN (${filters.mealTypes.map(() => '?').join(',')})`);
      params.push(...filters.mealTypes);
    }

    if (filters.dietFilters && filters.dietFilters.length > 0) {
      for (const diet of filters.dietFilters) {
        conditions.push(`diet LIKE '%' || ? || '%'`);
        params.push(diet);
      }
    }

    if (filters.cuisine) {
      conditions.push('cuisine = ?');
      params.push(filters.cuisine);
    }

    if (filters.maxCalories) {
      conditions.push('calories <= ?');
      params.push(filters.maxCalories);
    }

    if (filters.minProtein) {
      conditions.push('protein_g >= ?');
      params.push(filters.minProtein);
    }

    if (filters.maxCarbs) {
      conditions.push('carbs_g <= ?');
      params.push(filters.maxCarbs);
    }

    if (filters.maxFat) {
      conditions.push('fat_g <= ?');
      params.push(filters.maxFat);
    }

    if (filters.difficulty) {
      conditions.push('difficulty = ?');
      params.push(filters.difficulty);
    }

    if (filters.maxTime) {
      conditions.push('total_time_min <= ?');
      params.push(filters.maxTime);
    }

    if (filters.textSearch) {
      conditions.push(`(name LIKE '%' || ? || '%' OR description LIKE '%' || ? || '%' OR ingredients_items LIKE '%' || ? || '%')`);
      params.push(filters.textSearch, filters.textSearch, filters.textSearch);
    }

    if (filters.excludeAllergens && filters.excludeAllergens.length > 0) {
      for (const allergen of filters.excludeAllergens) {
        conditions.push(`(allergens NOT LIKE '%' || ? || '%' OR allergens = '')`);
        params.push(allergen);
      }
    }

    if (filters.tagGoal) {
      conditions.push(`tag_goal LIKE '%' || ? || '%'`);
      params.push(filters.tagGoal);
    }

    const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';
    const limit = filters.limit || 20;
    const sql = `SELECT * FROM recipes ${where} ORDER BY calories ASC LIMIT ?`;
    params.push(limit);

    const rows = this._queryRows(sql, params);
    return rows.map(r => this._transformRow(r));
  },

  findMacroFit(remaining, filters = {}) {
    // Pre-filter with SQL: get candidates within calorie budget (10% overshoot tolerance)
    const maxCal = Math.round(remaining.calories * 1.1);
    const searchFilters = {
      ...filters,
      maxCalories: maxCal > 0 ? maxCal : 9999,
      limit: 200
    };
    const candidates = this.searchRecipes(searchFilters);

    if (candidates.length === 0) return [];

    // Determine ideal calorie target based on meal type
    const mealTypes = filters.mealTypes || [];
    let calFraction = 0.4; // default
    if (mealTypes.length === 1) {
      const fractions = { breakfast: 0.3, lunch: 0.35, dinner: 0.45, snack: 0.15, pre_workout: 0.15, post_workout: 0.2 };
      calFraction = fractions[mealTypes[0]] || 0.4;
    }
    const idealCal = remaining.calories * calFraction;

    // Score each candidate
    const scored = candidates.map(recipe => {
      const calDiff = Math.abs(recipe.calories - idealCal) / Math.max(idealCal, 1);
      const proteinShortfall = Math.max(0, remaining.protein * calFraction - recipe.protein_g) / Math.max(remaining.protein * calFraction, 1);
      const carbOvershoot = Math.max(0, recipe.carbs_g - remaining.carbs) / Math.max(remaining.carbs, 1);
      const fatOvershoot = Math.max(0, recipe.fat_g - remaining.fat) / Math.max(remaining.fat, 1);

      const score = 1.0 * calDiff + 1.5 * proteinShortfall + 0.8 * carbOvershoot + 0.8 * fatOvershoot;
      return { recipe, score };
    });

    scored.sort((a, b) => a.score - b.score);

    // Take top 10 with cuisine diversity
    const results = [];
    const cuisineCounts = {};
    for (const { recipe } of scored) {
      if (results.length >= 10) break;
      const c = recipe.cuisine;
      cuisineCounts[c] = (cuisineCounts[c] || 0) + 1;
      if (cuisineCounts[c] <= 3) {
        results.push(recipe);
      }
    }

    // If we have fewer than 10 due to diversity filtering, fill from remaining
    if (results.length < 10) {
      const ids = new Set(results.map(r => r.id));
      for (const { recipe } of scored) {
        if (results.length >= 10) break;
        if (!ids.has(recipe.id)) results.push(recipe);
      }
    }

    return results;
  }
};
