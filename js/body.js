const BodyTrack = {
  renderScreen() {
    const profile = Store.getProfile();
    const water = Store.getWater();
    const waterTarget = Math.round(profile.weight * 33); // 33ml per kg
    const workouts = Store.getTodayWorkouts();
    const workoutCals = Store.getTodayWorkoutCalories();
    const bodyLog = Store.getBodyLog();
    const latest = Store.getLatestBody();
    const unit = profile.unit === 'metric' ? 'kg' : 'lbs';

    const screen = UI.$('#screen-body');
    screen.innerHTML = `
      <!-- WATER TRACKER -->
      <div class="card">
        <div class="card-title">Water Intake</div>
        <div class="water-display">
          <div class="water-visual">
            <div class="water-fill-bg">
              <div class="water-fill-bar" style="height:${Math.min(100, (water / waterTarget) * 100)}%"></div>
            </div>
            <div class="water-amount">${Math.round(water / 1000 * 10) / 10}L</div>
            <div class="water-target">of ${(waterTarget / 1000).toFixed(1)}L</div>
          </div>
          <div class="water-buttons">
            <button class="water-btn" data-ml="150">150ml</button>
            <button class="water-btn" data-ml="250">250ml</button>
            <button class="water-btn" data-ml="500">500ml</button>
            <button class="water-btn water-btn-minus" data-ml="-250">-250ml</button>
          </div>
        </div>
      </div>

      <!-- BODY LOG -->
      <div class="card">
        <div class="card-title">Body Log</div>
        ${latest ? `
          <div class="body-latest">
            <div class="body-stat">
              <div class="body-stat-value">${latest.weight} <span>${unit}</span></div>
              <div class="body-stat-label">Weight</div>
            </div>
            ${latest.bodyFat ? `
            <div class="body-stat">
              <div class="body-stat-value">${latest.bodyFat} <span>%</span></div>
              <div class="body-stat-label">Body Fat</div>
            </div>` : ''}
          </div>
        ` : ''}
        <div class="form-row" style="margin-top:10px">
          <div class="form-group" style="margin-bottom:0">
            <input type="number" class="form-input" id="inp-body-weight" placeholder="Weight (${unit})" step="0.1">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <input type="number" class="form-input" id="inp-body-fat" placeholder="Body fat %" step="0.1">
          </div>
        </div>
        <button class="btn btn-full" id="btn-log-body" style="margin-top:8px">Log Weigh-In</button>

        ${bodyLog.length > 1 ? `
        <div class="body-chart-wrap">
          <div class="card-title" style="margin-top:14px">Trend (last 30 entries)</div>
          <canvas id="body-chart" height="150"></canvas>
        </div>` : ''}
      </div>

      <!-- WORKOUTS -->
      <div class="card">
        <div class="card-title">Today's Workouts</div>
        ${workoutCals > 0 ? `<div class="workout-burn">Burned: <span>${workoutCals} cal</span></div>` : ''}
        <div id="workout-list">
          ${workouts.length === 0 ? '<div class="empty-state" style="padding:16px 0"><div class="empty-state-text">No workouts logged today</div></div>' :
            workouts.map((w, i) => `
              <div class="workout-card">
                <div class="workout-card-header">
                  <span class="workout-name">${w.name}</span>
                  <button class="meal-delete workout-delete" data-index="${i}">&times;</button>
                </div>
                <div class="workout-details">
                  ${w.duration ? `<span>${w.duration} min</span>` : ''}
                  ${w.sets ? `<span>${w.sets} sets</span>` : ''}
                  ${w.reps ? `<span>${w.reps} reps</span>` : ''}
                  ${w.weight_used ? `<span>${w.weight_used}${unit}</span>` : ''}
                  ${w.caloriesBurned ? `<span class="workout-cal">-${w.caloriesBurned} cal</span>` : ''}
                </div>
              </div>
            `).join('')}
        </div>
        <div class="workout-add-form" id="workout-form">
          <div class="form-group" style="margin-bottom:8px">
            <input type="text" class="form-input" id="inp-workout-name" placeholder="Exercise name (e.g. Bench Press, Running)">
          </div>
          <div class="form-row">
            <div class="form-group" style="margin-bottom:0">
              <input type="number" class="form-input" id="inp-workout-duration" placeholder="Min">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <input type="number" class="form-input" id="inp-workout-cal" placeholder="Cal burned">
            </div>
          </div>
          <div class="form-row" style="margin-top:8px">
            <div class="form-group" style="margin-bottom:0">
              <input type="number" class="form-input" id="inp-workout-sets" placeholder="Sets">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <input type="number" class="form-input" id="inp-workout-reps" placeholder="Reps">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <input type="number" class="form-input" id="inp-workout-weight" placeholder="${unit}">
            </div>
          </div>
          <button class="btn btn-full" id="btn-log-workout" style="margin-top:8px">Log Workout</button>
        </div>
      </div>
    `;

    this._bindEvents();
    if (bodyLog.length > 1) this._drawChart(bodyLog);
  },

  _bindEvents() {
    // Water buttons
    UI.$$('.water-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const ml = parseInt(btn.dataset.ml);
        if (ml < 0) {
          Store.setWater(Math.max(0, Store.getWater() + ml));
        } else {
          Store.addWater(ml);
        }
        this.renderScreen();
      });
    });

    // Body log
    UI.$('#btn-log-body')?.addEventListener('click', () => {
      const weight = parseFloat(UI.$('#inp-body-weight')?.value);
      const bodyFat = parseFloat(UI.$('#inp-body-fat')?.value) || null;
      if (!weight) { UI.toast('Enter your weight', 'error'); return; }
      Store.addBodyEntry({ weight, bodyFat });
      UI.toast('Weigh-in logged!', 'success');
      this.renderScreen();
    });

    // Workout log
    UI.$('#btn-log-workout')?.addEventListener('click', () => {
      const name = UI.$('#inp-workout-name')?.value.trim();
      if (!name) { UI.toast('Enter exercise name', 'error'); return; }
      Store.addWorkout({
        name,
        duration: parseInt(UI.$('#inp-workout-duration')?.value) || null,
        caloriesBurned: parseInt(UI.$('#inp-workout-cal')?.value) || 0,
        sets: parseInt(UI.$('#inp-workout-sets')?.value) || null,
        reps: parseInt(UI.$('#inp-workout-reps')?.value) || null,
        weight_used: parseFloat(UI.$('#inp-workout-weight')?.value) || null
      });
      UI.toast('Workout logged!', 'success');
      this.renderScreen();
    });

    // Delete workout
    UI.$$('.workout-delete').forEach(btn => {
      btn.addEventListener('click', e => {
        Store.deleteWorkout(parseInt(btn.dataset.index));
        this.renderScreen();
      });
    });
  },

  _drawChart(bodyLog) {
    const canvas = UI.$('#body-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const entries = bodyLog.slice(-30);
    const w = canvas.width = canvas.offsetWidth * 2;
    const h = canvas.height = 300;
    ctx.scale(1, 1);

    const padding = { top: 20, right: 15, bottom: 30, left: 45 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    const weights = entries.map(e => e.weight);
    const minW = Math.min(...weights) - 1;
    const maxW = Math.max(...weights) + 1;
    const range = maxW - minW || 1;

    // Background
    ctx.fillStyle = '#1e1e2a';
    ctx.fillRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = '#2a2a3a';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();
      ctx.fillStyle = '#8888a0';
      ctx.font = '20px system-ui';
      ctx.textAlign = 'right';
      ctx.fillText((maxW - (range / 4) * i).toFixed(1), padding.left - 8, y + 6);
    }

    // Weight line
    ctx.strokeStyle = '#40c4ff';
    ctx.lineWidth = 3;
    ctx.beginPath();
    entries.forEach((e, i) => {
      const x = padding.left + (chartW / Math.max(1, entries.length - 1)) * i;
      const y = padding.top + chartH - ((e.weight - minW) / range) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Dots
    entries.forEach((e, i) => {
      const x = padding.left + (chartW / Math.max(1, entries.length - 1)) * i;
      const y = padding.top + chartH - ((e.weight - minW) / range) * chartH;
      ctx.fillStyle = '#40c4ff';
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
    });

    // Body fat line if available
    const fatEntries = entries.filter(e => e.bodyFat);
    if (fatEntries.length > 1) {
      const fats = fatEntries.map(e => e.bodyFat);
      const minF = Math.min(...fats) - 1;
      const maxF = Math.max(...fats) + 1;
      const fRange = maxF - minF || 1;

      ctx.strokeStyle = '#ff80ab';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      fatEntries.forEach((e, i) => {
        const idx = entries.indexOf(e);
        const x = padding.left + (chartW / Math.max(1, entries.length - 1)) * idx;
        const y = padding.top + chartH - ((e.bodyFat - minF) / fRange) * chartH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Date labels
    ctx.fillStyle = '#8888a0';
    ctx.font = '18px system-ui';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(entries.length / 5));
    entries.forEach((e, i) => {
      if (i % step === 0 || i === entries.length - 1) {
        const x = padding.left + (chartW / Math.max(1, entries.length - 1)) * i;
        const label = e.date.slice(5);
        ctx.fillText(label, x, h - 6);
      }
    });
  }
};
