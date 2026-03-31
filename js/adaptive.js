/**
 * Adaptive Macro Targets
 *
 * Dynamically adjusts daily macro targets based on:
 * 1. Workout intensity — more calories/carbs on training days
 * 2. Weekly trend correction — behind on protein avg → shift today up
 * 3. Weight trajectory — stall detection → suggest deficit adjustment
 */
const Adaptive = {

  /**
   * Compute adjusted macro targets for today.
   * Returns { adjusted: {calories, protein, carbs, fat}, base: {...}, adjustments: [...], weightInsight: string|null }
   */
  getAdaptiveTargets() {
    const profile = Store.getProfile();
    const base = { ...profile.macros };
    if (!base.calories) return null;

    const adjustments = [];
    const adjusted = { calories: base.calories, protein: base.protein, carbs: base.carbs, fat: base.fat };

    // 1. Workout-based adjustment
    const workoutAdj = this._workoutAdjustment(profile.goal);
    if (workoutAdj) {
      adjusted.calories += workoutAdj.calories;
      adjusted.protein += workoutAdj.protein;
      adjusted.carbs += workoutAdj.carbs;
      adjusted.fat += workoutAdj.fat;
      adjustments.push(workoutAdj);
    }

    // 2. Weekly trend correction
    const trendAdj = this._weeklyTrendCorrection(base);
    if (trendAdj) {
      adjusted.calories += trendAdj.calories;
      adjusted.protein += trendAdj.protein;
      adjusted.carbs += trendAdj.carbs;
      adjusted.fat += trendAdj.fat;
      adjustments.push(trendAdj);
    }

    // 3. Weight trajectory insight
    const weightInsight = this._weightTrajectory(profile.goal);

    // Clamp to minimums
    adjusted.calories = Math.max(adjusted.calories, 1200);
    adjusted.protein = Math.max(adjusted.protein, 50);
    adjusted.carbs = Math.max(adjusted.carbs, 50);
    adjusted.fat = Math.max(adjusted.fat, 25);

    // Round
    adjusted.calories = Math.round(adjusted.calories);
    adjusted.protein = Math.round(adjusted.protein);
    adjusted.carbs = Math.round(adjusted.carbs);
    adjusted.fat = Math.round(adjusted.fat);

    return { adjusted, base, adjustments, weightInsight };
  },

  /**
   * Adjust macros based on today's workout activity.
   */
  _workoutAdjustment(goal) {
    const todayWorkouts = Store.getTodayWorkouts();
    if (!todayWorkouts || todayWorkouts.length === 0) return null;

    const totalCalsBurned = todayWorkouts.reduce((s, w) => s + (w.caloriesBurned || 0), 0);
    const hasStrength = todayWorkouts.some(w =>
      (w.sets && w.sets > 0) || (w.weight_used && w.weight_used > 0) ||
      (w.name && /strength|lift|squat|deadlift|bench|press|curl|row/i.test(w.name))
    );
    const hasCardio = todayWorkouts.some(w =>
      (w.duration && w.duration >= 20 && !hasStrength) ||
      (w.name && /run|jog|cycle|swim|hiit|cardio|walk/i.test(w.name))
    );

    if (totalCalsBurned < 50 && !hasStrength && !hasCardio) return null;

    let calAdj = 0, protAdj = 0, carbAdj = 0, fatAdj = 0;
    let reason = '';

    if (hasStrength) {
      // Heavy training: replenish ~60% of burned cals, extra protein + carbs
      calAdj = Math.round(totalCalsBurned * 0.6);
      protAdj = 15;
      carbAdj = Math.round(totalCalsBurned * 0.6 * 0.5 / 4); // 50% of extra cals from carbs
      fatAdj = Math.round(totalCalsBurned * 0.6 * 0.1 / 9);  // 10% from fat
      reason = `Strength training detected (${totalCalsBurned} cal burned)`;

      if (goal === 'bulking' || goal === 'muscle_building') {
        calAdj = Math.round(totalCalsBurned * 0.8);
        protAdj = 20;
        carbAdj = Math.round(totalCalsBurned * 0.8 * 0.5 / 4);
        reason += ' — bulking surplus applied';
      }
    } else if (hasCardio) {
      // Cardio: replenish ~40% of burned cals, modest carb boost
      calAdj = Math.round(totalCalsBurned * 0.4);
      protAdj = 5;
      carbAdj = Math.round(totalCalsBurned * 0.4 * 0.6 / 4);
      fatAdj = 0;
      reason = `Cardio session (${totalCalsBurned} cal burned)`;

      if (goal === 'fat_loss' || goal === 'cutting') {
        calAdj = Math.round(totalCalsBurned * 0.25);
        carbAdj = Math.round(totalCalsBurned * 0.25 * 0.5 / 4);
        reason += ' — cutting: minimal replenishment';
      }
    } else {
      // Generic activity
      calAdj = Math.round(totalCalsBurned * 0.3);
      carbAdj = Math.round(calAdj * 0.5 / 4);
      reason = `Activity logged (${totalCalsBurned} cal burned)`;
    }

    if (calAdj === 0 && protAdj === 0) return null;

    return { calories: calAdj, protein: protAdj, carbs: carbAdj, fat: fatAdj, reason, type: 'workout' };
  },

  /**
   * If the 7-day average is behind target, nudge today's macros up.
   */
  _weeklyTrendCorrection(baseTargets) {
    const weekAvg = Store.getWeekAverage();
    if (!weekAvg || weekAvg.days < 3) return null; // Need at least 3 days of data

    const proteinRatio = weekAvg.protein / baseTargets.protein;
    const carbRatio = weekAvg.carbs / baseTargets.carbs;
    const calRatio = weekAvg.calories / baseTargets.calories;

    let protAdj = 0, carbAdj = 0, calAdj = 0, fatAdj = 0;
    const reasons = [];

    // If weekly protein avg is < 85% of target, boost today
    if (proteinRatio < 0.85 && baseTargets.protein > 0) {
      const deficit = baseTargets.protein - weekAvg.protein;
      protAdj = Math.round(Math.min(deficit * 0.3, 25)); // Up to 25g boost
      calAdj += protAdj * 4;
      reasons.push(`Weekly protein avg ${Math.round(proteinRatio * 100)}% of target`);
    }

    // If weekly carbs avg is < 80% of target on non-keto/low-carb goals
    if (carbRatio < 0.80 && baseTargets.carbs > 80) {
      const deficit = baseTargets.carbs - weekAvg.carbs;
      carbAdj = Math.round(Math.min(deficit * 0.25, 30));
      calAdj += carbAdj * 4;
      reasons.push(`Weekly carbs avg ${Math.round(carbRatio * 100)}% of target`);
    }

    // If consistently overeating, suggest a slight pullback (not punitive)
    if (calRatio > 1.15 && baseTargets.calories > 0) {
      const excess = Math.round((calRatio - 1) * baseTargets.calories);
      calAdj = -Math.round(Math.min(excess * 0.15, 150)); // Gentle pullback, max 150 cal
      reasons.push(`Weekly avg ${Math.round(calRatio * 100)}% of calorie target`);
    }

    if (reasons.length === 0) return null;

    return {
      calories: calAdj, protein: protAdj, carbs: carbAdj, fat: fatAdj,
      reason: reasons.join('; '), type: 'weekly_trend'
    };
  },

  /**
   * Analyze weight trajectory and return an insight string.
   */
  _weightTrajectory(goal) {
    const bodyLog = Store.getBodyLog();
    if (!bodyLog || bodyLog.length < 3) return null;

    // Get last 14 days of weight entries
    const twoWeeksAgo = new Date();
    twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14);
    const recent = bodyLog.filter(e => e.date && new Date(e.date) >= twoWeeksAgo && e.weight);

    if (recent.length < 3) return null;

    // Simple linear trend: compare first half avg to second half avg
    const mid = Math.floor(recent.length / 2);
    const firstHalf = recent.slice(0, mid);
    const secondHalf = recent.slice(mid);

    const avgFirst = firstHalf.reduce((s, e) => s + e.weight, 0) / firstHalf.length;
    const avgSecond = secondHalf.reduce((s, e) => s + e.weight, 0) / secondHalf.length;
    const change = avgSecond - avgFirst;
    const changeRate = change / (recent.length / 7); // per week

    if (goal === 'fat_loss' || goal === 'cutting') {
      if (Math.abs(changeRate) < 0.1) {
        return 'Weight has plateaued over 2 weeks. Consider reducing daily calories by 100-150 or adding a cardio session.';
      }
      if (changeRate > 0.3) {
        return `Weight trending up (+${changeRate.toFixed(1)} kg/wk). Review calorie intake or increase activity.`;
      }
      if (changeRate < -1.0) {
        return `Losing weight fast (${changeRate.toFixed(1)} kg/wk). Slow down to preserve muscle — add 100-200 cal.`;
      }
      if (changeRate < -0.2) {
        return `On track: losing ${Math.abs(changeRate).toFixed(1)} kg/wk. Keep it up!`;
      }
    }

    if (goal === 'bulking' || goal === 'muscle_building') {
      if (Math.abs(changeRate) < 0.05) {
        return 'Weight stalled. Increase daily calories by 150-200 to resume gaining.';
      }
      if (changeRate > 0.5) {
        return `Gaining ${changeRate.toFixed(1)} kg/wk — might be too fast. Pull back 100-150 cal to stay lean.`;
      }
      if (changeRate > 0.1) {
        return `Good lean bulk: +${changeRate.toFixed(1)} kg/wk.`;
      }
      if (changeRate < -0.2) {
        return `Losing weight while bulking. Increase calories by 200-300.`;
      }
    }

    // Maintenance
    if (Math.abs(changeRate) > 0.3) {
      const direction = changeRate > 0 ? 'gaining' : 'losing';
      return `Weight ${direction} at ${Math.abs(changeRate).toFixed(1)} kg/wk. Adjust calories if unintentional.`;
    }

    return null;
  },

  /**
   * Render the adaptive targets card for the dashboard.
   */
  renderCard() {
    const result = this.getAdaptiveTargets();
    if (!result) return '';

    const { adjusted, base, adjustments, weightInsight } = result;
    const hasAdjustments = adjustments.length > 0;
    const hasWeightInsight = !!weightInsight;

    if (!hasAdjustments && !hasWeightInsight) return '';

    const calDiff = adjusted.calories - base.calories;
    const protDiff = adjusted.protein - base.protein;

    return `
      <div class="card adaptive-card">
        <div class="card-title">
          Adjusted Targets Today
          <span class="adaptive-badge">Smart</span>
        </div>
        ${hasAdjustments ? `
          <div class="adaptive-targets">
            <div class="adaptive-target">
              <span class="adaptive-label">Calories</span>
              <span class="adaptive-value" style="color:var(--cal-color)">${adjusted.calories}
                ${calDiff !== 0 ? `<span class="adaptive-diff ${calDiff > 0 ? 'up' : 'down'}">${calDiff > 0 ? '+' : ''}${calDiff}</span>` : ''}
              </span>
            </div>
            <div class="adaptive-target">
              <span class="adaptive-label">Protein</span>
              <span class="adaptive-value" style="color:var(--protein-color)">${adjusted.protein}g
                ${protDiff !== 0 ? `<span class="adaptive-diff ${protDiff > 0 ? 'up' : 'down'}">${protDiff > 0 ? '+' : ''}${protDiff}</span>` : ''}
              </span>
            </div>
            <div class="adaptive-target">
              <span class="adaptive-label">Carbs</span>
              <span class="adaptive-value" style="color:var(--carb-color)">${adjusted.carbs}g</span>
            </div>
            <div class="adaptive-target">
              <span class="adaptive-label">Fat</span>
              <span class="adaptive-value" style="color:var(--fat-color)">${adjusted.fat}g</span>
            </div>
          </div>
          <div class="adaptive-reasons">
            ${adjustments.map(a => `
              <div class="adaptive-reason">
                <span class="adaptive-reason-icon">${a.type === 'workout' ? '&#127947;' : '&#128200;'}</span>
                ${a.reason}
              </div>
            `).join('')}
          </div>
        ` : ''}
        ${hasWeightInsight ? `
          <div class="adaptive-weight-insight">
            <span class="adaptive-reason-icon">&#9878;</span>
            ${weightInsight}
          </div>
        ` : ''}
      </div>
    `;
  }
};
