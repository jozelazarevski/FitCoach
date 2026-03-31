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


@coach_bp.route('/streaks', methods=['POST'])
def streaks():
    """Compute streak and badge data from user's log history.

    Accepts: logged_days (sorted desc date strings), daily_totals (list of
    {date, calories, protein, ...}), targets, water_today_ml.
    """
    data = request.get_json() or {}

    logged_days = data.get('logged_days', [])
    daily_totals = data.get('daily_totals', [])
    targets = data.get('targets', {})
    water_ml = data.get('water_today_ml', 0)
    water_target = data.get('water_target_ml', 2300)
    unique_foods = data.get('unique_food_count', 0)

    # Logging streak
    streak = _compute_logging_streak(logged_days)

    # Weekly badges
    badges = []
    recent_7 = daily_totals[:7] if daily_totals else []
    protein_hits = sum(
        1 for d in recent_7
        if d.get('calories', 0) > 0
        and targets.get('protein')
        and d.get('protein', 0) >= targets['protein'] * 0.9
    )
    calorie_hits = sum(
        1 for d in recent_7
        if d.get('calories', 0) > 0
        and targets.get('calories')
        and 0.9 <= d['calories'] / targets['calories'] <= 1.1
    )
    logged_count = sum(1 for d in recent_7 if d.get('calories', 0) > 0)

    if protein_hits >= 5:
        badges.append({'icon': 'muscle', 'name': 'Protein Pro', 'desc': f'Hit protein target {protein_hits}/7 days'})
    elif protein_hits >= 3:
        badges.append({'icon': 'trophy', 'name': 'Protein Rising', 'desc': f'Hit protein target {protein_hits}/7 days'})

    if calorie_hits >= 5:
        badges.append({'icon': 'target', 'name': 'Calorie Sniper', 'desc': f'On calorie target {calorie_hits}/7 days'})

    if logged_count >= 7:
        badges.append({'icon': 'notebook', 'name': 'Full Week Logger', 'desc': 'Logged every day this week'})

    if water_target > 0 and water_ml >= water_target:
        badges.append({'icon': 'water', 'name': 'Hydrated', 'desc': 'Hit water target today'})

    # Milestones
    milestones = []
    total = len(logged_days)
    streak_levels = [(100, '100-Day Streak'), (30, '30-Day Streak'), (14, '2-Week Streak'), (7, '7-Day Streak'), (3, '3-Day Streak')]
    for days, name in streak_levels:
        if streak >= days:
            milestones.append({'name': name, 'type': 'streak'})
            break

    total_levels = [(365, '1 Year of Tracking'), (100, '100 Days Tracked'), (30, '30 Days Tracked'), (7, 'First Week')]
    for days, name in total_levels:
        if total >= days:
            milestones.append({'name': name, 'type': 'total'})
            break

    if unique_foods >= 100:
        milestones.append({'name': '100 Different Foods', 'type': 'variety'})
    elif unique_foods >= 50:
        milestones.append({'name': '50 Different Foods', 'type': 'variety'})

    return jsonify({
        'streak': streak,
        'total_days': total,
        'water': {'current': water_ml, 'target': water_target, 'percent': min(round(water_ml / water_target * 100), 100) if water_target else 0},
        'badges': badges,
        'milestones': milestones,
    })


def _compute_logging_streak(logged_days):
    """Count consecutive days with logs ending today or yesterday."""
    if not logged_days:
        return 0

    day_set = set(logged_days)
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    start = today if today in day_set else (yesterday if yesterday in day_set else None)
    if not start:
        return 0

    streak = 0
    d = datetime.strptime(start, '%Y-%m-%d')
    while d.strftime('%Y-%m-%d') in day_set:
        streak += 1
        d -= timedelta(days=1)

    return streak
