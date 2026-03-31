const Recipes = {
  page: 1,
  filters: {},
  cache: {},
  _currentRecipe: null,
  _currentServings: null,

  async renderScreen() {
    const screen = UI.$('#screen-recipes');
    screen.innerHTML = `
      <div class="card">
        <div class="card-title">Browse Recipes</div>
        <div class="recipe-search-bar">
          <input type="text" class="food-input" id="recipe-search" placeholder="Search recipes...">
        </div>
        <div class="recipe-filter-row" id="cuisine-filters">
          ${['All','Italian','Mexican','Thai','Japanese','Indian','Greek','Korean','Mediterranean','American','Moroccan','French'].map(c =>
            `<button class="filter-chip ${c === 'All' ? 'active' : ''}" data-cuisine="${c === 'All' ? '' : c}">${c}</button>`
          ).join('')}
        </div>
        <div class="recipe-filter-row" id="meal-filters">
          ${[{l:'All',v:''},{l:'Breakfast',v:'breakfast'},{l:'Lunch',v:'lunch'},{l:'Dinner',v:'dinner'},{l:'Snack',v:'snack'},{l:'Pre-WO',v:'pre_workout'},{l:'Post-WO',v:'post_workout'}].map(m =>
            `<button class="filter-chip meal-chip ${!m.v ? 'active' : ''}" data-meal="${m.v}">${m.l}</button>`
          ).join('')}
        </div>
        <div class="recipe-filter-row" id="diet-chips">
          ${['High Protein','Low Carb','Vegan','Vegetarian','Gluten Free','Keto','Dairy Free','Paleo'].map(d =>
            `<button class="filter-chip diet-chip" data-diet="${d.toLowerCase().replace(/ /g, '_')}">${d}</button>`
          ).join('')}
        </div>
      </div>
      <div id="recipe-grid" class="recipe-grid"></div>
      <div id="recipe-pagination" class="recipe-pagination"></div>
      <div class="modal-overlay" id="recipe-detail-modal">
        <div class="recipe-detail-sheet" id="recipe-detail-content"></div>
      </div>
    `;
    this._bindFilters();
    this.loadRecipes();
  },

  _bindFilters() {
    UI.$('#recipe-search')?.addEventListener('input', this._debounce(() => {
      this.page = 1;
      this.loadRecipes();
    }, 300));

    UI.$('#cuisine-filters')?.addEventListener('click', e => {
      const chip = e.target.closest('.filter-chip');
      if (!chip) return;
      UI.$$('#cuisine-filters .filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      this.page = 1;
      this.loadRecipes();
    });

    UI.$('#meal-filters')?.addEventListener('click', e => {
      const chip = e.target.closest('.meal-chip');
      if (!chip) return;
      UI.$$('#meal-filters .meal-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      this.page = 1;
      this.loadRecipes();
    });

    UI.$('#diet-chips')?.addEventListener('click', e => {
      const chip = e.target.closest('.diet-chip');
      if (!chip) return;
      chip.classList.toggle('active');
      this.page = 1;
      this.loadRecipes();
    });

    UI.$('#recipe-detail-modal')?.addEventListener('click', e => {
      if (e.target.id === 'recipe-detail-modal') this.closeDetail();
    });
  },

  _debounce(fn, delay) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
  },

  _getFilters() {
    const search = UI.$('#recipe-search')?.value?.trim() || '';
    const cuisine = UI.$('#cuisine-filters .filter-chip.active')?.dataset?.cuisine || '';
    const meal = UI.$('#meal-filters .meal-chip.active')?.dataset?.meal || '';
    const diets = Array.from(UI.$$('#diet-chips .diet-chip.active')).map(c => c.dataset.diet);

    let qs = `?page=${this.page}&per_page=12`;
    if (search) qs += `&search=${encodeURIComponent(search)}`;
    if (cuisine) qs += `&cuisine=${encodeURIComponent(cuisine)}`;
    if (meal) qs += `&meal_type=${encodeURIComponent(meal)}`;
    if (diets.length) qs += `&diet=${encodeURIComponent(diets.join(','))}`;
    return qs;
  },

  async loadRecipes() {
    const grid = UI.$('#recipe-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="recipe-loading">Loading...</div>';

    try {
      const qs = this._getFilters();
      const res = await fetch(`/api/recipes${qs}`);
      if (!res.ok) throw new Error('Failed to load');
      const data = await res.json();

      if (data.recipes.length === 0) {
        grid.innerHTML = `
          <div class="recipe-empty">
            <div style="font-size:32px;margin-bottom:8px">&#127869;</div>
            <div>No recipes found</div>
            <div style="font-size:12px;color:var(--text-dim);margin-top:4px">Try different filters or generate more recipes</div>
          </div>
        `;
        UI.$('#recipe-pagination').innerHTML = '';
        return;
      }

      grid.innerHTML = data.recipes.map(r => `
        <div class="recipe-card" data-id="${r.id}">
          <div class="recipe-card-badges">
            ${r.cuisine && r.cuisine !== 'International' ? `<span class="rc-badge rc-cuisine">${r.cuisine}</span>` : ''}
            ${r.meal_type ? `<span class="rc-badge rc-meal">${r.meal_type.replace('_', '-')}</span>` : ''}
          </div>
          <div class="recipe-card-name">${r.name}</div>
          <div class="recipe-card-macros">
            <span class="rcm cal">${r.calories} cal</span>
            <span class="rcm prot">${r.protein}g P</span>
            <span class="rcm carb">${r.carbs}g C</span>
            <span class="rcm fat">${r.fat}g F</span>
          </div>
          <div class="recipe-card-meta">
            ${r.total_time_min ? `<span>${r.total_time_min} min</span>` : ''}
            ${r.difficulty ? `<span>${r.difficulty}</span>` : ''}
            ${r.category ? `<span>${r.category.replace('_', ' ')}</span>` : ''}
          </div>
        </div>
      `).join('');

      // Pagination
      const pag = UI.$('#recipe-pagination');
      if (data.pages > 1) {
        const pages = [];
        for (let i = 1; i <= Math.min(data.pages, 8); i++) pages.push(i);
        pag.innerHTML = pages.map(p =>
          `<button class="page-dot ${p === this.page ? 'active' : ''}" data-p="${p}">${p}</button>`
        ).join('') + (data.pages > 8 ? `<span class="page-more">/${data.pages}</span>` : '');
        pag.querySelectorAll('.page-dot').forEach(b => {
          b.onclick = () => { this.page = +b.dataset.p; this.loadRecipes(); };
        });
      } else {
        pag.innerHTML = '';
      }

      // Card click -> detail
      grid.querySelectorAll('.recipe-card').forEach(card => {
        card.onclick = () => this.showDetail(+card.dataset.id);
      });

    } catch (err) {
      grid.innerHTML = `<div class="recipe-empty"><div>Could not load recipes</div><div style="font-size:12px;color:var(--text-dim)">${err.message}</div></div>`;
    }
  },

  async showDetail(id) {
    const modal = UI.$('#recipe-detail-modal');
    const content = UI.$('#recipe-detail-content');
    if (!modal || !content) return;

    content.innerHTML = '<div class="recipe-loading">Loading...</div>';
    modal.classList.add('show');

    try {
      let recipe = this.cache[id];
      if (!recipe) {
        const res = await fetch(`/api/recipes/${id}`);
        if (!res.ok) throw new Error('Not found');
        recipe = await res.json();
        this.cache[id] = recipe;
      }

      const tags = recipe.tags || {};
      const goalTags = tags.goal || [];
      const healthTags = tags.health || [];
      const dietTags = tags.dietary || [];
      const timingTags = tags.timing || [];

      content.innerHTML = `
        <div class="rd-header">
          <button class="rd-close" id="rd-close">&times;</button>
          <div class="rd-cuisine">${recipe.cuisine || 'International'}${recipe.region && recipe.region !== 'International' ? ` · ${recipe.region}` : ''}</div>
          <div class="rd-name">${recipe.name}</div>
          ${recipe.description ? `<div class="rd-desc">${recipe.description}</div>` : ''}
          <div class="rd-meta-row">
            ${recipe.total_time_min ? `<span class="rd-meta-item">&#9201; ${recipe.total_time_min} min</span>` : ''}
            ${recipe.difficulty ? `<span class="rd-meta-item">${recipe.difficulty}</span>` : ''}
            ${recipe.servings ? `<span class="rd-meta-item rd-servings-wrap">
              <button class="rd-serving-btn" id="rd-serving-minus">&#8722;</button>
              <span id="rd-serving-count">Serves ${recipe.servings}</span>
              <button class="rd-serving-btn" id="rd-serving-plus">&#43;</button>
            </span>` : ''}
          </div>
        </div>

        <div class="rd-macros">
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--cal-color)">${recipe.calories}</div><div class="rd-macro-label">cal</div></div>
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--protein-color)">${recipe.protein}g</div><div class="rd-macro-label">protein</div></div>
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--carb-color)">${recipe.carbs}g</div><div class="rd-macro-label">carbs</div></div>
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--fat-color)">${recipe.fat}g</div><div class="rd-macro-label">fat</div></div>
          ${recipe.fiber ? `<div class="rd-macro"><div class="rd-macro-val" style="color:#56ab2f">${recipe.fiber}g</div><div class="rd-macro-label">fiber</div></div>` : ''}
        </div>

        ${goalTags.length || healthTags.length || dietTags.length ? `
          <div class="rd-tags">
            ${goalTags.map(t => `<span class="rd-tag rd-tag-goal">${t.replace(/_/g, ' ')}</span>`).join('')}
            ${healthTags.map(t => `<span class="rd-tag rd-tag-health">${t.replace(/_/g, ' ')}</span>`).join('')}
            ${dietTags.filter(t => !['gluten_free','dairy_free','soy_free','nut_free','egg_free','seafood_free','sesame_free'].includes(t) || recipe.allergens?.length).slice(0, 8).map(t => `<span class="rd-tag rd-tag-diet">${t.replace(/_/g, ' ')}</span>`).join('')}
          </div>
        ` : ''}

        <div class="rd-section">
          <div class="rd-section-title">Ingredients</div>
          <ul class="rd-list">
            ${(recipe.ingredients || []).map(i => `<li>${typeof i === 'string' ? i : `${i.amount || ''} ${i.item || ''}`}</li>`).join('')}
          </ul>
        </div>

        <div class="rd-section">
          <div class="rd-section-title">Instructions</div>
          <ol class="rd-steps">
            ${(recipe.steps || []).map(s => `<li>${s}</li>`).join('')}
          </ol>
        </div>

        ${recipe.tips ? `
          <div class="rd-section">
            <div class="rd-section-title">Coach Tip</div>
            <div class="rd-tip">${recipe.tips}</div>
          </div>
        ` : ''}

        <div class="rd-actions">
          <button class="btn rd-btn-log" data-id="${recipe.id}">Log This Meal</button>
          <button class="btn btn-outline rd-btn-like" data-name="${recipe.name}">&#9829; Like</button>
        </div>
      `;

      UI.$('#rd-close')?.addEventListener('click', () => this.closeDetail());

      // Servings adjuster
      this._currentRecipe = recipe;
      this._currentServings = recipe.servings || 1;
      UI.$('#rd-serving-minus')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (this._currentServings > 1) {
          this._currentServings--;
          this._scaleRecipe();
        }
      });
      UI.$('#rd-serving-plus')?.addEventListener('click', (e) => {
        e.stopPropagation();
        this._currentServings++;
        this._scaleRecipe();
      });

      content.querySelector('.rd-btn-log')?.addEventListener('click', () => {
        Store.addMeal({
          time: new Date().toISOString(),
          description: recipe.name,
          items: [{ name: recipe.name, calories: recipe.calories, protein: recipe.protein, carbs: recipe.carbs, fat: recipe.fat, sugar_natural: 0, sugar_processed: 0, fiber: recipe.fiber || 0 }],
          total: { calories: recipe.calories, protein: recipe.protein, carbs: recipe.carbs, fat: recipe.fat, sugar_natural: 0, sugar_processed: 0, fiber: recipe.fiber || 0 }
        });
        UI.toast(`${recipe.name} logged!`, 'success');
        this.closeDetail();
      });

      content.querySelector('.rd-btn-like')?.addEventListener('click', function() {
        Store.addPreference('liked', recipe.name);
        this.textContent = 'Liked!';
        this.disabled = true;
        UI.toast(`Added "${recipe.name}" to favorites`, 'success');
      });

    } catch (err) {
      content.innerHTML = `<div class="recipe-empty">${err.message}</div>`;
    }
  },

  async _scaleRecipe() {
    const recipe = this._currentRecipe;
    if (!recipe || !recipe.id) return;

    try {
      const res = await fetch(`/api/recipes/${recipe.id}/scale?servings=${this._currentServings}`);
      if (!res.ok) return;
      const scaled = await res.json();

      // Update serving count display
      const countEl = UI.$('#rd-serving-count');
      if (countEl) countEl.textContent = `Serves ${this._currentServings}`;

      // Update macros display
      const macroContainer = document.querySelector('.rd-macros');
      if (macroContainer) {
        macroContainer.innerHTML = `
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--cal-color)">${scaled.calories}</div><div class="rd-macro-label">cal</div></div>
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--protein-color)">${scaled.protein}g</div><div class="rd-macro-label">protein</div></div>
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--carb-color)">${scaled.carbs}g</div><div class="rd-macro-label">carbs</div></div>
          <div class="rd-macro"><div class="rd-macro-val" style="color:var(--fat-color)">${scaled.fat}g</div><div class="rd-macro-label">fat</div></div>
          ${scaled.fiber ? `<div class="rd-macro"><div class="rd-macro-val" style="color:#56ab2f">${scaled.fiber}g</div><div class="rd-macro-label">fiber</div></div>` : ''}
        `;
      }

      // Update ingredients
      const ingList = document.querySelector('.rd-list');
      if (ingList && scaled.ingredients) {
        ingList.innerHTML = scaled.ingredients.map(i =>
          `<li>${typeof i === 'string' ? i : `${i.amount || ''} ${i.item || ''}`}</li>`
        ).join('');
      }

      // Show scale factor badge
      if (scaled.scale_factor && scaled.scale_factor !== 1) {
        const badge = document.querySelector('.rd-scale-badge');
        if (badge) {
          badge.textContent = `${scaled.scale_factor}x`;
        } else {
          const countEl2 = UI.$('#rd-serving-count');
          if (countEl2) {
            countEl2.insertAdjacentHTML('afterend', `<span class="rd-scale-badge">${scaled.scale_factor}x</span>`);
          }
        }
      } else {
        document.querySelector('.rd-scale-badge')?.remove();
      }
    } catch (err) {
      console.error('Scale failed:', err);
    }
  },

  closeDetail() {
    UI.$('#recipe-detail-modal')?.classList.remove('show');
    this._currentRecipe = null;
    this._currentServings = null;
  }
};
