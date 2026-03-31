"""Tests for streak and habit tracking."""

from datetime import datetime, timedelta


def _make_days(n, start_offset=0):
    """Generate n consecutive date strings ending at today - start_offset."""
    today = datetime.now()
    return [(today - timedelta(days=i + start_offset)).strftime('%Y-%m-%d') for i in range(n)]


def test_streak_basic(client):
    """Test basic streak counting."""
    days = _make_days(5)
    resp = client.post('/api/coach/streaks', json={
        'logged_days': days,
        'targets': {'calories': 2000, 'protein': 150},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['streak'] == 5
    assert data['total_days'] == 5


def test_streak_broken(client):
    """Test streak resets when there's a gap."""
    today = datetime.now()
    days = [
        (today - timedelta(days=0)).strftime('%Y-%m-%d'),
        (today - timedelta(days=1)).strftime('%Y-%m-%d'),
        # gap at day 2
        (today - timedelta(days=3)).strftime('%Y-%m-%d'),
        (today - timedelta(days=4)).strftime('%Y-%m-%d'),
    ]
    resp = client.post('/api/coach/streaks', json={'logged_days': days, 'targets': {}})
    data = resp.get_json()
    assert data['streak'] == 2  # Only today + yesterday


def test_streak_from_yesterday(client):
    """Test streak still counts if today not logged yet."""
    days = _make_days(3, start_offset=1)
    resp = client.post('/api/coach/streaks', json={'logged_days': days, 'targets': {}})
    data = resp.get_json()
    assert data['streak'] == 3


def test_streak_no_days(client):
    """Test zero streak with no data."""
    resp = client.post('/api/coach/streaks', json={'logged_days': [], 'targets': {}})
    data = resp.get_json()
    assert data['streak'] == 0


def test_badges_protein_pro(client):
    """Test protein pro badge at 5/7 days."""
    days = _make_days(7)
    totals = [
        {'date': d, 'calories': 2000, 'protein': 145}
        for d in days[:5]
    ] + [
        {'date': d, 'calories': 2000, 'protein': 80}
        for d in days[5:]
    ]
    resp = client.post('/api/coach/streaks', json={
        'logged_days': days,
        'daily_totals': totals,
        'targets': {'calories': 2000, 'protein': 150},
    })
    data = resp.get_json()
    badge_names = [b['name'] for b in data['badges']]
    assert 'Protein Pro' in badge_names


def test_badges_hydrated(client):
    """Test water badge."""
    resp = client.post('/api/coach/streaks', json={
        'logged_days': _make_days(1),
        'targets': {},
        'water_today_ml': 2500,
        'water_target_ml': 2300,
    })
    data = resp.get_json()
    assert data['water']['percent'] == 100
    badge_names = [b['name'] for b in data['badges']]
    assert 'Hydrated' in badge_names


def test_milestones(client):
    """Test milestone detection."""
    days = _make_days(35)
    resp = client.post('/api/coach/streaks', json={
        'logged_days': days,
        'targets': {},
    })
    data = resp.get_json()
    milestone_names = [m['name'] for m in data['milestones']]
    assert '30-Day Streak' in milestone_names
    assert '30 Days Tracked' in milestone_names


def test_variety_milestone(client):
    """Test unique foods milestone."""
    resp = client.post('/api/coach/streaks', json={
        'logged_days': _make_days(1),
        'targets': {},
        'unique_food_count': 55,
    })
    data = resp.get_json()
    milestone_names = [m['name'] for m in data['milestones']]
    assert '50 Different Foods' in milestone_names
