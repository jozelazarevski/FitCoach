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

      ${typeof Streaks !== 'undefined' ? Streaks.renderCard() : ''}

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

      ${typeof MealHistory !== 'undefined' ? MealHistory.renderInsightsCard() : ''}

      ${this._renderCoachingInsights(totals, targets, meals)}

      ${this._renderMacroGapCard(totals, targets)}

      ${this._renderWeeklySummary(targets)}

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

  _renderWeeklySummary(targets) {
    try {
      const data = Store.load();
      const days = [];
      for (let i = 1; i <= 7; i++) {
        const d = new Date(); d.setDate(d.getDate() - i);
        const key = d.toISOString().split('T')[0];
        const entry = data.logs[key];
        const meals = Array.isArray(entry) ? entry : (entry?.meals || []);
        if (meals.length > 0) {
          const dayCal = meals.reduce((s, m) => s + (m.total?.calories || 0), 0);
          const dayProt = meals.reduce((s, m) => s + (m.total?.protein || 0), 0);
          const dayCarbs = meals.reduce((s, m) => s + (m.total?.carbs || 0), 0);
          const dayFat = meals.reduce((s, m) => s + (m.total?.fat || 0), 0);
          const hitCal = Math.abs(dayCal - targets.calories) < targets.calories * 0.15;
          const hitProt = dayProt >= targets.protein * 0.85;
          days.push({ cal: dayCal, prot: dayProt, carbs: dayCarbs, fat: dayFat, hitCal, hitProt });
        }
      }
      if (days.length < 2) return '';

      const avgCal = Math.round(days.reduce((s, d) => s + d.cal, 0) / days.length);
      const avgProt = Math.round(days.reduce((s, d) => s + d.prot, 0) / days.length);
      const calHitDays = days.filter(d => d.hitCal).length;
      const protHitDays = days.filter(d => d.hitProt).length;
      const consistency = Math.round(((calHitDays + protHitDays) / (days.length * 2)) * 100);

      // Actionable tip
      let tip = '';
      if (protHitDays < days.length * 0.5) {
        tip = 'Protein has been consistently low. Try adding a protein source to every meal — eggs at breakfast, chicken at lunch, Greek yogurt as snack.';
      } else if (avgCal > targets.calories * 1.1) {
        tip = 'Calories trending above target. Try slightly smaller portions or swapping one snack for a lower-cal option.';
      } else if (consistency >= 80) {
        tip = 'Excellent consistency! Your nutrition discipline is paying off. Keep this rhythm going.';
      } else {
        tip = 'Focus on hitting protein first, then fill remaining calories with balanced carbs and fats.';
      }

      return `
        <div class="card">
          <div class="card-title">Weekly Summary (${days.length} days)</div>
          <div class="weekly-stats-grid">
            <div class="weekly-stat">
              <div class="weekly-stat-val" style="color:var(--cal-color)">${avgCal}</div>
              <div class="weekly-stat-label">avg cal/day</div>
              <div class="weekly-stat-target">${targets.calories > 0 ? (avgCal > targets.calories ? '↑' : '↓') + ' target ' + targets.calories : ''}</div>
            </div>
            <div class="weekly-stat">
              <div class="weekly-stat-val" style="color:var(--protein-color)">${avgProt}g</div>
              <div class="weekly-stat-label">avg protein</div>
              <div class="weekly-stat-target">${targets.protein > 0 ? (avgProt >= targets.protein * 0.85 ? '&#9989;' : '&#9888;') + ' target ' + targets.protein + 'g' : ''}</div>
            </div>
            <div class="weekly-stat">
              <div class="weekly-stat-val" style="color:var(--primary)">${consistency}%</div>
              <div class="weekly-stat-label">consistency</div>
              <div class="weekly-stat-target">${calHitDays}/${days.length} cal + ${protHitDays}/${days.length} prot</div>
            </div>
          </div>
          <div class="weekly-tip">${tip}</div>
        </div>
      `;
    } catch(e) {
      return '';
    }
  },

  _renderCoachingInsights(totals, targets, meals) {
    const hour = new Date().getHours();
    const profile = Store.getProfile();
    const insights = [];

    // Macro pacing
    const dayProgress = Math.min(hour / 21, 1.0);
    const calPacing = totals.calories / Math.max(targets.calories, 1);
    const protPacing = totals.protein / Math.max(targets.protein, 1);

    if (dayProgress > 0.4 && protPacing < dayProgress * 0.5 && targets.protein > 0) {
      insights.push({
        icon: '&#9888;&#65039;',
        text: `Protein behind schedule — ${totals.protein}g eaten (${Math.round(protPacing*100)}%) but ${Math.round(dayProgress*100)}% of day is done. Focus on high-protein meals.`,
        type: 'warning'
      });
    }

    if (dayProgress > 0.6 && calPacing > 0.9 && targets.calories > 0) {
      insights.push({
        icon: '&#9888;&#65039;',
        text: `Already at ${Math.round(calPacing*100)}% of calorie target. Keep remaining meals very light and protein-focused.`,
        type: 'warning'
      });
    }

    // Meal timing
    if (hour >= 13 && meals.length === 0) {
      insights.push({
        icon: '&#9200;',
        text: 'No meals logged yet today. Skipping meals can lead to overeating later — grab something balanced now.',
        type: 'alert'
      });
    } else if (hour >= 11 && meals.length === 1 && totals.calories < 300) {
      insights.push({
        icon: '&#127860;',
        text: 'Light breakfast so far. Time for a protein-rich lunch to keep energy steady.',
        type: 'info'
      });
    }

    // Workout awareness
    try {
      const todayWorkouts = Store.getTodayWorkouts ? Store.getTodayWorkouts() : [];
      if (todayWorkouts.length > 0) {
        const lastW = todayWorkouts[todayWorkouts.length - 1];
        const hoursAgo = (Date.now() - new Date(lastW.time).getTime()) / 3600000;
        if (hoursAgo < 2) {
          insights.push({
            icon: '&#128170;',
            text: `Workout ${Math.round(hoursAgo * 60)} min ago — eat protein + carbs within 2 hours for optimal recovery.`,
            type: 'workout'
          });
        } else if (totals.protein < targets.protein * 0.5) {
          insights.push({
            icon: '&#128170;',
            text: 'You worked out today but protein is low. Prioritize protein in your next meal for recovery.',
            type: 'workout'
          });
        }
      }
    } catch(e) {}

    // Hydration
    try {
      const water = Store.getTodayWater ? Store.getTodayWater() : 0;
      if (water < 500 && hour > 12) {
        insights.push({
          icon: '&#128167;',
          text: `Only ${water}ml water today. Aim for at least 2L — dehydration hurts performance and recovery.`,
          type: 'hydration'
        });
      }
    } catch(e) {}

    // Weekly protein trend
    try {
      const data = Store.load();
      let protDays = 0, lowProtDays = 0;
      for (let i = 1; i <= 7; i++) {
        const d = new Date(); d.setDate(d.getDate() - i);
        const key = d.toISOString().split('T')[0];
        const entry = data.logs[key];
        const dayMeals = Array.isArray(entry) ? entry : (entry?.meals || []);
        if (dayMeals.length > 0) {
          protDays++;
          const dayProt = dayMeals.reduce((sum, m) => sum + (m.total?.protein || 0), 0);
          if (dayProt < targets.protein * 0.8) lowProtDays++;
        }
      }
      if (protDays >= 3 && lowProtDays >= Math.ceil(protDays * 0.5)) {
        insights.push({
          icon: '&#128200;',
          text: `Weekly trend: protein was below target ${lowProtDays} of ${protDays} days. Consistently hitting protein is key for ${profile.goal === 'fat_loss' ? 'preserving muscle during fat loss' : 'muscle growth'}.`,
          type: 'trend'
        });
      }
    } catch(e) {}

    if (insights.length === 0) {
      // Positive reinforcement
      if (meals.length >= 2 && protPacing >= dayProgress * 0.8) {
        insights.push({
          icon: '&#9989;',
          text: 'Great macro pacing today! You\'re on track with protein. Keep it up.',
          type: 'positive'
        });
      } else {
        return '';
      }
    }

    const typeColors = {
      warning: 'var(--accent-orange)',
      alert: 'var(--accent-red)',
      workout: 'var(--primary)',
      hydration: 'var(--accent-blue)',
      trend: 'var(--protein-color)',
      info: 'var(--text-dim)',
      positive: 'var(--accent-green)',
    };

    return `
      <div class="card coaching-insights-card">
        <div class="card-title">Coach Insights</div>
        ${insights.slice(0, 3).map(i => `
          <div class="coaching-insight" style="border-left: 3px solid ${typeColors[i.type] || 'var(--border)'}">
            <span class="coaching-insight-icon">${i.icon}</span>
            <span class="coaching-insight-text">${i.text}</span>
          </div>
        `).join('')}
      </div>
    `;
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
