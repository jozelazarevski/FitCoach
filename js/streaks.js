/**
 * Streak & Habit Tracking
 *
 * - Daily logging streak counter
 * - Water intake goal tracking
 * - Weekly macro adherence badges
 * - Milestone celebrations
 */
const Streaks = {

  WATER_TARGET: 2300, // ml

  /**
   * Compute all streak and badge data.
   */
  getStreakData() {
    const allDays = Store.getAllDays();
    const profile = Store.getProfile();
    const targets = profile.macros;

    return {
      loggingStreak: this._computeLoggingStreak(allDays),
      totalDaysLogged: allDays.length,
      waterToday: this._getWaterProgress(),
      badges: this._computeBadges(allDays, targets),
      milestones: this._checkMilestones(allDays),
    };
  },

  /**
   * Count consecutive days with logged meals ending today or yesterday.
   */
  _computeLoggingStreak(allDays) {
    if (allDays.length === 0) return 0;

    const today = new Date();
    const todayKey = today.toISOString().split('T')[0];
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayKey = yesterday.toISOString().split('T')[0];

    // Build a set for fast lookup
    const daySet = new Set(allDays);

    // Streak must include today or yesterday
    let startKey = todayKey;
    if (!daySet.has(todayKey)) {
      if (daySet.has(yesterdayKey)) {
        startKey = yesterdayKey;
      } else {
        return 0;
      }
    }

    let streak = 0;
    const d = new Date(startKey + 'T12:00:00');
    while (daySet.has(d.toISOString().split('T')[0])) {
      streak++;
      d.setDate(d.getDate() - 1);
    }

    return streak;
  },

  _getWaterProgress() {
    const today = Store.getTodayKey();
    const current = Store.getWater(today);
    return {
      current,
      target: this.WATER_TARGET,
      percent: Math.min(Math.round((current / this.WATER_TARGET) * 100), 100),
    };
  },

  /**
   * Compute weekly badges: protein adherence, calorie consistency, etc.
   */
  _computeBadges(allDays, targets) {
    const badges = [];
    const today = new Date();

    // Look at last 7 days
    let proteinHits = 0;
    let calorieHits = 0;
    let loggedDays = 0;

    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const totals = Store.getDayTotals(key);

      if (totals.calories > 0) {
        loggedDays++;
        if (targets.protein && totals.protein >= targets.protein * 0.9) proteinHits++;
        if (targets.calories) {
          const ratio = totals.calories / targets.calories;
          if (ratio >= 0.9 && ratio <= 1.1) calorieHits++;
        }
      }
    }

    if (proteinHits >= 5) {
      badges.push({ icon: '&#128170;', name: 'Protein Pro', desc: `Hit protein target ${proteinHits}/7 days` });
    } else if (proteinHits >= 3) {
      badges.push({ icon: '&#127942;', name: 'Protein Rising', desc: `Hit protein target ${proteinHits}/7 days` });
    }

    if (calorieHits >= 5) {
      badges.push({ icon: '&#127919;', name: 'Calorie Sniper', desc: `On calorie target ${calorieHits}/7 days` });
    }

    if (loggedDays >= 7) {
      badges.push({ icon: '&#128221;', name: 'Full Week Logger', desc: 'Logged every day this week' });
    }

    // Water badge
    const water = this._getWaterProgress();
    if (water.percent >= 100) {
      badges.push({ icon: '&#128167;', name: 'Hydrated', desc: 'Hit water target today' });
    }

    return badges;
  },

  /**
   * Check for milestone achievements.
   */
  _checkMilestones(allDays) {
    const total = allDays.length;
    const streak = this._computeLoggingStreak(allDays);
    const milestones = [];

    // Streak milestones
    const streakLevels = [
      { days: 100, icon: '&#128293;', name: '100-Day Streak' },
      { days: 30, icon: '&#11088;', name: '30-Day Streak' },
      { days: 14, icon: '&#127775;', name: '2-Week Streak' },
      { days: 7, icon: '&#128077;', name: '7-Day Streak' },
      { days: 3, icon: '&#127793;', name: '3-Day Streak' },
    ];

    for (const level of streakLevels) {
      if (streak >= level.days) {
        milestones.push({ ...level, type: 'streak', achieved: true });
        break; // Only show highest streak milestone
      }
    }

    // Total days milestones
    const totalLevels = [
      { days: 365, icon: '&#127881;', name: '1 Year of Tracking' },
      { days: 100, icon: '&#128640;', name: '100 Days Tracked' },
      { days: 30, icon: '&#127947;', name: '30 Days Tracked' },
      { days: 7, icon: '&#128170;', name: 'First Week' },
    ];

    for (const level of totalLevels) {
      if (total >= level.days) {
        milestones.push({ ...level, type: 'total', achieved: true });
        break;
      }
    }

    // Recipes tried
    const foodSet = new Set();
    allDays.forEach(dateKey => {
      const meals = Store.getDayMeals(dateKey);
      meals.forEach(m => (m.items || []).forEach(i => {
        if (i.name) foodSet.add(i.name.toLowerCase().trim());
      }));
    });

    if (foodSet.size >= 100) {
      milestones.push({ icon: '&#127860;', name: '100 Different Foods', type: 'variety', achieved: true });
    } else if (foodSet.size >= 50) {
      milestones.push({ icon: '&#127869;', name: '50 Different Foods', type: 'variety', achieved: true });
    }

    return milestones;
  },

  /**
   * Render the streak card for the dashboard.
   */
  renderCard() {
    const data = this.getStreakData();

    return `
      <div class="card streak-card">
        <div class="card-title">Streaks & Habits</div>

        <div class="streak-row">
          <div class="streak-counter">
            <div class="streak-flame">${data.loggingStreak > 0 ? '&#128293;' : '&#9898;'}</div>
            <div class="streak-number">${data.loggingStreak}</div>
            <div class="streak-label">day streak</div>
          </div>

          <div class="streak-water">
            <div class="streak-water-ring" style="--water-pct:${data.waterToday.percent}">
              <span class="streak-water-val">${Math.round(data.waterToday.current / 1000 * 10) / 10}L</span>
            </div>
            <div class="streak-label">water</div>
          </div>

          <div class="streak-counter">
            <div class="streak-flame">&#128197;</div>
            <div class="streak-number">${data.totalDaysLogged}</div>
            <div class="streak-label">days logged</div>
          </div>
        </div>

        ${data.badges.length > 0 ? `
          <div class="streak-badges">
            ${data.badges.map(b => `
              <div class="streak-badge">
                <span class="streak-badge-icon">${b.icon}</span>
                <div>
                  <div class="streak-badge-name">${b.name}</div>
                  <div class="streak-badge-desc">${b.desc}</div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : ''}

        ${data.milestones.length > 0 ? `
          <div class="streak-milestones">
            ${data.milestones.map(m => `
              <span class="streak-milestone">${m.icon} ${m.name}</span>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  },
};
