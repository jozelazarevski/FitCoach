"""Coach API endpoints — adaptive macro targets and insights."""

import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

coach_bp = Blueprint('coach', __name__)
logger = logging.getLogger(__name__)


def _compute_workout_adjustment(workouts, goal):
    """Compute macro adjustments based on today's workouts."""
    if not workouts:
        return None

    total_cals_burned = sum(w.get('caloriesBurned', 0) for w in workouts)
    has_strength = any(
        (w.get('sets') and w['sets'] > 0)
        or (w.get('weight_used') and w['weight_used'] > 0)
        or (w.get('name', '') and any(
            k in w['name'].lower()
            for k in ('strength', 'lift', 'squat', 'deadlift', 'bench', 'press', 'curl', 'row')
        ))
        for w in workouts
    )
    has_cardio = any(
        (w.get('duration', 0) >= 20 and not has_strength)
        or (w.get('name', '') and any(
            k in w['name'].lower()
            for k in ('run', 'jog', 'cycle', 'swim', 'hiit', 'cardio', 'walk')
        ))
        for w in workouts
    )

    if total_cals_burned < 50 and not has_strength and not has_cardio:
        return None

    cal_adj = prot_adj = carb_adj = fat_adj = 0
    reason = ''

    if has_strength:
        replenish = 0.8 if goal in ('bulking', 'muscle_building') else 0.6
        cal_adj = round(total_cals_burned * replenish)
        prot_adj = 20 if goal in ('bulking', 'muscle_building') else 15
        carb_adj = round(cal_adj * 0.5 / 4)
        fat_adj = round(cal_adj * 0.1 / 9)
        reason = f'Strength training ({total_cals_burned} cal burned)'
    elif has_cardio:
        replenish = 0.25 if goal in ('fat_loss', 'cutting') else 0.4
        cal_adj = round(total_cals_burned * replenish)
        prot_adj = 5
        carb_adj = round(cal_adj * 0.6 / 4)
        fat_adj = 0
        reason = f'Cardio session ({total_cals_burned} cal burned)'
    else:
        cal_adj = round(total_cals_burned * 0.3)
        carb_adj = round(cal_adj * 0.5 / 4)
        reason = f'Activity logged ({total_cals_burned} cal burned)'

    if cal_adj == 0 and prot_adj == 0:
        return None

    return {
        'calories': cal_adj, 'protein': prot_adj,
        'carbs': carb_adj, 'fat': fat_adj,
        'reason': reason, 'type': 'workout',
    }


def _compute_weekly_trend(daily_logs, base_targets):
    """Compute adjustments based on weekly macro averages."""
    if not daily_logs or len(daily_logs) < 3:
        return None

    avg_protein = sum(d.get('protein', 0) for d in daily_logs) / len(daily_logs)
    avg_carbs = sum(d.get('carbs', 0) for d in daily_logs) / len(daily_logs)
    avg_calories = sum(d.get('calories', 0) for d in daily_logs) / len(daily_logs)

    prot_target = base_targets.get('protein', 150)
    carb_target = base_targets.get('carbs', 200)
    cal_target = base_targets.get('calories', 2000)

    prot_adj = carb_adj = cal_adj = fat_adj = 0
    reasons = []

    if prot_target > 0 and avg_protein / prot_target < 0.85:
        deficit = prot_target - avg_protein
        prot_adj = round(min(deficit * 0.3, 25))
        cal_adj += prot_adj * 4
        reasons.append(f'Weekly protein avg {round(avg_protein / prot_target * 100)}% of target')

    if carb_target > 80 and avg_carbs / carb_target < 0.80:
        deficit = carb_target - avg_carbs
        carb_adj = round(min(deficit * 0.25, 30))
        cal_adj += carb_adj * 4
        reasons.append(f'Weekly carbs avg {round(avg_carbs / carb_target * 100)}% of target')

    if cal_target > 0 and avg_calories / cal_target > 1.15:
        excess = round((avg_calories / cal_target - 1) * cal_target)
        cal_adj = -round(min(excess * 0.15, 150))
        reasons.append(f'Weekly avg {round(avg_calories / cal_target * 100)}% of calorie target')

    if not reasons:
        return None

    return {
        'calories': cal_adj, 'protein': prot_adj,
        'carbs': carb_adj, 'fat': fat_adj,
        'reason': '; '.join(reasons), 'type': 'weekly_trend',
    }


def _compute_weight_insight(weight_entries, goal):
    """Analyze weight trajectory and return insight string."""
    if not weight_entries or len(weight_entries) < 3:
        return None

    cutoff = (datetime.now() - timedelta(days=14)).isoformat()[:10]
    recent = [e for e in weight_entries if e.get('date', '') >= cutoff and e.get('weight')]

    if len(recent) < 3:
        return None

    mid = len(recent) // 2
    avg_first = sum(e['weight'] for e in recent[:mid]) / mid
    avg_second = sum(e['weight'] for e in recent[mid:]) / (len(recent) - mid)
    change_rate = (avg_second - avg_first) / (len(recent) / 7)

    if goal in ('fat_loss', 'cutting'):
        if abs(change_rate) < 0.1:
            return 'Weight plateaued. Consider -100 to -150 cal/day or adding cardio.'
        if change_rate > 0.3:
            return f'Weight trending up (+{change_rate:.1f} kg/wk). Review intake or increase activity.'
        if change_rate < -1.0:
            return f'Losing fast ({change_rate:.1f} kg/wk). Add 100-200 cal to preserve muscle.'
        if change_rate < -0.2:
            return f'On track: losing {abs(change_rate):.1f} kg/wk.'
    elif goal in ('bulking', 'muscle_building'):
        if abs(change_rate) < 0.05:
            return 'Weight stalled. Increase calories by 150-200.'
        if change_rate > 0.5:
            return f'Gaining {change_rate:.1f} kg/wk — might be too fast. Pull back 100-150 cal.'
        if change_rate > 0.1:
            return f'Good lean bulk: +{change_rate:.1f} kg/wk.'
        if change_rate < -0.2:
            return 'Losing weight while bulking. Increase calories by 200-300.'
    else:
        if abs(change_rate) > 0.3:
            direction = 'gaining' if change_rate > 0 else 'losing'
            return f'Weight {direction} at {abs(change_rate):.1f} kg/wk. Adjust if unintentional.'

    return None


@coach_bp.route('/adaptive-targets', methods=['POST'])
def adaptive_targets():
    """Compute adaptive macro targets.

    Accepts user context (workouts, daily logs, weight, base targets, goal)
    and returns adjusted macros with explanations.
    """
    data = request.get_json() or {}

    base_targets = data.get('base_targets', {})
    if not base_targets.get('calories'):
        return jsonify({'error': 'base_targets with calories required'}), 400

    goal = data.get('goal', 'maintenance')
    workouts = data.get('workouts', [])
    daily_logs = data.get('daily_logs', [])
    weight_entries = data.get('weight_entries', [])

    adjustments = []
    adjusted = {
        'calories': base_targets.get('calories', 2000),
        'protein': base_targets.get('protein', 150),
        'carbs': base_targets.get('carbs', 200),
        'fat': base_targets.get('fat', 60),
    }

    # 1. Workout adjustment
    workout_adj = _compute_workout_adjustment(workouts, goal)
    if workout_adj:
        for key in ('calories', 'protein', 'carbs', 'fat'):
            adjusted[key] += workout_adj[key]
        adjustments.append(workout_adj)

    # 2. Weekly trend correction
    trend_adj = _compute_weekly_trend(daily_logs, base_targets)
    if trend_adj:
        for key in ('calories', 'protein', 'carbs', 'fat'):
            adjusted[key] += trend_adj[key]
        adjustments.append(trend_adj)

    # 3. Weight insight
    weight_insight = _compute_weight_insight(weight_entries, goal)

    # Clamp minimums
    adjusted['calories'] = max(round(adjusted['calories']), 1200)
    adjusted['protein'] = max(round(adjusted['protein']), 50)
    adjusted['carbs'] = max(round(adjusted['carbs']), 50)
    adjusted['fat'] = max(round(adjusted['fat']), 25)

    return jsonify({
        'adjusted': adjusted,
        'base': base_targets,
        'adjustments': adjustments,
        'weight_insight': weight_insight,
    })
