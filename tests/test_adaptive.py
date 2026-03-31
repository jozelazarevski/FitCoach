"""Tests for adaptive macro targets."""


def test_adaptive_targets_strength_workout(client):
    """Test that strength workouts boost protein and calories."""
    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 2000, 'protein': 150, 'carbs': 200, 'fat': 60},
        'goal': 'maintenance',
        'workouts': [
            {'name': 'Bench Press', 'sets': 4, 'reps': 8, 'weight_used': 80, 'caloriesBurned': 300},
        ],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['adjusted']['calories'] > 2000
    assert data['adjusted']['protein'] > 150
    assert len(data['adjustments']) == 1
    assert data['adjustments'][0]['type'] == 'workout'
    assert 'Strength' in data['adjustments'][0]['reason']


def test_adaptive_targets_cardio_cutting(client):
    """Test that cardio on a cut gives minimal replenishment."""
    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 1800, 'protein': 160, 'carbs': 180, 'fat': 50},
        'goal': 'cutting',
        'workouts': [
            {'name': 'Running', 'duration': 45, 'caloriesBurned': 400},
        ],
    })
    data = resp.get_json()
    adj = data['adjustments'][0]
    # Cutting cardio: 25% replenishment = 100 cal
    assert adj['calories'] == 100
    assert data['adjusted']['calories'] == 1900


def test_adaptive_targets_bulking_strength(client):
    """Test bulking goal gets higher replenishment."""
    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 3000, 'protein': 200, 'carbs': 350, 'fat': 80},
        'goal': 'bulking',
        'workouts': [
            {'name': 'Squat', 'sets': 5, 'reps': 5, 'weight_used': 120, 'caloriesBurned': 400},
        ],
    })
    data = resp.get_json()
    adj = data['adjustments'][0]
    # Bulking strength: 80% replenishment = 320 cal, 20g extra protein
    assert adj['calories'] == 320
    assert adj['protein'] == 20


def test_adaptive_targets_weekly_protein_deficit(client):
    """Test weekly protein deficit triggers correction."""
    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 2000, 'protein': 150, 'carbs': 200, 'fat': 60},
        'goal': 'maintenance',
        'daily_logs': [
            {'calories': 1900, 'protein': 100, 'carbs': 190, 'fat': 55},
            {'calories': 1950, 'protein': 110, 'carbs': 195, 'fat': 58},
            {'calories': 1850, 'protein': 105, 'carbs': 185, 'fat': 52},
            {'calories': 1900, 'protein': 95, 'carbs': 190, 'fat': 55},
        ],
    })
    data = resp.get_json()
    # Avg protein ~102.5, target 150, ratio ~68% < 85%
    assert any(a['type'] == 'weekly_trend' for a in data['adjustments'])
    assert data['adjusted']['protein'] > 150


def test_adaptive_targets_no_workouts(client):
    """Test no adjustments when no workouts or data."""
    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 2000, 'protein': 150, 'carbs': 200, 'fat': 60},
        'goal': 'maintenance',
    })
    data = resp.get_json()
    assert data['adjusted']['calories'] == 2000
    assert data['adjusted']['protein'] == 150
    assert len(data['adjustments']) == 0


def test_adaptive_targets_missing_base(client):
    """Test error when no base targets."""
    resp = client.post('/api/coach/adaptive-targets', json={})
    assert resp.status_code == 400


def test_adaptive_targets_weight_plateau(client):
    """Test weight plateau detection on cutting."""
    from datetime import datetime, timedelta
    entries = []
    for i in range(10):
        d = (datetime.now() - timedelta(days=10 - i)).strftime('%Y-%m-%d')
        entries.append({'date': d, 'weight': 80.0 + (i % 2) * 0.1})

    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 1800, 'protein': 160, 'carbs': 180, 'fat': 50},
        'goal': 'cutting',
        'weight_entries': entries,
    })
    data = resp.get_json()
    assert data['weight_insight'] is not None
    assert 'plateau' in data['weight_insight'].lower() or 'cal' in data['weight_insight'].lower()


def test_adaptive_targets_clamps_minimums(client):
    """Test that adjusted values never go below safe minimums."""
    resp = client.post('/api/coach/adaptive-targets', json={
        'base_targets': {'calories': 1200, 'protein': 50, 'carbs': 50, 'fat': 25},
        'goal': 'cutting',
        'daily_logs': [
            {'calories': 1800, 'protein': 60, 'carbs': 60, 'fat': 30},
            {'calories': 1900, 'protein': 55, 'carbs': 65, 'fat': 35},
            {'calories': 1700, 'protein': 58, 'carbs': 55, 'fat': 28},
        ],
    })
    data = resp.get_json()
    assert data['adjusted']['calories'] >= 1200
    assert data['adjusted']['protein'] >= 50
    assert data['adjusted']['carbs'] >= 50
    assert data['adjusted']['fat'] >= 25
