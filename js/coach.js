const Coach = {
  selectedMealTypes: [],
  selectedDietFilters: [],
  selectedCuisine: '',
  selectedDifficulty: '',
  selectedMaxTime: 0,
  customRequest: '',
  lastSuggestions: null,
  lastRecipeResults: null,
  _dbReady: false,

<<<<<<< Updated upstream
=======
  _detectMealType() {
    const hour = new Date().getHours();
    if (hour < 10) return 'breakfast';
    if (hour < 14) return 'lunch';
    if (hour < 17) return 'snack';
    return 'dinner';
  },

  _getCoachInsight(profile, totals, remaining, todayMeals) {
    const hour = new Date().getHours();
    const mealType = this._detectMealType();
    const mealsLeft = mealType === 'dinner' ? 1 : mealType === 'snack' ? 2 : mealType === 'lunch' ? 2 : 3;
    const insights = [];

    // Protein urgency
    if (remaining.protein > 40 && mealsLeft <= 2) {
      insights.push(`You're ${remaining.protein}g short on protein with ${mealsLeft} meal${mealsLeft > 1 ? 's' : ''} left. Prioritize high-protein options.`);
    }

    // Calorie budget
    if (remaining.calories < 300 && mealsLeft >= 2) {
      insights.push(`Only ${remaining.calories} cal left but ${mealsLeft} meals to go. Keep it light - lean protein and veggies.`);
    } else if (remaining.calories > 800 && hour > 17) {
      insights.push(`You have ${remaining.calories} cal still available. A hearty dinner is fine.`);
    }

    // Ate nothing yet
    if (todayMeals.length === 0 && hour > 10) {
      insights.push(`You haven't logged anything yet today. Start with a balanced ${mealType} to fuel up.`);
    }

    // Variety check from week
    const weekMeals = this._getWeekMealNames();
    if (weekMeals.length > 5) {
      const freq = {};
      weekMeals.forEach(n => { freq[n] = (freq[n] || 0) + 1; });
      const repeated = Object.entries(freq).filter(([, c]) => c >= 3).map(([n]) => n);
      if (repeated.length > 0) {
        insights.push(`You've had ${repeated[0]} ${freq[repeated[0]]} times this week. Let's mix it up!`);
      }
    }

    return insights.length > 0 ? insights[0] : `Based on your macros and the time of day, here's what I'd suggest for ${mealType}.`;
  },

  _getWeekMealNames() {
    const names = [];
    const data = Store.load();
    for (let i = 0; i < 7; i++) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const entry = data.logs[key];
      // Handle both formats: array (old) or {meals: [...]} (new)
      const meals = Array.isArray(entry) ? entry : (entry?.meals || []);
      meals.forEach(m => {
        if (m.description) names.push(m.description);
        else if (m.items) m.items.forEach(it => names.push(it.name || ''));
      });
    }
    return names.filter(Boolean);
  },

>>>>>>> Stashed changes
  renderCoachScreen() {
    try { return this._renderCoachScreenInner(); } catch(e) {
      console.error('Coach screen render failed:', e);
      const screen = UI.$('#screen-coach');
      if (screen) screen.innerHTML = `<div class="card" style="margin:20px;padding:20px"><div class="card-title">Coach Error</div><p style="color:var(--accent-red)">${e.message}</p><button class="btn" onclick="Coach.renderCoachScreen()">Retry</button></div>`;
    }
  },
  _renderCoachScreenInner() {
    const profile = Store.getProfile();
    const macros = profile.macros || { calories: 0, protein: 0, carbs: 0, fat: 0 };
    const totals = Store.getTodayTotals() || { calories: 0, protein: 0, carbs: 0, fat: 0 };
    const remaining = {
      calories: Math.max(0, macros.calories - totals.calories),
      protein: Math.max(0, macros.protein - totals.protein),
      carbs: Math.max(0, macros.carbs - totals.carbs),
      fat: Math.max(0, macros.fat - totals.fat)
    };
    const prefs = Store.getPreferences();

<<<<<<< Updated upstream
    // Build coaching context summary
    const condCount = (profile.healthConditions || []).length;
    const dislikedCount = (prefs.disliked || []).length;
=======
    // Smart context
    const autoMealType = this._detectMealType();
    let todayMeals = [];
    try { todayMeals = Store.getTodayMeals() || []; } catch(e) { console.warn('getTodayMeals failed:', e); }
    let insight = `Here's what I'd suggest for ${autoMealType}.`;
    try { insight = this._getCoachInsight(profile, totals, remaining, todayMeals); } catch(e) { console.warn('Coach insight failed:', e); }
>>>>>>> Stashed changes
    const goalLabel = Profile.goalLabels?.[profile.goal] || profile.goal;
    const contextParts = [goalLabel];
    if (condCount > 0) contextParts.push(`${condCount} health condition${condCount > 1 ? 's' : ''}`);
    contextParts.push(`${remaining.calories} cal remaining`);
    if (dislikedCount > 0) contextParts.push(`avoiding ${dislikedCount} food${dislikedCount > 1 ? 's' : ''}`);
    const contextSummary = contextParts.join(' · ');

    const screen = UI.$('#screen-coach');
    screen.innerHTML = `
      <div class="coach-context-summary">Coaching for ${profile.name || 'you'}: ${contextSummary}</div>
      <div class="card">
        <div class="card-title">Remaining Today</div>
        <div class="macro-grid">
          <div class="macro-item full-width">
            <div class="macro-label"><span>Calories</span></div>
            <div class="macro-value" style="color:var(--cal-color)">${remaining.calories} <span>cal left</span></div>
          </div>
          <div class="macro-item">
            <div class="macro-label"><span>Protein</span></div>
            <div class="macro-value" style="color:var(--protein-color)">${remaining.protein}g</div>
          </div>
          <div class="macro-item">
            <div class="macro-label"><span>Carbs</span></div>
            <div class="macro-value" style="color:var(--carb-color)">${remaining.carbs}g</div>
          </div>
          <div class="macro-item full-width">
            <div class="macro-label"><span>Fat</span></div>
            <div class="macro-value" style="color:var(--fat-color)">${remaining.fat}g</div>
          </div>
        </div>
      </div>

<<<<<<< Updated upstream
      <div class="card">
        <div class="card-title">What meal is this for?</div>
        <div class="meal-type-pills" id="meal-type-pills">
          <button class="meal-type-pill" data-type="breakfast">Breakfast</button>
          <button class="meal-type-pill" data-type="lunch">Lunch</button>
          <button class="meal-type-pill" data-type="snack">Snack</button>
          <button class="meal-type-pill" data-type="dinner">Dinner</button>
          <button class="meal-type-pill" data-type="pre_workout">Pre-Workout</button>
          <button class="meal-type-pill" data-type="post_workout">Post-Workout</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Dietary Style (optional)</div>
        <div class="meal-type-pills" id="diet-filter-pills">
          <button class="meal-type-pill diet-pill" data-filter="vegan">Vegan</button>
          <button class="meal-type-pill diet-pill" data-filter="vegetarian">Vegetarian</button>
          <button class="meal-type-pill diet-pill" data-filter="keto">Keto</button>
          <button class="meal-type-pill diet-pill" data-filter="low_carb">Low Carb</button>
          <button class="meal-type-pill diet-pill" data-filter="high_protein">High Protein</button>
          <button class="meal-type-pill diet-pill" data-filter="paleo">Paleo</button>
          <button class="meal-type-pill diet-pill" data-filter="gluten_free">Gluten Free</button>
          <button class="meal-type-pill diet-pill" data-filter="dairy_free">Dairy Free</button>
          <button class="meal-type-pill diet-pill" data-filter="mediterranean">Mediterranean</button>
          <button class="meal-type-pill diet-pill" data-filter="whole30">Whole30</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Cuisine (optional)</div>
        <div class="meal-type-pills" id="cuisine-filter-pills"></div>
      </div>

      <div class="card filter-collapse-wrap">
        <button class="filter-collapse-toggle" id="btn-more-filters">More Filters <span class="toggle-arrow">&#9662;</span></button>
        <div class="filter-collapse-content" id="more-filters">
          <div style="margin-bottom:12px">
            <div class="card-title" style="margin-bottom:8px">Max Cook Time</div>
            <div class="meal-type-pills" id="time-filter-pills">
              <button class="meal-type-pill time-pill" data-time="15">Under 15 min</button>
              <button class="meal-type-pill time-pill" data-time="30">Under 30 min</button>
              <button class="meal-type-pill time-pill" data-time="60">Under 60 min</button>
              <button class="meal-type-pill time-pill active" data-time="0">Any</button>
            </div>
          </div>
          <div>
            <div class="card-title" style="margin-bottom:8px">Difficulty</div>
            <div class="meal-type-pills" id="difficulty-filter-pills">
              <button class="meal-type-pill diff-pill" data-diff="easy">Easy</button>
              <button class="meal-type-pill diff-pill" data-diff="medium">Medium</button>
              <button class="meal-type-pill diff-pill" data-diff="hard">Hard</button>
              <button class="meal-type-pill diff-pill active" data-diff="">Any</button>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Extra Instructions (optional)</div>
        <input type="text" class="food-input" id="coach-custom" placeholder="e.g. quick to prepare, no fish, under 10 min...">
      </div>

      <div class="card">
        <div class="card-title">My Pantry / Ingredients I Have</div>
        <div class="food-input-wrap">
          <input type="text" class="food-input" id="pantry-input" placeholder="Add ingredient (e.g. chicken, rice, eggs...)">
          <button class="btn" id="btn-add-pantry" style="padding:10px 16px">Add</button>
        </div>
        <div class="prefs-tags" id="pantry-tags" style="margin-top:8px">
          ${Store.getPantry().map(item => `<span class="pref-tag pref-liked">${item} <button class="pantry-remove" data-item="${item}">&times;</button></span>`).join('')}
        </div>
        ${Store.getPantry().length > 0 ? `<label style="display:flex;align-items:center;gap:6px;margin-top:8px;font-size:12px;color:var(--text-dim);cursor:pointer"><input type="checkbox" id="chk-pantry-only"> Only suggest meals I can make with these ingredients</label>` : ''}
      </div>

      <button class="btn btn-coach" id="btn-find-recipes" disabled>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
        Pick a meal type first
      </button>

      <button class="btn btn-outline btn-full" id="btn-ai-suggest" style="margin-top:8px" disabled>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        Ask AI Coach for personalized suggestions
      </button>

      <button class="btn btn-outline btn-full" id="btn-meal-plan" style="margin-top:8px">
        Generate Weekly Meal Plan
      </button>
=======
      <!-- Hidden meal type pills for compatibility -->
      <div style="display:none">
        <div id="meal-type-pills">
          <button class="meal-type-pill active" data-type="${autoMealType}"></button>
        </div>
      </div>

      <div id="coach-results">
        <div class="card" style="text-align:center;padding:24px">
          <span class="spinner" style="width:24px;height:24px;border-width:3px;margin-bottom:8px"></span>
          <div style="color:var(--text-dim);font-size:13px">Finding the best meals for you...</div>
        </div>
      </div>

      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn btn-outline" id="btn-ai-suggest" style="flex:1;font-size:13px">Refresh Suggestions</button>
        <button class="btn btn-outline" id="btn-find-recipes" style="flex:1;font-size:13px">Browse Recipes</button>
        <button class="btn btn-outline" id="btn-meal-plan" style="flex:1;font-size:13px">Weekly Plan</button>
      </div>
>>>>>>> Stashed changes

      <!-- Hidden filter elements for compatibility -->
      <div style="display:none">
        <div id="diet-filter-pills"></div>
        <div id="cuisine-filter-pills"></div>
        <div id="time-filter-pills"><button class="meal-type-pill time-pill active" data-time="0"></button></div>
        <div id="difficulty-filter-pills"><button class="meal-type-pill diff-pill active" data-diff=""></button></div>
        <input id="coach-custom">
        <input id="pantry-input">
        <div id="pantry-tags"></div>
      </div>

      ${(prefs.liked.length > 0 || prefs.disliked.length > 0) ? `
        <div class="card prefs-card">
          <div class="card-title">Your Food Preferences</div>
          ${prefs.liked.length > 0 ? `
            <div class="prefs-section">
              <div class="prefs-label">Foods you like:</div>
              <div class="prefs-tags">
                ${prefs.liked.map(f => `<span class="pref-tag pref-liked">${f} <button class="pref-remove" data-type="liked" data-food="${f}">&times;</button></span>`).join('')}
              </div>
            </div>
          ` : ''}
          ${prefs.disliked.length > 0 ? `
            <div class="prefs-section">
              <div class="prefs-label">Foods you dislike:</div>
              <div class="prefs-tags">
                ${prefs.disliked.map(f => `<span class="pref-tag pref-disliked">${f} <button class="pref-remove" data-type="disliked" data-food="${f}">&times;</button></span>`).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      ` : ''}
    `;

    // Auto-apply dietary style filters from profile
    this._autoApplyDietFilters(profile);

    this._bindMealTypePills();
    this._bindDietFilters();
    this._bindCuisineFilters();
    this._bindExtraFilters();
    this._bindPrefRemove();
    this._bindPantry();
    UI.$('#btn-find-recipes')?.addEventListener('click', () => this.findRecipes());
    UI.$('#btn-ai-suggest')?.addEventListener('click', () => this.getSuggestion());
    UI.$('#btn-meal-plan')?.addEventListener('click', () => this.generateMealPlan());

    // Auto-fetch suggestions immediately
    this.getSuggestion();
  },

  _bindMealTypePills() {
    const labels = {
      breakfast: 'Breakfast',
      lunch: 'Lunch',
      snack: 'Snack',
      dinner: 'Dinner',
      pre_workout: 'Pre-Workout',
      post_workout: 'Post-Workout'
    };

    UI.$('#meal-type-pills').addEventListener('click', e => {
      const pill = e.target.closest('.meal-type-pill');
      if (!pill) return;
      pill.classList.toggle('active');

      this.selectedMealTypes = Array.from(UI.$$('#meal-type-pills .meal-type-pill.active')).map(p => p.dataset.type);

      const btnRecipes = UI.$('#btn-find-recipes');
      const btnAI = UI.$('#btn-ai-suggest');
      if (this.selectedMealTypes.length === 0) {
        btnRecipes.disabled = true;
        btnAI.disabled = true;
        btnRecipes.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
          Pick a meal type first
        `;
      } else {
        btnRecipes.disabled = false;
        btnAI.disabled = false;
        const selected = this.selectedMealTypes.map(t => labels[t]).join(' + ');
        btnRecipes.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
          Find ${selected} Recipes
        `;
      }
    });
  },

  // Map health conditions to auto-selected diet filters
  _healthToDietMap: {
    celiac: 'gluten_free',
    lactose_intolerant: 'dairy_free'
  },

  _autoApplyDietFilters(profile) {
    const savedDiets = profile.dietaryPreferences?.dietaryStyle || [];
    const healthConditions = profile.healthConditions || [];

    // Auto-select from health conditions
    const healthDiets = healthConditions
      .map(c => this._healthToDietMap[c])
      .filter(Boolean);

    const allAutoFilters = [...new Set([...savedDiets, ...healthDiets])];

    allAutoFilters.forEach(diet => {
      const pill = UI.$(`.diet-pill[data-filter="${diet}"]`);
      if (pill) pill.classList.add('active');
    });

    this.selectedDietFilters = [...allAutoFilters];

    // Show note if health-based filters were applied
    if (healthDiets.length > 0) {
      const container = UI.$('#diet-filter-pills');
      if (container) {
        const note = document.createElement('div');
        note.className = 'coach-auto-note';
        note.textContent = 'Auto-selected based on your health profile';
        container.parentNode.insertBefore(note, container.nextSibling);
      }
    }
  },

  _bindDietFilters() {
    UI.$('#diet-filter-pills').addEventListener('click', e => {
      const pill = e.target.closest('.diet-pill');
      if (!pill) return;
      pill.classList.toggle('active');
      this.selectedDietFilters = Array.from(UI.$$('.diet-pill.active')).map(p => p.dataset.filter);
    });
  },

  _bindPantry() {
    const addItem = () => {
      const input = UI.$('#pantry-input');
      const val = input?.value.trim();
      if (!val) return;
      Store.addPantryItem(val);
      input.value = '';
      this.renderCoachScreen();
    };
    UI.$('#btn-add-pantry')?.addEventListener('click', addItem);
    UI.$('#pantry-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') addItem(); });
    UI.$$('.pantry-remove').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        Store.removePantryItem(btn.dataset.item);
        this.renderCoachScreen();
      });
    });
  },

  _bindPrefRemove() {
    UI.$$('.pref-remove').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const type = btn.dataset.type;
        const food = btn.dataset.food;
        Store.removePreference(type, food);
        UI.toast(`Removed "${food}" from ${type}`, '');
        this.renderCoachScreen();
      });
    });
  },

  async _bindCuisineFilters() {
    try {
      await RecipeDB.init();
      const cuisines = RecipeDB.getDistinctValues('cuisine');
      const container = UI.$('#cuisine-filter-pills');
      if (!container) return;
      container.innerHTML = cuisines.map(c =>
        `<button class="meal-type-pill cuisine-pill" data-cuisine="${c}">${c}</button>`
      ).join('');
      container.addEventListener('click', e => {
        const pill = e.target.closest('.cuisine-pill');
        if (!pill) return;
        const wasActive = pill.classList.contains('active');
        UI.$$('.cuisine-pill').forEach(p => p.classList.remove('active'));
        if (!wasActive) pill.classList.add('active');
        this.selectedCuisine = wasActive ? '' : pill.dataset.cuisine;
      });
      this._dbReady = true;
    } catch {
      UI.$('#cuisine-filter-pills').innerHTML = '<span style="color:var(--text-dim);font-size:12px">Recipe DB not loaded. Run build script first.</span>';
    }
  },

  _bindExtraFilters() {
    UI.$('#time-filter-pills')?.addEventListener('click', e => {
      const pill = e.target.closest('.time-pill');
      if (!pill) return;
      UI.$$('.time-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      this.selectedMaxTime = parseInt(pill.dataset.time) || 0;
    });
    UI.$('#difficulty-filter-pills')?.addEventListener('click', e => {
      const pill = e.target.closest('.diff-pill');
      if (!pill) return;
      UI.$$('.diff-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      this.selectedDifficulty = pill.dataset.diff || '';
    });
  },

  async findRecipes() {
    if (this.selectedMealTypes.length === 0) {
      UI.toast('Pick at least one meal type', 'error');
      return;
    }

    if (!this._dbReady) {
      UI.showLoading('Loading recipe database...');
      try {
        await RecipeDB.init();
        this._dbReady = true;
      } catch (err) {
        UI.hideLoading();
        UI.toast('Recipe database not available. Run the build script first.', 'error');
        return;
      }
      UI.hideLoading();
    }

    const profile = Store.getProfile();
    const totals = Store.getTodayTotals();
    const remaining = {
      calories: Math.max(0, profile.macros.calories - totals.calories),
      protein: Math.max(0, profile.macros.protein - totals.protein),
      carbs: Math.max(0, profile.macros.carbs - totals.carbs),
      fat: Math.max(0, profile.macros.fat - totals.fat)
    };

    const prefs = Store.getPreferences();
    const pantry = Store.getPantry();
    const pantryOnly = UI.$('#chk-pantry-only')?.checked || false;
    const textSearch = UI.$('#coach-custom')?.value.trim() || '';

    // Map health conditions to allergen exclusions
    const allergenMap = {
      nut_allergy: 'tree_nuts',
      shellfish_allergy: 'shellfish',
      egg_allergy: 'egg',
      soy_allergy: 'soy',
      lactose_intolerant: 'dairy',
      celiac: 'gluten'
    };
    const excludeAllergens = (profile.healthConditions || [])
      .map(c => allergenMap[c]).filter(Boolean);

    // Map goal to tag_goal
    const goalTagMap = {
      fat_loss: 'fat_loss',
      aggressive_fat_loss: 'cutting',
      muscle_gain: 'muscle_building',
      lean_bulk: 'bulking',
      maintain: 'maintenance',
      recomp: 'fat_loss'
    };

    const filters = {
      mealTypes: this.selectedMealTypes,
      dietFilters: this.selectedDietFilters,
      cuisine: this.selectedCuisine || undefined,
      difficulty: this.selectedDifficulty || undefined,
      maxTime: this.selectedMaxTime || undefined,
      textSearch: textSearch || undefined,
      excludeAllergens: excludeAllergens.length > 0 ? excludeAllergens : undefined,
      tagGoal: goalTagMap[profile.goal] || undefined
    };

    const recipes = RecipeDB.findMacroFit(remaining, filters);

    if (recipes.length === 0) {
      // Retry without tagGoal for broader results
      delete filters.tagGoal;
      const broader = RecipeDB.findMacroFit(remaining, filters);
      if (broader.length === 0) {
        UI.toast('No recipes match your filters. Try relaxing some filters.', 'error');
        return;
      }
      this.lastRecipeResults = broader;
      this.showRecipeResults(broader);
      return;
    }

    // Filter out disliked foods
    const filtered = recipes.filter(r =>
      !prefs.disliked.some(d => r.name.toLowerCase().includes(d.toLowerCase()))
    );

    this.lastRecipeResults = filtered.length > 0 ? filtered : recipes;
    this.showRecipeResults(this.lastRecipeResults);
  },

  showRecipeResults(recipes) {
    const container = UI.$('#coach-results');
    container.innerHTML = `
      <div class="recipe-results-header">
        <span class="recipe-results-count">${recipes.length} recipes found</span>
      </div>
      ${recipes.map((r, i) => `
        <div class="suggestion-card ${i === 0 ? 'top-pick' : ''}" id="db-recipe-${r.id}">
          ${i === 0 ? '<div class="suggestion-rank-badge">#1 Best Macro Fit</div>' : `<div class="suggestion-rank-badge">#${i + 1}</div>`}
          <div class="recipe-badges">
            <span class="recipe-badge">${r.cuisine}</span>
            <span class="recipe-badge">${r.difficulty}</span>
            <span class="recipe-badge">${r.total_time_min} min</span>
            ${r.meal_prep_friendly ? '<span class="recipe-badge badge-prep">Meal Prep</span>' : ''}
          </div>
          <div class="suggestion-header">
            <div class="suggestion-title">${r.name}</div>
            <div class="suggestion-actions">
              <button class="sug-btn sug-like" data-recipe-id="${r.id}" title="I like this kind of food">&#9829;</button>
              <button class="sug-btn sug-discard" data-recipe-id="${r.id}" title="Not for me">&#10005;</button>
            </div>
          </div>
          <div class="suggestion-desc">${r.description}</div>
          <div class="suggestion-macros">
            <span style="color:var(--cal-color)">${r.calories} cal</span>
            <span style="color:var(--protein-color)">${r.protein_g}g P</span>
            <span style="color:var(--carb-color)">${r.carbs_g}g C</span>
            <span style="color:var(--fat-color)">${r.fat_g}g F</span>
            ${r.fiber_g ? `<span style="color:#56ab2f">${r.fiber_g}g fiber</span>` : ''}
          </div>
          <div class="recipe-tags">
            ${r.diet.map(d => `<span class="recipe-diet-tag">${d.replace(/_/g, ' ')}</span>`).join('')}
          </div>
          <div class="suggestion-btn-row">
            <button class="btn btn-recipe" data-recipe-id="${r.id}">View Recipe</button>
            <button class="btn btn-log-suggestion" data-recipe-id="${r.id}">I ate this</button>
          </div>
          <div class="recipe-content" id="recipe-db-${r.id}"></div>
        </div>
      `).join('')}
      <div style="margin-top:8px">
        <button class="btn btn-outline btn-full" id="btn-refresh-recipes">Find different recipes</button>
      </div>
    `;

    this._bindRecipeResultActions();
    UI.$('#btn-refresh-recipes')?.addEventListener('click', () => this.findRecipes());
  },

  _bindRecipeResultActions() {
    // Like
    UI.$$('#coach-results .sug-like').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.recipeId);
        const recipe = this.lastRecipeResults?.find(r => r.id === id);
        if (!recipe) return;
        Store.addPreference('liked', recipe.name);
        btn.classList.add('liked-active');
        UI.toast(`Noted: you like "${recipe.name}"`, 'success');
      });
    });

    // Dislike
    UI.$$('#coach-results .sug-discard').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.recipeId);
        const recipe = this.lastRecipeResults?.find(r => r.id === id);
        if (!recipe) return;
        Store.addPreference('disliked', recipe.name);
        const card = UI.$(`#db-recipe-${id}`);
        card.classList.add('discarded');
        setTimeout(() => { card.style.display = 'none'; }, 300);
        UI.toast(`Got it, won't suggest "${recipe.name}" again`, '');
      });
    });

    // View Recipe (from DB - instant, no LLM call)
    UI.$$('#coach-results .btn-recipe').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.recipeId);
        const container = UI.$(`#recipe-db-${id}`);
        if (container.classList.contains('show')) {
          container.classList.remove('show');
          btn.textContent = 'View Recipe';
          return;
        }
        const recipe = RecipeDB.getRecipeById(id);
        if (!recipe) return;
        container.innerHTML = this._renderRecipe({
          name: recipe.name,
          prep_time: recipe.prep_time_min + ' min',
          cook_time: recipe.cook_time_min + ' min',
          servings: String(recipe.servings),
          ingredients: recipe.ingredients.map(i => `${i.amount} ${i.item}`),
          steps: recipe.steps,
          tips: recipe.tips,
          calories: recipe.calories,
          protein: recipe.protein_g,
          carbs: recipe.carbs_g,
          fat: recipe.fat_g
        });
        container.classList.add('show');
        btn.textContent = 'Hide Recipe';
      });
    });

    // Log meal from recipe
    UI.$$('#coach-results .btn-log-suggestion').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.recipeId);
        const recipe = this.lastRecipeResults?.find(r => r.id === id);
        if (!recipe) return;
        Store.addMeal({
          time: new Date().toISOString(),
          description: recipe.name,
          items: [{
            name: recipe.name,
            calories: recipe.calories || 0,
            protein: recipe.protein_g || 0,
            carbs: recipe.carbs_g || 0,
            fat: recipe.fat_g || 0,
            sugar_natural: 0,
            sugar_processed: recipe.sugar_g || 0,
            fiber: recipe.fiber_g || 0
          }],
          total: {
            calories: recipe.calories || 0,
            protein: recipe.protein_g || 0,
            carbs: recipe.carbs_g || 0,
            fat: recipe.fat_g || 0,
            sugar_natural: 0,
            sugar_processed: recipe.sugar_g || 0,
            fiber: recipe.fiber_g || 0
          }
        });
        btn.textContent = 'Logged!';
        btn.disabled = true;
        btn.classList.add('logged');
        UI.toast(`${recipe.name} logged!`, 'success');
      });
    });
  },

  async getSuggestion() {
    const profile = Store.getProfile();
    const macros = profile.macros || { calories: 0, protein: 0, carbs: 0, fat: 0 };
    const totals = Store.getTodayTotals() || { calories: 0, protein: 0, carbs: 0, fat: 0 };
    const remaining = {
      calories: Math.max(0, macros.calories - totals.calories),
      protein: Math.max(0, macros.protein - totals.protein),
      carbs: Math.max(0, macros.carbs - totals.carbs),
      fat: Math.max(0, macros.fat - totals.fat),
    };

    // Gather today's meals with details
    const todayMeals = Store.getTodayMeals() || [];
    const todayMealData = todayMeals.map(m => ({
      name: m.description || (m.items ? m.items.map(i => i.name).join(', ') : 'Meal'),
      calories: m.total?.calories || 0,
      protein: m.total?.protein || 0,
      hour: m.time ? new Date(m.time).getHours() : 12,
    }));

    // Gather week's meal names
    const weekMeals = [];
    const data = Store.load();
    for (let i = 0; i < 7; i++) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const entry = data.logs[key];
      const meals = Array.isArray(entry) ? entry : (entry?.meals || []);
      meals.forEach(m => {
        const name = m.description || (m.items ? m.items.map(i => i.name).join(', ') : '');
        if (name) weekMeals.push(name);
      });
    }

    const prefs = Store.getPreferences();
    const dietFilters = profile.dietaryPreferences?.dietaryStyle || [];

    const container = UI.$('#coach-results');
    container.innerHTML = `
      <div class="card" style="text-align:center;padding:24px">
        <span class="spinner" style="width:24px;height:24px;border-width:3px;display:inline-block;margin-bottom:8px"></span>
        <div style="color:var(--text-dim);font-size:13px">Finding the best meals for you...</div>
      </div>
    `;

    // Gather workout data
    let todayWorkouts = [];
    let lastWorkoutHoursAgo = null;
    try {
      const wks = Store.getTodayWorkouts ? Store.getTodayWorkouts() : [];
      todayWorkouts = wks.map(w => ({
        type: w.type || w.name || 'workout',
        calories: w.calories || 0,
        hour: w.time ? new Date(w.time).getHours() : null,
      }));
      if (wks.length > 0) {
        const lastTime = new Date(wks[wks.length - 1].time);
        lastWorkoutHoursAgo = Math.round((Date.now() - lastTime.getTime()) / 3600000 * 10) / 10;
      }
    } catch(e) {}

    // Water intake
    let waterMl = 0;
    try { waterMl = Store.getTodayWater ? Store.getTodayWater() : 0; } catch(e) {}

    // Weekly macro averages
    let weeklyAvg = { days: 0, avgCal: 0, avgProtein: 0, avgCarbs: 0, avgFat: 0 };
    try {
      let totalDays = 0, sumCal = 0, sumProt = 0, sumCarbs = 0, sumFat = 0;
      for (let i = 1; i <= 7; i++) {
        const d = new Date(); d.setDate(d.getDate() - i);
        const key = d.toISOString().split('T')[0];
        const entry = data.logs[key];
        const meals = Array.isArray(entry) ? entry : (entry?.meals || []);
        if (meals.length > 0) {
          totalDays++;
          meals.forEach(m => {
            sumCal += m.total?.calories || 0;
            sumProt += m.total?.protein || 0;
            sumCarbs += m.total?.carbs || 0;
            sumFat += m.total?.fat || 0;
          });
        }
      }
      if (totalDays > 0) {
        weeklyAvg = { days: totalDays, avgCal: Math.round(sumCal/totalDays), avgProtein: Math.round(sumProt/totalDays), avgCarbs: Math.round(sumCarbs/totalDays), avgFat: Math.round(sumFat/totalDays) };
      }
    } catch(e) {}

    // Feeling patterns
    let feelingPatterns = [];
    try {
      if (typeof MealHistory !== 'undefined' && MealHistory.getFeelingInsights) {
        feelingPatterns = MealHistory.getFeelingInsights() || [];
      }
    } catch(e) {}

    try {
      const res = await fetch(`${LLM.backendUrl}/api/recipes/smart-suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hour: new Date().getHours(),
          profile: {
            goal: profile.goal || 'maintenance',
            gender: profile.gender || 'unknown',
            age: profile.age || 30,
            weight: profile.weight || 0,
            height: profile.height || 0,
            activity_level: profile.activityLevel || 'moderate',
            target_calories: macros.calories,
            target_protein: macros.protein,
            target_carbs: macros.carbs,
            target_fat: macros.fat,
          },
          today_meals: todayMealData,
          remaining,
          week_meals: weekMeals,
          liked: prefs.liked || [],
          disliked: prefs.disliked || [],
          diet_filters: dietFilters,
          health_conditions: profile.healthConditions || [],
          workouts: todayWorkouts,
          last_workout_hours_ago: lastWorkoutHoursAgo,
          water_ml: waterMl,
          weekly_avg: weeklyAvg,
          feeling_patterns: feelingPatterns,
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Failed to get suggestions');
      }

      const result = await res.json();
      this.lastSuggestions = result;
      this.showSuggestions(result);
    } catch (err) {
      container.innerHTML = `
        <div class="card" style="padding:16px;text-align:center">
          <div style="color:var(--accent-red);margin-bottom:8px">${UI.esc(err.message)}</div>
          <button class="btn btn-outline" onclick="Coach.getSuggestion()">Try Again</button>
        </div>
      `;
    }
  },

  showSuggestions(result) {
    const container = UI.$('#coach-results');
    const nextMeal = result.next_meal || '';
    const mealsHad = result.meals_had_today || [];
    const mealLabel = nextMeal.charAt(0).toUpperCase() + nextMeal.slice(1);

    container.innerHTML = `
      ${result.coaching_note ? `
        <div class="coach-insight-card card" style="margin-bottom:8px">
          <div class="coach-insight-icon">&#129504;</div>
          <div class="coach-insight-text">${UI.esc(result.coaching_note)}</div>
        </div>
      ` : ''}
      ${result.top_pick_reason ? `<div class="top-pick-banner"><div class="top-pick-label">Why #1 is your best pick right now</div><div class="top-pick-text">${UI.esc(result.top_pick_reason)}</div></div>` : ''}
      ${nextMeal ? `<div style="font-size:12px;color:var(--text-dim);padding:4px 0 8px;text-transform:uppercase;letter-spacing:1px;font-weight:700">${mealLabel} suggestions ${mealsHad.length > 0 ? `· Already had: ${mealsHad.join(', ')}` : ''}</div>` : ''}
      ${result.suggestions.map((s, i) => `
        <div class="suggestion-card ${i === 0 ? 'top-pick' : ''}" id="suggestion-${i}">
          <div class="suggestion-rank-badge">
            ${i === 0 ? '#1 Best Pick' : `#${i + 1}`}
          </div>
          <div class="suggestion-header">
            <div class="suggestion-title">${UI.esc(s.name)}</div>
            <div class="suggestion-actions">
              <button class="sug-btn sug-like" data-index="${i}" title="I like this kind of food">&#9829;</button>
              <button class="sug-btn sug-discard" data-index="${i}" title="Not for me">&#10005;</button>
            </div>
          </div>
          ${s.why ? `<div class="suggestion-why">${UI.esc(s.why)}</div>` : ''}
          <div class="suggestion-desc">${UI.esc(s.description)}</div>
          <div class="suggestion-macros">
            <span style="color:var(--cal-color)">${s.calories} cal</span>
            <span style="color:var(--protein-color)">${s.protein}g P</span>
            <span style="color:var(--carb-color)">${s.carbs}g C</span>
            <span style="color:var(--fat-color)">${s.fat}g F</span>
          </div>
          <div class="suggestion-btn-row">
            <button class="btn btn-recipe instant" data-index="${i}">View Recipe</button>
            <button class="btn btn-log-suggestion" data-index="${i}">I ate this</button>
          </div>
          <div class="recipe-content" id="recipe-${i}"></div>
        </div>
      `).join('')}
      <button class="btn btn-outline btn-full" id="btn-regenerate" style="margin-top:4px">
        Suggest different options
      </button>
    `;

    this._bindSuggestionActions();
    this._bindRecipeButtons();
    this._bindLogSuggestions();
    UI.$('#btn-regenerate')?.addEventListener('click', () => this.getSuggestion());
  },

  _bindSuggestionActions() {
    UI.$$('.sug-like').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index);
        const suggestion = this.lastSuggestions?.suggestions[idx];
        if (!suggestion) return;
        Store.addPreference('liked', suggestion.name);
        btn.classList.add('liked-active');
        UI.toast(`Noted: you like "${suggestion.name}"`, 'success');
      });
    });

    UI.$$('.sug-discard').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index);
        const suggestion = this.lastSuggestions?.suggestions[idx];
        if (!suggestion) return;
        Store.addPreference('disliked', suggestion.name);

        const card = UI.$(`#suggestion-${idx}`);
        card.classList.add('discarded');
        setTimeout(() => {
          card.style.display = 'none';
          UI.toast(`Got it, won't suggest "${suggestion.name}" again`, '');
        }, 300);
      });
    });
  },

  _bindRecipeButtons() {
    UI.$$('.btn-recipe').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index);
        const suggestion = this.lastSuggestions?.suggestions[idx];
        if (!suggestion) return;

        const container = UI.$(`#recipe-${idx}`);

        // Toggle off if already showing
        if (container.classList.contains('show')) {
          container.classList.remove('show');
          btn.textContent = 'View Recipe';
          return;
        }

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px"></span> Loading...';

        try {
          const recipe = await LLM.generateRecipe(suggestion, this.selectedDietFilters);
          container.innerHTML = this._renderRecipe(recipe);
          container.classList.add('show');
          btn.textContent = 'Hide Recipe';
        } catch (err) {
          UI.toast(err.message, 'error');
          btn.textContent = 'View Recipe';
        } finally {
          btn.disabled = false;
        }
      });
    });
  },

  async generateMealPlan() {
    const profile = Store.getProfile();

    const dbPlan = await this._tryDbMealPlan(profile);
    if (dbPlan) {
      this._renderMealPlan(dbPlan);
      return;
    }

    // Fallback: generate meal plan via LLM
    const llmPlan = await this._tryLLMMealPlan(profile);
    if (llmPlan) {
      this._renderMealPlan(llmPlan);
      return;
    }

    UI.toast('Could not generate meal plan. Add your Anthropic API key in the admin panel.', 'error');
  },

  async _tryLLMMealPlan(profile) {
    try {
      UI.showLoading('Generating meal plan with AI...');
      const res = await fetch('/api/recipes/meal-plan-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diet_filters: this.selectedDietFilters,
          goal: profile.goal || 'maintenance',
          target_calories: profile.macros.calories || 2000,
          target_protein: profile.macros.protein || 150
        })
      });
      UI.hideLoading();
      if (!res.ok) return null;
      return await res.json();
    } catch {
      UI.hideLoading();
      return null;
    }
  },

  async _tryDbMealPlan(profile) {
    try {
      UI.showLoading('Building your weekly plan from recipes...');
      const prefs = Store.getPreferences();
      const res = await fetch('/api/recipes/meal-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diet_filters: this.selectedDietFilters,
          goal: profile.goal || '',
          target_calories: profile.macros.calories || 2000,
          target_protein: profile.macros.protein || 150,
          liked: prefs.liked || [],
          disliked: prefs.disliked || []
        })
      });
      UI.hideLoading();
      if (!res.ok) return null;
      const data = await res.json();
      // Verify we got enough meals
      const totalMeals = data.plan?.reduce((s, d) => s + (d.meals?.length || 0), 0) || 0;
      if (totalMeals < 14) return null; // Need at least 2 meals per day
      return data;
    } catch {
      UI.hideLoading();
      return null;
    }
  },

  _renderMealPlan(result) {
    const container = UI.$('#coach-results');
    container.innerHTML = `
      <div class="card-title" style="margin-bottom:12px">
        Your Weekly Meal Plan
        <span class="sug-source sug-source-db" style="margin-left:8px">From Recipe DB</span>
      </div>
      ${result.plan.map(day => `
        <div class="card meal-plan-day">
          <div class="meal-plan-day-title">${day.day}</div>
          ${day.meals.map(m => `
            <div class="meal-plan-item" ${m.recipe_id ? `data-recipe-id="${m.recipe_id}" style="cursor:pointer"` : ''}>
              <div class="meal-plan-type">${m.type}</div>
              <div class="meal-plan-name">${m.name}</div>
              <div class="meal-plan-desc">${m.description}</div>
              <div class="suggestion-macros" style="margin-top:4px">
                <span style="color:var(--cal-color)">${m.calories}cal</span>
                <span style="color:var(--protein-color)">${m.protein}gP</span>
                <span style="color:var(--carb-color)">${m.carbs}gC</span>
                <span style="color:var(--fat-color)">${m.fat}gF</span>
              </div>
            </div>
          `).join('')}
          <div class="meal-plan-day-total">
            Day total: ${day.meals.reduce((s,m) => s+m.calories, 0)} cal /
            ${day.meals.reduce((s,m) => s+m.protein, 0)}g P /
            ${day.meals.reduce((s,m) => s+m.carbs, 0)}g C /
            ${day.meals.reduce((s,m) => s+m.fat, 0)}g F
          </div>
        </div>
      `).join('')}
    `;

    // Add grocery list button
    const recipeIds = [];
    result.plan.forEach(day => {
      (day.meals || []).forEach(m => { if (m.recipe_id) recipeIds.push(m.recipe_id); });
    });
    if (recipeIds.length > 0) {
      container.insertAdjacentHTML('beforeend', `
        <div class="card" style="text-align:center;margin-top:8px">
          <button class="btn btn-full" id="btn-grocery-list">&#128722; Generate Grocery List</button>
        </div>
      `);
      UI.$('#btn-grocery-list')?.addEventListener('click', () => this._showGroceryList(recipeIds));
    }

    // Click on meal plan items to view recipe detail
    container.querySelectorAll('.meal-plan-item[data-recipe-id]').forEach(item => {
      item.addEventListener('click', () => {
        const id = +item.dataset.recipeId;
        if (id && typeof Recipes !== 'undefined') {
          Recipes.showDetail(id);
        }
      });
    });
  },

  async _showGroceryList(recipeIds) {
    const btn = UI.$('#btn-grocery-list');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px"></span> Loading...';
    }

    try {
      const pantry = Store.getPantry?.() || [];
      const res = await fetch('/api/recipes/grocery-list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipe_ids: recipeIds, pantry })
      });
      if (!res.ok) throw new Error('Failed to generate grocery list');
      const data = await res.json();

      // Build modal
      const grouped = data.grouped || {};
      const categoryIcons = { produce: '&#129382;', protein: '&#129385;', dairy: '&#129472;', grains: '&#127838;', pantry: '&#129474;', other: '&#127860;' };

      let html = `
        <div class="modal-overlay show" id="grocery-modal">
          <div class="recipe-detail-sheet" style="max-height:85vh;overflow-y:auto">
            <div class="rd-header">
              <button class="rd-close" id="grocery-close">&times;</button>
              <div class="rd-name">Grocery List</div>
              <div class="rd-desc">${data.total_items} items total &middot; ${data.to_buy} to buy${data.pantry_items ? ` &middot; ${data.pantry_items} in pantry` : ''}</div>
            </div>
            <div class="grocery-categories">
      `;

      for (const [cat, items] of Object.entries(grouped)) {
        const icon = categoryIcons[cat] || '&#127860;';
        html += `
          <div class="grocery-category">
            <div class="grocery-cat-title">${icon} ${cat.charAt(0).toUpperCase() + cat.slice(1)}</div>
            <ul class="grocery-items">
              ${items.map(item => `
                <li class="grocery-item ${item.in_pantry ? 'in-pantry' : ''}">
                  <label>
                    <input type="checkbox" ${item.in_pantry ? 'checked' : ''}>
                    <span class="grocery-item-name">${item.name}</span>
                    <span class="grocery-item-amount">${item.amount}</span>
                    ${item.recipe_count > 1 ? `<span class="grocery-item-recipes">${item.recipe_count} recipes</span>` : ''}
                  </label>
                </li>
              `).join('')}
            </ul>
          </div>
        `;
      }

      html += `
            </div>
            <div class="rd-actions" style="margin-top:16px">
              <button class="btn btn-full" id="grocery-copy">&#128203; Copy to Clipboard</button>
            </div>
          </div>
        </div>
      `;

      document.body.insertAdjacentHTML('beforeend', html);

      UI.$('#grocery-close')?.addEventListener('click', () => {
        UI.$('#grocery-modal')?.remove();
      });
      UI.$('#grocery-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'grocery-modal') UI.$('#grocery-modal')?.remove();
      });
      UI.$('#grocery-copy')?.addEventListener('click', () => {
        const lines = data.items
          .filter(i => !i.in_pantry)
          .map(i => `${i.name} - ${i.amount}`);
        navigator.clipboard?.writeText(lines.join('\n'))
          .then(() => UI.toast('Grocery list copied!', 'success'))
          .catch(() => UI.toast('Could not copy', 'error'));
      });

    } catch (err) {
      UI.toast(err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '&#128722; Generate Grocery List';
      }
    }
  },

  _bindLogSuggestions() {
    UI.$$('.btn-log-suggestion').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index);
        const s = this.lastSuggestions?.suggestions[idx];
        if (!s) return;
        Store.addMeal({
          time: new Date().toISOString(),
          description: s.name,
          items: [{ name: s.name, calories: s.calories||0, protein: s.protein||0, carbs: s.carbs||0, fat: s.fat||0, sugar_natural: 0, sugar_processed: 0 }],
          total: { calories: s.calories||0, protein: s.protein||0, carbs: s.carbs||0, fat: s.fat||0, sugar_natural: 0, sugar_processed: 0 }
        });
        btn.textContent = 'Logged!';
        btn.disabled = true;
        btn.classList.add('logged');
        UI.toast(`${s.name} logged!`, 'success');
      });
    });
  },

  _renderRecipe(recipe) {
    return `
      <div class="recipe-box">
        <div class="recipe-header">
          <div class="recipe-title">${UI.esc(recipe.name)}</div>
          <div class="recipe-meta">
            ${recipe.prep_time ? `<span>Prep: ${UI.esc(recipe.prep_time)}</span>` : ''}
            ${recipe.cook_time ? `<span>Cook: ${UI.esc(recipe.cook_time)}</span>` : ''}
            ${recipe.servings ? `<span>Serves: ${UI.esc(recipe.servings)}</span>` : ''}
          </div>
        </div>
        <div class="recipe-section">
          <div class="recipe-section-title">Ingredients</div>
<<<<<<< Updated upstream
          <ul class="recipe-list">
            ${recipe.ingredients.map(ing => `<li>${UI.esc(ing)}</li>`).join('')}
=======
          <ul class="recipe-list" id="ings-${uid}">
            ${recipe.ingredients.map(ing => `<li>${UI.esc(typeof ing === 'object' ? `${ing.amount || ''} ${ing.item || ''}`.trim() : String(ing))}</li>`).join('')}
>>>>>>> Stashed changes
          </ul>
        </div>
        <div class="recipe-section">
          <div class="recipe-section-title">Instructions</div>
          <ol class="recipe-steps">
            ${recipe.steps.map(step => `<li>${UI.esc(step)}</li>`).join('')}
          </ol>
        </div>
        ${recipe.tips ? `
          <div class="recipe-section">
            <div class="recipe-section-title">Coach Tips</div>
            <div class="recipe-tips">${UI.esc(recipe.tips)}</div>
          </div>
        ` : ''}
        <div class="recipe-macros-summary">
          <span style="color:var(--cal-color)">${recipe.calories} cal</span>
          <span style="color:var(--protein-color)">${recipe.protein}g P</span>
          <span style="color:var(--carb-color)">${recipe.carbs}g C</span>
          <span style="color:var(--fat-color)">${recipe.fat}g F</span>
        </div>
      </div>
    `;
<<<<<<< Updated upstream
=======
  },

  _bindRecipeBoxEvents(container, recipe) {
    const uid = container.querySelector('.recipe-box')?.dataset.uid;
    if (!uid) return;

    const baseServings = parseInt(recipe.servings) || 1;
    let currentServings = recipe.requested_servings || baseServings;
    const ingsRaw = recipe.ingredients_raw || [];
    const hasRawIngs = ingsRaw.length > 0 && typeof ingsRaw[0] === 'object';

    const updateServings = (newVal) => {
      currentServings = Math.max(1, Math.min(12, newVal));
      const srvEl = UI.$(`#srv-${uid}`);
      if (srvEl) srvEl.textContent = currentServings;

      // Scale ingredients
      if (hasRawIngs) {
        const scale = currentServings / baseServings;
        const ingsEl = UI.$(`#ings-${uid}`);
        if (ingsEl) {
          ingsEl.innerHTML = ingsRaw.map(ing => {
            const grams = ing.grams ? Math.round(ing.grams * scale) : null;
            const amt = ing.amount || '';
            const scaledAmt = grams ? `${grams}g` : this._scaleAmount(amt, scale);
            return `<li>${UI.esc(scaledAmt)} ${UI.esc(ing.item || '')}</li>`;
          }).join('');
        }
      }

      // Scale macros per serving stays same, total changes shown
      const macrosEl = UI.$(`#macros-${uid}`);
      if (macrosEl) {
        macrosEl.innerHTML = `
          <span style="color:var(--cal-color)">${recipe.calories} cal</span>
          <span style="color:var(--protein-color)">${recipe.protein}g P</span>
          <span style="color:var(--carb-color)">${recipe.carbs}g C</span>
          <span style="color:var(--fat-color)">${recipe.fat}g F</span>
          <span class="macro-per-note">per serving (${currentServings} servings = ${recipe.calories * currentServings} cal total)</span>
        `;
      }
    };

    container.querySelector('.servings-minus')?.addEventListener('click', () => updateServings(currentServings - 1));
    container.querySelector('.servings-plus')?.addEventListener('click', () => updateServings(currentServings + 1));

    // Shopping list
    container.querySelector('.btn-shopping-list')?.addEventListener('click', () => {
      const shopEl = UI.$(`#shop-${uid}`);
      if (shopEl.style.display !== 'none') { shopEl.style.display = 'none'; return; }

      const scale = currentServings / baseServings;
      const categories = {};
      const items = hasRawIngs ? ingsRaw : recipe.ingredients.map(i => typeof i === 'object' ? { item: i.item || '', amount: i.amount || '', category: i.category || 'other' } : { item: String(i), amount: '', category: 'other' });
      items.forEach(ing => {
        const cat = (ing.category || 'other').toLowerCase();
        if (!categories[cat]) categories[cat] = [];
        const grams = ing.grams ? Math.round(ing.grams * scale) : null;
        const amt = grams ? `${grams}g` : (ing.amount ? this._scaleAmount(ing.amount, scale) : '');
        categories[cat].push({ item: ing.item || ing, amount: amt });
      });

      const catLabels = { protein: 'Protein', produce: 'Produce', dairy: 'Dairy', grain: 'Grains & Pasta', spice: 'Spices & Seasonings', oil: 'Oils & Sauces', other: 'Other' };
      shopEl.innerHTML = `
        <div class="shopping-list">
          <div class="shopping-list-header">
            <span class="recipe-section-title">Shopping List (${currentServings} servings)</span>
            <button class="btn btn-outline btn-copy-shop" style="font-size:11px;padding:4px 10px">Copy</button>
          </div>
          ${Object.entries(categories).map(([cat, items]) => `
            <div class="shop-category">
              <div class="shop-cat-title">${catLabels[cat] || cat}</div>
              ${items.map(i => `
                <label class="shop-item">
                  <input type="checkbox" class="shop-check">
                  <span>${UI.esc(i.amount)} ${UI.esc(typeof i.item === 'string' ? i.item : '')}</span>
                </label>
              `).join('')}
            </div>
          `).join('')}
        </div>
      `;
      shopEl.style.display = 'block';

      shopEl.querySelector('.btn-copy-shop')?.addEventListener('click', () => {
        const text = Object.entries(categories).map(([cat, items]) =>
          `${(catLabels[cat] || cat).toUpperCase()}\n${items.map(i => `  - ${i.amount} ${typeof i.item === 'string' ? i.item : ''}`).join('\n')}`
        ).join('\n\n');
        navigator.clipboard.writeText(text).then(() => UI.toast('Shopping list copied!', 'success'));
      });
    });

    // Copy recipe
    container.querySelector('.btn-copy-recipe')?.addEventListener('click', () => {
      const fmtIng = i => typeof i === 'object' ? `${i.amount || ''} ${i.item || ''}`.trim() : String(i);
      const text = `${recipe.name}\n\nIngredients:\n${recipe.ingredients.map(i => `- ${fmtIng(i)}`).join('\n')}\n\nInstructions:\n${recipe.steps.map((s, i) => `${i+1}. ${s}`).join('\n')}\n\nMacros per serving: ${recipe.calories} cal, ${recipe.protein}g protein, ${recipe.carbs}g carbs, ${recipe.fat}g fat`;
      navigator.clipboard.writeText(text).then(() => UI.toast('Recipe copied!', 'success'));
    });
  },

  _scaleAmount(amount, scale) {
    if (!amount) return '';
    const match = amount.match(/^([\d.\/]+)\s*(.*)/);
    if (!match) return amount;
    let num = parseFloat(match[1]);
    if (match[1].includes('/')) {
      const [n, d] = match[1].split('/');
      num = parseFloat(n) / parseFloat(d);
    }
    if (isNaN(num)) return amount;
    const scaled = Math.round(num * scale * 10) / 10;
    return `${scaled}${match[2] ? ' ' + match[2] : ''}`;
>>>>>>> Stashed changes
  }
};
