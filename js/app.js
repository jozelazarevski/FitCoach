const App = {
  currentScreen: 'dashboard',
  historyMonth: new Date(),

  init() {
    // Auth gate: require login before anything
    if (!Auth.isLoggedIn()) {
      Auth.renderAuthScreen();
      this.bindNav();
      return;
    }

    if (!Store.isProfileComplete()) {
      Profile.renderOnboarding();
    }
    this.bindNav();
    this.navigate('dashboard');
  },

  bindNav() {
    UI.$$('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.screen;
        if (target) this.navigate(target);
      });
    });
  },

  navigate(screen) {
    this.currentScreen = screen;

    UI.$$('.screen').forEach(s => s.classList.remove('active'));
    UI.$(`#screen-${screen}`)?.classList.add('active');

    UI.$$('.nav-btn').forEach(b => b.classList.remove('active'));
    UI.$(`.nav-btn[data-screen="${screen}"]`)?.classList.add('active');

    // Update header
    const titles = { dashboard: 'FitCoach', coach: 'AI Coach', recipes: 'Recipes', body: 'Body & Workouts', history: 'History', profile: 'Profile' };
    UI.$('.header h1').textContent = titles[screen] || 'FitCoach';

    switch (screen) {
      case 'dashboard': this.renderDashboard(); break;
      case 'coach': Coach.renderCoachScreen(); break;
      case 'recipes': Recipes.renderScreen(); break;
      case 'body': BodyTrack.renderScreen(); break;
      case 'history': this.renderHistory(); break;
      case 'profile': Profile.renderProfileForm(); break;
    }
  },

  refreshDashboard() {
    if (this.currentScreen === 'dashboard') this.renderDashboard();
  },

  renderDashboard() {
    const profile = Store.getProfile();
    const totals = Store.getTodayTotals();
    const meals = Store.getTodayMeals();
    const adaptiveResult = typeof Adaptive !== 'undefined' ? Adaptive.getAdaptiveTargets() : null;
    const targets = adaptiveResult && adaptiveResult.adjustments.length > 0 ? adaptiveResult.adjusted : profile.macros;

    const screen = UI.$('#screen-dashboard');

    screen.innerHTML = `
      ${Tracker.renderFoodInput()}

      <div class="card">
        <div class="card-title">Today's Macros</div>
        <div class="macro-grid">
          <div class="macro-item full-width">
            <div class="macro-label">
              <span>Calories</span>
              <span>${UI.formatNum(totals.calories)} / ${UI.formatNum(targets.calories)}</span>
            </div>
            <div class="macro-value" style="color:var(--cal-color)">${UI.formatNum(totals.calories)}</div>
            <div class="progress-bar">
              <div class="progress-fill cal" style="width:${UI.progressPercent(totals.calories, targets.calories)}%"></div>
            </div>
          </div>
          <div class="macro-item">
            <div class="macro-label">
              <span>Protein</span>
              <span>${totals.protein}/${targets.protein}g</span>
            </div>
            <div class="macro-value" style="color:var(--protein-color)">${totals.protein}g</div>
            <div class="progress-bar">
              <div class="progress-fill protein" style="width:${UI.progressPercent(totals.protein, targets.protein)}%"></div>
            </div>
          </div>
          <div class="macro-item">
            <div class="macro-label">
              <span>Carbs</span>
              <span>${totals.carbs}/${targets.carbs}g</span>
            </div>
            <div class="macro-value" style="color:var(--carb-color)">${totals.carbs}g</div>
            <div class="progress-bar">
              <div class="progress-fill carb" style="width:${UI.progressPercent(totals.carbs, targets.carbs)}%"></div>
            </div>
          </div>
          <div class="macro-item">
            <div class="macro-label">
              <span>Fat</span>
              <span>${totals.fat}/${targets.fat}g</span>
            </div>
            <div class="macro-value" style="color:var(--fat-color)">${totals.fat}g</div>
            <div class="progress-bar">
              <div class="progress-fill fat" style="width:${UI.progressPercent(totals.fat, targets.fat)}%"></div>
            </div>
          </div>
          <div class="macro-item">
            <div class="macro-label">
              <span>Fiber</span>
              <span>${totals.fiber >= 25 ? '✓ Good' : totals.calories > 500 && totals.fiber < 10 ? '⚠ Low' : ''}</span>
            </div>
            <div class="macro-value" style="color:#56ab2f;font-size:18px">${totals.fiber}g</div>
            <div class="progress-bar">
              <div class="progress-fill" style="width:${UI.progressPercent(totals.fiber, 30)}%;background:linear-gradient(90deg,#56ab2f,#a8e063)"></div>
            </div>
          </div>
          <div class="macro-item">
            <div class="macro-label"><span>Natural Sugar</span></div>
            <div class="macro-value" style="color:#a8e063;font-size:18px">${totals.sugar_natural}g</div>
          </div>
          <div class="macro-item">
            <div class="macro-label">
              <span>Processed Sugar</span>
              ${totals.sugar_processed > 25 ? '<span style="color:var(--accent-orange)">⚠ High</span>' : ''}
            </div>
            <div class="macro-value" style="color:#f7971e;font-size:18px">${totals.sugar_processed}g</div>
          </div>
        </div>
      </div>


      ${typeof Adaptive !== 'undefined' ? Adaptive.renderCard() : ''}

      ${this._renderMacroGapCard(totals, targets)}

      <button class="btn btn-coach" id="btn-dashboard-coach">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        What should I eat next?
      </button>

      <div class="card">
        <div class="card-title">Today's Meals</div>
        ${Tracker.renderMealsList(meals)}
      </div>
    `;

    Tracker.bindFoodInput();
    Tracker.bindDeleteButtons();

    UI.$('#btn-dashboard-coach')?.addEventListener('click', () => {
      this.navigate('coach');
    });

    UI.$('#btn-gap-advisor')?.addEventListener('click', () => this.getGapAdvice());
  },

  _renderMacroGapCard(totals, targets) {
    const gaps = [];
    const proteinGap = targets.protein - totals.protein;
    const carbGap = targets.carbs - totals.carbs;
    const fatGap = targets.fat - totals.fat;
    const calGap = targets.calories - totals.calories;

    if (proteinGap > 15) gaps.push({ macro: 'Protein', amount: proteinGap, unit: 'g', color: 'var(--protein-color)' });
    if (carbGap > 20) gaps.push({ macro: 'Carbs', amount: carbGap, unit: 'g', color: 'var(--carb-color)' });
    if (fatGap > 10) gaps.push({ macro: 'Fat', amount: fatGap, unit: 'g', color: 'var(--fat-color)' });

    if (gaps.length === 0 || targets.calories === 0) return '';

    const biggestGap = gaps.reduce((a, b) => a.amount > b.amount ? a : b);

    return `
      <div class="card gap-card">
        <div class="card-title">Macro Gap Alert</div>
        <div class="gap-summary">
          ${gaps.map(g => `
            <div class="gap-item">
              <span class="gap-amount" style="color:${g.color}">${g.amount}${g.unit}</span>
              <span class="gap-label">${g.macro} left</span>
            </div>
          `).join('')}
        </div>
        <div class="gap-hint">
          ${proteinGap > 30 ? 'Still short on protein. A shake, Greek yogurt, or eggs could close the gap fast.' :
            proteinGap > 15 ? 'A small protein boost would help - cottage cheese, jerky, or a half scoop shake.' :
            carbGap > 30 ? 'Carbs are low - oats, rice, fruit, or a banana could help.' :
            fatGap > 15 ? 'Healthy fats needed - nuts, avocado, or olive oil drizzle.' : 'You have some macros to fill.'}
        </div>
        <button class="btn btn-gap" id="btn-gap-advisor">
          How should I fill this gap?
        </button>
        <div id="gap-advice"></div>
      </div>
    `;
  },

  async getGapAdvice() {
    const profile = Store.getProfile();
    if (!profile.apiKey) {
      UI.toast('Set your API key in Profile first', 'error');
      App.navigate('profile');
      return;
    }

    const btn = UI.$('#btn-gap-advisor');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px"></span> Thinking...';

    try {
      const result = await LLM.getGapAdvice();
      const container = UI.$('#gap-advice');
      const options = result.options || result.suggestions || [];
      container.innerHTML = `
        <div class="gap-advice-content">
          ${result.assessment ? `<div class="gap-assessment">${UI.esc(result.assessment)}</div>` : ''}
          <div class="gap-options">
            ${options.map((opt, i) => {
              const isSupplement = (opt.type || '').toLowerCase().includes('supplement');
              return `
              <div class="gap-option ${isSupplement ? 'gap-supplement' : 'gap-food'}">
                <div class="gap-option-header">
                  <span class="gap-option-rank">${i + 1}</span>
                  <span class="gap-option-type">${isSupplement ? 'Supplement' : 'Whole Food'}</span>
                </div>
                <div class="gap-option-name">${UI.esc(opt.name || 'Option')}</div>
                <div class="gap-option-desc">${UI.esc(opt.description || '')}</div>
                <div class="gap-option-macros">
                  <span style="color:var(--cal-color)">${opt.calories || 0} cal</span>
                  <span style="color:var(--protein-color)">${opt.protein || 0}g P</span>
                  <span style="color:var(--carb-color)">${opt.carbs || 0}g C</span>
                  <span style="color:var(--fat-color)">${opt.fat || 0}g F</span>
                </div>
                ${opt.tip ? `<div class="gap-option-tip">${UI.esc(opt.tip)}</div>` : ''}
                <div class="gap-option-btns">
                  <button class="btn btn-log-option" data-index="${i}">I had this - log it</button>
                  <button class="btn btn-decline-option" data-index="${i}" title="Don't suggest this again" style="background:transparent;border:1px solid var(--border);color:var(--text-dim);padding:8px 12px;font-size:12px">&#10005; Not for me</button>
                </div>
              </div>
            `;}).join('')}
          </div>
        </div>
      `;
      this._lastGapOptions = options;
      UI.$$('.btn-log-option').forEach(b => {
        b.addEventListener('click', e => {
          const idx = parseInt(b.dataset.index);
          const opt = this._lastGapOptions[idx];
          if (!opt) return;
          Store.addMeal({
            time: new Date().toISOString(),
            description: opt.name,
            items: [{ name: opt.name, calories: opt.calories||0, protein: opt.protein||0, carbs: opt.carbs||0, fat: opt.fat||0 }],
            total: { calories: opt.calories||0, protein: opt.protein||0, carbs: opt.carbs||0, fat: opt.fat||0, sugar_natural: 0, sugar_processed: 0 }
          });
          b.textContent = 'Logged!';
          b.disabled = true;
          b.classList.add('logged');
          UI.toast(`${opt.name} logged!`, 'success');
          setTimeout(() => this.refreshDashboard(), 1500);
        });
      });
      UI.$$('.btn-decline-option').forEach(b => {
        b.addEventListener('click', () => {
          const idx = parseInt(b.dataset.index);
          const opt = this._lastGapOptions[idx];
          if (!opt) return;
          Store.addPreference('disliked', opt.name);
          const card = b.closest('.gap-option');
          card.classList.add('discarded');
          setTimeout(() => { card.style.display = 'none'; }, 400);
          UI.toast(`"${opt.name}" won't be suggested again`, 'success');
        });
      });
      btn.textContent = 'Refresh advice';
      btn.disabled = false;
    } catch (err) {
      UI.toast(err.message, 'error');
      btn.textContent = 'How should I fill this gap?';
      btn.disabled = false;
    }
  },

  renderHistory() {
    const screen = UI.$('#screen-history');
    const year = this.historyMonth.getFullYear();
    const month = this.historyMonth.getMonth();
    const monthName = this.historyMonth.toLocaleString('default', { month: 'long', year: 'numeric' });

    // Get all days in this month that have logs
    const allDays = Store.getAllDays();
    const monthDays = allDays.filter(d => {
      const dt = new Date(d + 'T12:00:00');
      return dt.getFullYear() === year && dt.getMonth() === month;
    });

    const weekAvg = Store.getWeekAverage();

    screen.innerHTML = `
      ${typeof Insights !== 'undefined' ? Insights.render() : ''}

      ${weekAvg ? `
        <div class="weekly-avg">
          <div class="weekly-avg-title">7-Day Average (${weekAvg.days} days)</div>
          <div class="weekly-avg-values">
            <span style="color:var(--cal-color)">${weekAvg.calories} cal</span>
            <span style="color:var(--protein-color)">${weekAvg.protein}g P</span>
            <span style="color:var(--carb-color)">${weekAvg.carbs}g C</span>
            <span style="color:var(--fat-color)">${weekAvg.fat}g F</span>
          </div>
        </div>
      ` : ''}

      <div class="history-nav">
        <button class="history-nav-btn" id="hist-prev">&larr;</button>
        <span class="history-month">${monthName}</span>
        <button class="history-nav-btn" id="hist-next">&rarr;</button>
      </div>

      <div id="history-days">
        ${monthDays.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">&#128197;</div>
            <div class="empty-state-text">No meals logged this month</div>
          </div>
        ` : monthDays.map(dateKey => {
          const totals = Store.getDayTotals(dateKey);
          return `
            <div class="history-day" data-date="${dateKey}">
              <div class="history-day-header">
                <span class="history-day-date">${UI.formatDate(dateKey)}</span>
                <span class="history-day-cals">${totals.calories} cal</span>
              </div>
              <div class="history-day-macros">
                <span>${UI.macroDot('protein')} ${totals.protein}g P</span>
                <span>${UI.macroDot('carb')} ${totals.carbs}g C</span>
                <span>${UI.macroDot('fat')} ${totals.fat}g F</span>
              </div>
              <div class="history-detail" id="detail-${dateKey}"></div>
            </div>
          `;
        }).join('')}
      </div>
    `;

    if (typeof Insights !== 'undefined') Insights.bind();

    UI.$('#hist-prev')?.addEventListener('click', () => {
      this.historyMonth.setMonth(this.historyMonth.getMonth() - 1);
      this.renderHistory();
    });

    UI.$('#hist-next')?.addEventListener('click', () => {
      this.historyMonth.setMonth(this.historyMonth.getMonth() + 1);
      this.renderHistory();
    });

    UI.$$('.history-day').forEach(day => {
      day.addEventListener('click', () => {
        const dateKey = day.dataset.date;
        const detail = UI.$(`#detail-${dateKey}`);
        if (detail.classList.contains('show')) {
          UI.hide(detail);
          return;
        }

        // Close all other details
        UI.$$('.history-detail').forEach(d => d.classList.remove('show'));

        const meals = Store.getDayMeals(dateKey);
        detail.innerHTML = meals.map(meal => `
          <div class="meal-card" style="margin-top:8px">
            <div class="meal-card-header">
              <span class="meal-time">${UI.formatTime(meal.time)}</span>
            </div>
            <div class="meal-name">${UI.esc(meal.description || meal.items?.map(i => i.name).join(', '))}</div>
            <div class="meal-macros">
              <span>${UI.macroDot('cal')} ${meal.total.calories} cal</span>
              <span>${UI.macroDot('protein')} ${meal.total.protein}g P</span>
              <span>${UI.macroDot('carb')} ${meal.total.carbs}g C</span>
              <span>${UI.macroDot('fat')} ${meal.total.fat}g F</span>
            </div>
          </div>
        `).join('');
        UI.show(detail);
      });
    });
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());
