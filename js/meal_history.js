/**
 * Meal History Intelligence
 *
 * Analyzes past meal logs to extract patterns and enrich suggestions:
 * 1. Extract cuisine and protein source from meal names/items
 * 2. Compute meal frequency and patterns (by meal type, time of day)
 * 3. Detect nutritional gaps over time (e.g. consistently low protein at breakfast)
 * 4. Surface top/repeat meals and variety metrics
 */
const MealHistory = {

  _CUISINE_KEYWORDS: {
    italian: ['pasta', 'pizza', 'risotto', 'lasagna', 'pesto', 'marinara', 'parmesan', 'prosciutto', 'bruschetta', 'gnocchi', 'tiramisu'],
    mexican: ['burrito', 'taco', 'enchilada', 'quesadilla', 'salsa', 'guacamole', 'fajita', 'nacho', 'chimichanga', 'tamale', 'mole'],
    thai: ['pad thai', 'curry', 'tom yum', 'satay', 'basil chicken', 'green curry', 'red curry', 'panang', 'pad see ew', 'larb', 'sticky rice'],
    japanese: ['sushi', 'ramen', 'teriyaki', 'miso', 'tempura', 'udon', 'soba', 'onigiri', 'gyoza', 'katsu', 'poke', 'edamame'],
    indian: ['tikka', 'masala', 'biryani', 'naan', 'samosa', 'paneer', 'dal', 'tandoori', 'vindaloo', 'korma', 'chutney', 'roti'],
    chinese: ['stir fry', 'dumpling', 'fried rice', 'kung pao', 'wonton', 'chow mein', 'lo mein', 'szechuan', 'dim sum', 'mapo tofu'],
    korean: ['bibimbap', 'kimchi', 'bulgogi', 'gochujang', 'japchae', 'tteokbokki', 'kimbap', 'galbi'],
    greek: ['gyro', 'souvlaki', 'tzatziki', 'feta', 'moussaka', 'spanakopita', 'baklava', 'hummus', 'pita'],
    mediterranean: ['hummus', 'falafel', 'shawarma', 'tabbouleh', 'couscous', 'olive oil', 'grilled halloumi'],
    american: ['burger', 'hot dog', 'bbq', 'mac and cheese', 'buffalo wings', 'cornbread', 'coleslaw', 'brisket'],
    french: ['croissant', 'quiche', 'crepe', 'ratatouille', 'coq au vin', 'baguette', 'bechamel', 'brioche'],
  },

  _PROTEIN_KEYWORDS: {
    chicken: ['chicken', 'poultry', 'wing', 'thigh', 'breast'],
    beef: ['beef', 'steak', 'burger', 'brisket', 'sirloin', 'ground beef', 'meatball'],
    pork: ['pork', 'bacon', 'ham', 'sausage', 'prosciutto', 'chorizo'],
    fish: ['salmon', 'tuna', 'cod', 'tilapia', 'halibut', 'trout', 'sardine', 'mackerel', 'fish'],
    seafood: ['shrimp', 'prawn', 'crab', 'lobster', 'scallop', 'mussel', 'oyster', 'calamari'],
    turkey: ['turkey'],
    eggs: ['egg', 'omelette', 'frittata', 'scramble'],
    tofu: ['tofu', 'tempeh', 'seitan', 'edamame'],
    legumes: ['lentil', 'chickpea', 'black bean', 'kidney bean', 'hummus', 'falafel', 'dal'],
    dairy: ['yogurt', 'cottage cheese', 'cheese', 'whey', 'casein', 'protein shake'],
  },

  /**
   * Analyze the last N days of meals and return structured history.
   */
  analyze(numDays = 7) {
    const today = new Date();
    const meals = [];

    for (let i = 0; i < numDays; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const dayMeals = Store.getDayMeals(key);
      const dayTotals = Store.getDayTotals(key);
      const hour = i === 0 ? new Date().getHours() : null;

      dayMeals.forEach(m => {
        const text = this._mealText(m);
        meals.push({
          date: key,
          daysAgo: i,
          text,
          items: m.items || [],
          total: m.total || {},
          time: m.time,
          cuisines: this._detectCuisines(text),
          proteins: this._detectProteins(text),
          mealType: this._guessMealType(m.time),
        });
      });
    }

    return {
      meals,
      recentNames: meals.map(m => m.text),
      recentCuisines: this._flatten(meals.map(m => m.cuisines)),
      recentProteins: this._flatten(meals.map(m => m.proteins)),
      cuisineFrequency: this._frequency(this._flatten(meals.map(m => m.cuisines))),
      proteinFrequency: this._frequency(this._flatten(meals.map(m => m.proteins))),
      foodFrequency: this._foodFrequency(meals),
      patterns: this._analyzePatterns(meals, numDays),
      variety: this._varietyScore(meals),
    };
  },

  /**
   * Get enriched context for the suggestion engine.
   */
  getSuggestionContext(numDays = 5) {
    const analysis = this.analyze(numDays);
    const profile = Store.getProfile();
    const targets = profile.macros;

    return {
      recent_meal_names: analysis.recentNames.slice(0, 20),
      recent_cuisines: analysis.recentCuisines.slice(0, 15),
      recent_protein_sources: analysis.recentProteins.slice(0, 15),
      cuisine_frequency: analysis.cuisineFrequency,
      protein_frequency: analysis.proteinFrequency,
      patterns: analysis.patterns,
      variety_score: analysis.variety,
      top_foods: Object.entries(analysis.foodFrequency)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([name, count]) => ({ name, count })),
      // Identify what's been missing
      missing_proteins: this._findMissing(analysis.proteinFrequency, ['chicken', 'fish', 'eggs', 'legumes', 'dairy']),
      missing_cuisines: this._findMissing(analysis.cuisineFrequency, ['italian', 'mexican', 'asian', 'mediterranean']),
    };
  },

  _mealText(meal) {
    const desc = meal.description || '';
    const itemNames = (meal.items || []).map(i => i.name || '').join(' ');
    return (desc + ' ' + itemNames).toLowerCase().trim();
  },

  _detectCuisines(text) {
    const found = [];
    for (const [cuisine, keywords] of Object.entries(this._CUISINE_KEYWORDS)) {
      if (keywords.some(k => text.includes(k))) {
        found.push(cuisine);
      }
    }
    return found;
  },

  _detectProteins(text) {
    const found = [];
    for (const [source, keywords] of Object.entries(this._PROTEIN_KEYWORDS)) {
      if (keywords.some(k => text.includes(k))) {
        found.push(source);
      }
    }
    return found;
  },

  _guessMealType(timeStr) {
    if (!timeStr) return 'unknown';
    const h = new Date(timeStr).getHours();
    if (h < 10) return 'breakfast';
    if (h < 14) return 'lunch';
    if (h < 17) return 'snack';
    return 'dinner';
  },

  _flatten(arrays) {
    return arrays.reduce((acc, a) => acc.concat(a), []);
  },

  _frequency(items) {
    const counts = {};
    items.forEach(i => { counts[i] = (counts[i] || 0) + 1; });
    return counts;
  },

  _foodFrequency(meals) {
    const counts = {};
    meals.forEach(m => {
      (m.items || []).forEach(item => {
        const name = (item.name || '').toLowerCase().trim();
        if (name && name.length > 2) counts[name] = (counts[name] || 0) + 1;
      });
    });
    return counts;
  },

  _findMissing(frequency, expectedSources) {
    return expectedSources.filter(s => !frequency[s] || frequency[s] < 1);
  },

  _varietyScore(meals) {
    if (meals.length === 0) return 0;
    const uniqueFoods = new Set();
    const uniqueCuisines = new Set();
    const uniqueProteins = new Set();
    meals.forEach(m => {
      m.items.forEach(i => { if (i.name) uniqueFoods.add(i.name.toLowerCase().trim()); });
      m.cuisines.forEach(c => uniqueCuisines.add(c));
      m.proteins.forEach(p => uniqueProteins.add(p));
    });
    // Score 0-100: combo of unique foods, cuisines, proteins relative to meal count
    const foodRatio = Math.min(uniqueFoods.size / Math.max(meals.length, 1), 1);
    const cuisineScore = Math.min(uniqueCuisines.size / 4, 1) * 30;
    const proteinScore = Math.min(uniqueProteins.size / 4, 1) * 30;
    const foodScore = foodRatio * 40;
    return Math.round(foodScore + cuisineScore + proteinScore);
  },

  /**
   * Analyze patterns: per-meal-type macro averages, protein gaps, etc.
   */
  _analyzePatterns(meals, numDays) {
    const patterns = {
      by_meal_type: {},
      insights: [],
    };

    // Group by meal type
    const groups = {};
    meals.forEach(m => {
      const type = m.mealType;
      if (!groups[type]) groups[type] = [];
      groups[type].push(m);
    });

    const profile = Store.getProfile();
    const targets = profile.macros;

    for (const [type, typeMeals] of Object.entries(groups)) {
      const avgCal = typeMeals.reduce((s, m) => s + (m.total.calories || 0), 0) / typeMeals.length;
      const avgProt = typeMeals.reduce((s, m) => s + (m.total.protein || 0), 0) / typeMeals.length;
      const avgCarbs = typeMeals.reduce((s, m) => s + (m.total.carbs || 0), 0) / typeMeals.length;
      const avgFat = typeMeals.reduce((s, m) => s + (m.total.fat || 0), 0) / typeMeals.length;

      patterns.by_meal_type[type] = {
        count: typeMeals.length,
        avg_calories: Math.round(avgCal),
        avg_protein: Math.round(avgProt),
        avg_carbs: Math.round(avgCarbs),
        avg_fat: Math.round(avgFat),
      };

      // Detect low-protein meals
      if (avgProt < 15 && typeMeals.length >= 2) {
        patterns.insights.push({
          type: 'low_protein',
          meal_type: type,
          message: `Your ${type} meals average only ${Math.round(avgProt)}g protein. Try adding eggs, Greek yogurt, or chicken.`,
        });
      }

      // Detect high-calorie meals
      if (targets.calories && avgCal > targets.calories * 0.5 && typeMeals.length >= 2) {
        patterns.insights.push({
          type: 'high_calories',
          meal_type: type,
          message: `${type.charAt(0).toUpperCase() + type.slice(1)} averages ${Math.round(avgCal)} cal (${Math.round(avgCal / targets.calories * 100)}% of daily target).`,
        });
      }
    }

    // Detect same-food repetition
    const foodCounts = this._foodFrequency(meals);
    const repeated = Object.entries(foodCounts).filter(([_, c]) => c >= 3).sort((a, b) => b[1] - a[1]);
    if (repeated.length > 0) {
      patterns.insights.push({
        type: 'repetition',
        message: `You've eaten "${repeated[0][0]}" ${repeated[0][1]} times in ${numDays} days. Try mixing it up for better nutrient variety.`,
        foods: repeated.slice(0, 3).map(([name, count]) => ({ name, count })),
      });
    }

    // Detect missing meal types
    const expectedTypes = ['breakfast', 'lunch', 'dinner'];
    const loggedTypes = new Set(Object.keys(groups));
    const missing = expectedTypes.filter(t => !loggedTypes.has(t));
    if (missing.length > 0 && meals.length >= 3) {
      patterns.insights.push({
        type: 'missing_meals',
        message: `No ${missing.join(' or ')} logged recently. Spreading meals across the day improves energy and metabolism.`,
      });
    }

    return patterns;
  },

  /**
   * Render a compact meal history insights card for the dashboard.
   */
  renderInsightsCard() {
    const analysis = this.analyze(7);
    const { patterns, variety, cuisineFrequency, proteinFrequency } = analysis;

    if (analysis.meals.length < 3) return '';

    const insights = patterns.insights || [];
    if (insights.length === 0 && variety > 60) return '';

    return `
      <div class="card meal-history-card">
        <div class="card-title">Meal Intelligence</div>

        <div class="mh-variety-row">
          <div class="mh-variety-score">
            <div class="mh-variety-ring" style="--variety-pct:${variety}">
              <span>${variety}</span>
            </div>
            <div class="mh-variety-label">Variety Score</div>
          </div>
          <div class="mh-variety-breakdown">
            ${Object.entries(proteinFrequency).length > 0 ? `
              <div class="mh-mini-label">Protein sources this week</div>
              <div class="mh-tags">
                ${Object.entries(proteinFrequency).sort((a,b) => b[1] - a[1]).slice(0, 6).map(([p, c]) =>
                  `<span class="mh-tag">${p} <small>${c}x</small></span>`
                ).join('')}
              </div>
            ` : ''}
            ${Object.entries(cuisineFrequency).length > 0 ? `
              <div class="mh-mini-label" style="margin-top:6px">Cuisines</div>
              <div class="mh-tags">
                ${Object.entries(cuisineFrequency).sort((a,b) => b[1] - a[1]).slice(0, 5).map(([c, n]) =>
                  `<span class="mh-tag">${c} <small>${n}x</small></span>`
                ).join('')}
              </div>
            ` : ''}
          </div>
        </div>

        ${insights.length > 0 ? `
          <div class="mh-insights">
            ${insights.slice(0, 3).map(i => `
              <div class="mh-insight mh-insight-${i.type}">
                <span class="mh-insight-icon">${
                  i.type === 'low_protein' ? '&#9888;' :
                  i.type === 'high_calories' ? '&#128200;' :
                  i.type === 'repetition' ? '&#128260;' :
                  i.type === 'missing_meals' ? '&#128197;' : '&#128161;'
                }</span>
                ${i.message}
              </div>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  },
};
