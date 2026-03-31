"""Tests for restaurant mode endpoints."""


def test_quick_estimate_basic(client):
    """Test quick estimate returns results for known dishes."""
    resp = client.post('/api/tracker/restaurant-quick', json={
        'items': ['chicken caesar salad', 'grilled salmon'],
        'remaining_macros': {'calories': 800, 'protein': 50, 'carbs': 80, 'fat': 30},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['estimates']) == 2
    assert data['estimates'][0]['calories'] > 0
    assert data['estimates'][0]['protein'] > 0
    assert data['best_pick'] is not None


def test_quick_estimate_fuzzy_match(client):
    """Test fuzzy matching for similar dish names."""
    resp = client.post('/api/tracker/restaurant-quick', json={
        'items': ['chicken breast grilled', 'salmon fillet'],
    })
    data = resp.get_json()
    assert len(data['estimates']) == 2
    # Should match via keyword overlap
    assert all(e['calories'] > 0 for e in data['estimates'])


def test_quick_estimate_unknown_dish(client):
    """Test fallback estimate for unknown dishes."""
    resp = client.post('/api/tracker/restaurant-quick', json={
        'items': ['xyzzy mystery dish'],
    })
    data = resp.get_json()
    assert len(data['estimates']) == 1
    assert data['estimates'][0]['source'] == 'fallback'
    assert data['estimates'][0]['calories'] > 0


def test_quick_estimate_no_items(client):
    """Test error when no items provided."""
    resp = client.post('/api/tracker/restaurant-quick', json={})
    assert resp.status_code == 400


def test_quick_estimate_keyword_categories(client):
    """Test category-based estimates for keyword matches."""
    resp = client.post('/api/tracker/restaurant-quick', json={
        'items': ['garden salad', 'double cheeseburger', 'grilled chicken wrap', 'tuna poke'],
    })
    data = resp.get_json()
    estimates = {e['name']: e for e in data['estimates']}

    # Salad should be lower cal than burger
    assert estimates['garden salad']['calories'] < estimates['double cheeseburger']['calories']
    # Fish should have decent protein
    assert estimates['tuna poke']['protein'] >= 20


def test_quick_estimate_macro_fit_score(client):
    """Test that macro fit score varies by remaining macros."""
    resp = client.post('/api/tracker/restaurant-quick', json={
        'items': ['grilled chicken breast', 'burger and fries'],
        'remaining_macros': {'calories': 400, 'protein': 40, 'carbs': 30, 'fat': 15},
    })
    data = resp.get_json()
    estimates = {e['name']: e for e in data['estimates']}

    # Chicken should score higher when remaining budget is low
    assert estimates['grilled chicken breast']['macro_fit_score'] > estimates['burger and fries']['macro_fit_score']


def test_restaurant_llm_no_data(client):
    """Test LLM endpoint rejects empty requests."""
    resp = client.post('/api/tracker/restaurant', json={})
    assert resp.status_code == 400
