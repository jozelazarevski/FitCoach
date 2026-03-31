/**
 * Progress Insights Dashboard
 *
 * Lightweight canvas-based analytics:
 * 1. Macro adherence chart (% of target per day, 7/30 day)
 * 2. Weight trend line with moving average
 * 3. Top 10 most-eaten foods
 * 4. Protein source distribution
 * 5. Calorie consistency heatmap
 */
const Insights = {
  period: 7,

  render() {
    const profile = Store.getProfile();
    const targets = profile.macros;

    return `
      <div class="card insights-card">
        <div class="card-title">
          Progress Insights
          <div class="insights-period-toggle">
            <button class="insights-period-btn ${this.period === 7 ? 'active' : ''}" data-period="7">7d</button>
            <button class="insights-period-btn ${this.period === 30 ? 'active' : ''}" data-period="30">30d</button>
          </div>
        </div>

        <div class="insights-section">
          <div class="insights-subtitle">Macro Adherence</div>
          <canvas id="chart-adherence" height="140"></canvas>
        </div>

        <div class="insights-section">
          <div class="insights-subtitle">Calorie Trend</div>
          <canvas id="chart-calories" height="120"></canvas>
        </div>

        ${Store.getBodyLog().length >= 2 ? `
          <div class="insights-section">
            <div class="insights-subtitle">Weight Trend</div>
            <canvas id="chart-weight" height="120"></canvas>
          </div>
        ` : ''}

        <div class="insights-row">
          <div class="insights-half">
            <div class="insights-subtitle">Top Foods</div>
            <div id="insights-top-foods"></div>
          </div>
          <div class="insights-half">
            <div class="insights-subtitle">Stats</div>
            <div id="insights-stats"></div>
          </div>
        </div>
      </div>
    `;
  },

  bind() {
    document.querySelectorAll('.insights-period-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.period = parseInt(btn.dataset.period);
        document.querySelectorAll('.insights-period-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this._drawAll();
      });
    });
    this._drawAll();
  },

  _drawAll() {
    const days = this._getDayData(this.period);
    this._drawAdherenceChart(days);
    this._drawCalorieChart(days);
    this._drawWeightChart();
    this._renderTopFoods(days);
    this._renderStats(days);
  },

  _getDayData(numDays) {
    const profile = Store.getProfile();
    const targets = profile.macros;
    const days = [];
    const today = new Date();

    for (let i = numDays - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().split('T')[0];
      const totals = Store.getDayTotals(key);
      const meals = Store.getDayMeals(key);
      days.push({
        date: key,
        label: d.toLocaleDateString('en', { month: 'short', day: 'numeric' }),
        totals,
        meals,
        targets,
        adherence: {
          calories: targets.calories ? Math.min(totals.calories / targets.calories, 1.5) : 0,
          protein: targets.protein ? Math.min(totals.protein / targets.protein, 1.5) : 0,
          carbs: targets.carbs ? Math.min(totals.carbs / targets.carbs, 1.5) : 0,
          fat: targets.fat ? Math.min(totals.fat / targets.fat, 1.5) : 0,
        },
      });
    }
    return days;
  },

  _drawAdherenceChart(days) {
    const canvas = document.getElementById('chart-adherence');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.offsetWidth;
    const h = 140;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const padding = { top: 10, bottom: 25, left: 5, right: 5 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;
    const barGroupW = chartW / days.length;

    // 100% line
    const y100 = padding.top + chartH * (1 - 1 / 1.5);
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(padding.left, y100);
    ctx.lineTo(w - padding.right, y100);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.font = '9px system-ui';
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.textAlign = 'right';
    ctx.fillText('100%', w - padding.right, y100 - 3);

    const colors = {
      protein: '#a78bfa',
      carbs: '#60a5fa',
      fat: '#fbbf24',
    };

    days.forEach((day, i) => {
      const x = padding.left + i * barGroupW;
      const bw = Math.max(barGroupW * 0.2, 3);
      const gap = (barGroupW - bw * 3) / 4;

      ['protein', 'carbs', 'fat'].forEach((macro, mi) => {
        const val = day.adherence[macro];
        const barH = (val / 1.5) * chartH;
        const bx = x + gap * (mi + 1) + bw * mi;
        const by = padding.top + chartH - barH;

        ctx.fillStyle = colors[macro];
        ctx.globalAlpha = val > 0 ? 0.8 : 0.1;
        ctx.beginPath();
        ctx.roundRect(bx, by, bw, barH, 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // Date label (every nth day)
      if (days.length <= 10 || i % Math.ceil(days.length / 10) === 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.textAlign = 'center';
        ctx.font = '9px system-ui';
        ctx.fillText(day.label, x + barGroupW / 2, h - 5);
      }
    });

    // Legend
    ctx.font = '10px system-ui';
    const legendY = h - 5;
    let lx = w - 10;
    ctx.textAlign = 'right';
    [['Fat', '#fbbf24'], ['Carbs', '#60a5fa'], ['Protein', '#a78bfa']].forEach(([label, color]) => {
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.fillText(label, lx, legendY);
      lx -= tw + 4;
      ctx.fillStyle = color;
      ctx.fillRect(lx - 6, legendY - 7, 6, 6);
      lx -= 14;
    });
  },

  _drawCalorieChart(days) {
    const canvas = document.getElementById('chart-calories');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.offsetWidth;
    const h = 120;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const padding = { top: 10, bottom: 25, left: 5, right: 5 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    const maxCal = Math.max(...days.map(d => d.totals.calories), days[0]?.targets.calories || 2000) * 1.1;
    const target = days[0]?.targets.calories || 2000;

    // Target line
    const targetY = padding.top + chartH * (1 - target / maxCal);
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(padding.left, targetY);
    ctx.lineTo(w - padding.right, targetY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = '9px system-ui';
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.textAlign = 'right';
    ctx.fillText(`${target} cal`, w - padding.right, targetY - 3);

    // Line chart
    const points = days.map((d, i) => ({
      x: padding.left + (i / (days.length - 1 || 1)) * chartW,
      y: padding.top + chartH * (1 - d.totals.calories / maxCal),
      cal: d.totals.calories,
    }));

    // Fill area
    ctx.beginPath();
    ctx.moveTo(points[0].x, padding.top + chartH);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, padding.top + chartH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
    grad.addColorStop(0, 'rgba(245,158,11,0.25)');
    grad.addColorStop(1, 'rgba(245,158,11,0.02)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    points.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Dots
    points.forEach(p => {
      if (p.cal > 0) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#f59e0b';
        ctx.fill();
      }
    });

    // Labels
    days.forEach((day, i) => {
      if (days.length <= 10 || i % Math.ceil(days.length / 10) === 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.textAlign = 'center';
        ctx.font = '9px system-ui';
        ctx.fillText(day.label, points[i].x, h - 5);
      }
    });
  },

  _drawWeightChart() {
    const canvas = document.getElementById('chart-weight');
    if (!canvas) return;
    const bodyLog = Store.getBodyLog();
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - this.period);
    const entries = bodyLog.filter(e => e.weight && new Date(e.date) >= cutoff);
    if (entries.length < 2) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.offsetWidth;
    const h = 120;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const padding = { top: 10, bottom: 25, left: 5, right: 5 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    const weights = entries.map(e => e.weight);
    const minW = Math.min(...weights) - 0.5;
    const maxW = Math.max(...weights) + 0.5;
    const range = maxW - minW || 1;

    const points = entries.map((e, i) => ({
      x: padding.left + (i / (entries.length - 1 || 1)) * chartW,
      y: padding.top + chartH * (1 - (e.weight - minW) / range),
      weight: e.weight,
      date: e.date,
    }));

    // Line
    ctx.beginPath();
    points.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
    ctx.strokeStyle = '#34d399';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Moving average (3-point)
    if (points.length >= 3) {
      ctx.beginPath();
      for (let i = 1; i < points.length - 1; i++) {
        const avg = (weights[i - 1] + weights[i] + weights[i + 1]) / 3;
        const y = padding.top + chartH * (1 - (avg - minW) / range);
        i === 1 ? ctx.moveTo(points[i].x, y) : ctx.lineTo(points[i].x, y);
      }
      ctx.strokeStyle = 'rgba(52,211,153,0.4)';
      ctx.lineWidth = 3;
      ctx.stroke();
    }

    // Dots + labels
    points.forEach((p, i) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#34d399';
      ctx.fill();

      if (entries.length <= 10 || i % Math.ceil(entries.length / 7) === 0 || i === entries.length - 1) {
        ctx.font = '9px system-ui';
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.textAlign = 'center';
        ctx.fillText(`${p.weight}`, p.x, p.y - 8);
      }
    });

    // Min/Max labels
    ctx.font = '9px system-ui';
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.textAlign = 'left';
    ctx.fillText(`${minW.toFixed(1)}`, padding.left, padding.top + chartH + 12);
    ctx.textAlign = 'right';
    ctx.fillText(`${maxW.toFixed(1)}`, w - padding.right, padding.top + chartH + 12);
  },

  _renderTopFoods(days) {
    const el = document.getElementById('insights-top-foods');
    if (!el) return;

    const foodCounts = {};
    days.forEach(d => {
      (d.meals || []).forEach(meal => {
        (meal.items || []).forEach(item => {
          const name = (item.name || '').toLowerCase().trim();
          if (name) foodCounts[name] = (foodCounts[name] || 0) + 1;
        });
      });
    });

    const sorted = Object.entries(foodCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);

    if (sorted.length === 0) {
      el.innerHTML = '<div class="insights-empty">No meals logged yet</div>';
      return;
    }

    const maxCount = sorted[0][1];
    el.innerHTML = sorted.map(([name, count]) => `
      <div class="insights-food-row">
        <span class="insights-food-name">${name}</span>
        <div class="insights-food-bar-wrap">
          <div class="insights-food-bar" style="width:${(count / maxCount) * 100}%"></div>
        </div>
        <span class="insights-food-count">${count}x</span>
      </div>
    `).join('');
  },

  _renderStats(days) {
    const el = document.getElementById('insights-stats');
    if (!el) return;

    const profile = Store.getProfile();
    const targets = profile.macros;
    const daysWithLogs = days.filter(d => d.totals.calories > 0).length;

    // Adherence score (how many days within 10% of target)
    const onTarget = days.filter(d => {
      if (d.totals.calories === 0) return false;
      const ratio = d.totals.calories / (targets.calories || 2000);
      return ratio >= 0.9 && ratio <= 1.1;
    }).length;

    // Avg protein
    const avgProtein = daysWithLogs > 0
      ? Math.round(days.reduce((s, d) => s + d.totals.protein, 0) / daysWithLogs)
      : 0;

    // Protein hit rate
    const proteinHitDays = days.filter(d =>
      d.totals.protein > 0 && d.totals.protein >= (targets.protein || 150) * 0.9
    ).length;

    el.innerHTML = `
      <div class="insights-stat">
        <span class="insights-stat-val">${daysWithLogs}/${days.length}</span>
        <span class="insights-stat-label">Days logged</span>
      </div>
      <div class="insights-stat">
        <span class="insights-stat-val">${onTarget}/${daysWithLogs || 1}</span>
        <span class="insights-stat-label">On calorie target</span>
      </div>
      <div class="insights-stat">
        <span class="insights-stat-val">${avgProtein}g</span>
        <span class="insights-stat-label">Avg daily protein</span>
      </div>
      <div class="insights-stat">
        <span class="insights-stat-val">${proteinHitDays}/${daysWithLogs || 1}</span>
        <span class="insights-stat-label">Hit protein goal</span>
      </div>
    `;
  },
};
