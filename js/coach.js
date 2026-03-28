const Coach = {
  selectedMealTypes: [],
  selectedDietFilters: [],
  customRequest: '',
  lastSuggestions: null,

  renderCoachScreen() {
    const profile = Store.getProfile();
    const totals = Store.getTodayTotals();
    const remaining = {
      calories: Math.max(0, profile.macros.calories - totals.calories),
      protein: Math.max(0, profile.macros.protein - totals.protein),
      carbs: Math.max(0, profile.macros.carbs - totals.carbs),
      fat: Math.max(0, profile.macros.fat - totals.fat)
    };
    const prefs = Store.getPreferences();

    const screen = UI.$('#screen-coach');
    screen.innerHTML = `
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

      <button class="btn btn-coach" id="btn-suggest" disabled>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        Pick a meal type first
      </button>

      <button class="btn btn-outline btn-full" id="btn-meal-plan" style="margin-top:8px">
        Generate Weekly Meal Plan
      </button>

      <div id="coach-results"></div>

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

    this._bindMealTypePills();
    this._bindDietFilters();
    this._bindPrefRemove();
    this._bindPantry();
    UI.$('#btn-suggest').addEventListener('click', () => this.getSuggestion());
    UI.$('#btn-meal-plan')?.addEventListener('click', () => this.generateMealPlan());
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

      this.selectedMealTypes = Array.from(UI.$$('.meal-type-pill.active')).map(p => p.dataset.type);

      const btn = UI.$('#btn-suggest');
      if (this.selectedMealTypes.length === 0) {
        btn.disabled = true;
        btn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          Pick a meal type first
        `;
      } else {
        btn.disabled = false;
        const selected = this.selectedMealTypes.map(t => labels[t]).join(' + ');
        btn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          Suggest ${selected}
        `;
      }
    });
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

  async getSuggestion() {
    const profile = Store.getProfile();
    if (!profile.apiKey) {
      UI.toast('Set your API key in Profile first', 'error');
      App.navigate('profile');
      return;
    }
    if (this.selectedMealTypes.length === 0) {
      UI.toast('Pick at least one meal type', 'error');
      return;
    }

    UI.showLoading('Your coach is thinking...');

    this.customRequest = UI.$('#coach-custom')?.value.trim() || '';
    const pantry = Store.getPantry();
    const pantryOnly = UI.$('#chk-pantry-only')?.checked || false;
    let pantryText = '';
    if (pantry.length > 0) {
      pantryText = pantryOnly
        ? `\nINGREDIENTS AVAILABLE (ONLY use these): ${pantry.join(', ')}`
        : `\nIngredients client has at home (prefer these): ${pantry.join(', ')}`;
    }
    const fullCustom = (this.customRequest + pantryText).trim();

    try {
      const result = await LLM.getCoachSuggestion(this.selectedMealTypes, this.selectedDietFilters, fullCustom);
      this.lastSuggestions = result;
      this.showSuggestions(result);
    } catch (err) {
      UI.toast(err.message, 'error');
    } finally {
      UI.hideLoading();
    }
  },

  showSuggestions(result) {
    const container = UI.$('#coach-results');
    container.innerHTML = `
      ${result.top_pick_reason ? `<div class="top-pick-banner"><div class="top-pick-label">Why #1 is your best pick right now</div><div class="top-pick-text">${result.top_pick_reason}</div></div>` : ''}
      ${result.reasoning ? `<div class="coach-reasoning">${result.reasoning}</div>` : ''}
      ${result.suggestions.map((s, i) => `
        <div class="suggestion-card ${i === 0 ? 'top-pick' : ''}" id="suggestion-${i}">
          <div class="suggestion-rank-badge">${i === 0 ? '#1 Best Pick' : `#${s.rank || i + 1}`}</div>
          <div class="suggestion-header">
            <div class="suggestion-title">${s.name}</div>
            <div class="suggestion-actions">
              <button class="sug-btn sug-like" data-index="${i}" title="I like this kind of food">&#9829;</button>
              <button class="sug-btn sug-discard" data-index="${i}" title="Not for me">&#10005;</button>
            </div>
          </div>
          ${s.why ? `<div class="suggestion-why">${s.why}</div>` : ''}
          <div class="suggestion-desc">${s.description}</div>
          <div class="suggestion-macros">
            <span style="color:var(--cal-color)">${s.calories} cal</span>
            <span style="color:var(--protein-color)">${s.protein}g P</span>
            <span style="color:var(--carb-color)">${s.carbs}g C</span>
            <span style="color:var(--fat-color)">${s.fat}g F</span>
          </div>
          <div class="suggestion-btn-row">
            <button class="btn btn-recipe" data-index="${i}">View Recipe</button>
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
        btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px"></span> Generating...';

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
    if (!profile.apiKey) { UI.toast('Set API key first', 'error'); return; }

    UI.showLoading('Generating your weekly plan...');
    const pantry = Store.getPantry();
    const prefs = Store.getPreferences();
    const conditions = profile.healthConditions || [];

    const messages = [
      { role: 'system', content: `You are an elite nutrition coach. Create a 7-day meal plan.
Reply with ONLY valid JSON:
{
  "plan": [
    { "day": "Monday", "meals": [
      {"type": "breakfast", "name": "Meal name", "description": "portions", "calories": 0, "protein": 0, "carbs": 0, "fat": 0},
      {"type": "lunch", "name": "...", "description": "...", "calories": 0, "protein": 0, "carbs": 0, "fat": 0},
      {"type": "dinner", "name": "...", "description": "...", "calories": 0, "protein": 0, "carbs": 0, "fat": 0},
      {"type": "snack", "name": "...", "description": "...", "calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    ]}
  ]
}
Rules:
- 7 days (Mon-Sun), 4 meals each (breakfast, lunch, dinner, snack)
- Each day should hit daily macro targets closely
- Maximum variety across the week
- Practical, realistic meals with specific portions
- Respect all dietary requirements and health conditions
- Favor liked foods, avoid disliked foods
${pantry.length > 0 ? `- Prefer using these ingredients: ${pantry.join(', ')}` : ''}
${conditions.length > 0 ? `- Health conditions: ${conditions.join(', ')}` : ''}
${prefs.liked.length > 0 ? `- Likes: ${prefs.liked.join(', ')}` : ''}
${prefs.disliked.length > 0 ? `- Dislikes (AVOID): ${prefs.disliked.join(', ')}` : ''}` },
      { role: 'user', content: `Create a 7-day meal plan for:
- ${profile.gender}, ${profile.age}yo, ${profile.weight}${profile.unit === 'metric' ? 'kg' : 'lbs'}
- Goal: ${profile.goal}
- Daily targets: ${profile.macros.calories}cal / ${profile.macros.protein}g P / ${profile.macros.carbs}g C / ${profile.macros.fat}g F
${this.selectedDietFilters.length > 0 ? `- Diet: ${this.selectedDietFilters.join(', ')}` : ''}` }
    ];

    try {
      const response = await LLM.call(messages, profile, 4000);
      const cleaned = response.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
      const result = JSON.parse(cleaned);

      const container = UI.$('#coach-results');
      container.innerHTML = `
        <div class="card-title" style="margin-bottom:12px">Your Weekly Meal Plan</div>
        ${result.plan.map(day => `
          <div class="card meal-plan-day">
            <div class="meal-plan-day-title">${day.day}</div>
            ${day.meals.map(m => `
              <div class="meal-plan-item">
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
    } catch (err) {
      UI.toast(err.message || 'Failed to generate plan', 'error');
    } finally {
      UI.hideLoading();
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
          <div class="recipe-title">${recipe.name}</div>
          <div class="recipe-meta">
            ${recipe.prep_time ? `<span>Prep: ${recipe.prep_time}</span>` : ''}
            ${recipe.cook_time ? `<span>Cook: ${recipe.cook_time}</span>` : ''}
            ${recipe.servings ? `<span>Serves: ${recipe.servings}</span>` : ''}
          </div>
        </div>
        <div class="recipe-section">
          <div class="recipe-section-title">Ingredients</div>
          <ul class="recipe-list">
            ${recipe.ingredients.map(ing => `<li>${ing}</li>`).join('')}
          </ul>
        </div>
        <div class="recipe-section">
          <div class="recipe-section-title">Instructions</div>
          <ol class="recipe-steps">
            ${recipe.steps.map(step => `<li>${step}</li>`).join('')}
          </ol>
        </div>
        ${recipe.tips ? `
          <div class="recipe-section">
            <div class="recipe-section-title">Coach Tips</div>
            <div class="recipe-tips">${recipe.tips}</div>
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
  }
};
