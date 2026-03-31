"""Tests for grocery list and recipe scaling features."""



def test_grocery_list_from_recipe_ids(client, sample_recipe_data):
    """Test generating a grocery list from recipe IDs."""
    from backend.models import insert_recipe

    recipe_data = dict(sample_recipe_data)
    recipe_data['ingredients'] = [
        {'item': 'chicken breast', 'amount': '200g', 'grams': 200},
        {'item': 'brown rice', 'amount': '100g', 'grams': 100},
        {'item': 'broccoli', 'amount': '150g', 'grams': 150},
    ]
    rid = insert_recipe(recipe_data)

    resp = client.post('/api/recipes/grocery-list', json={'recipe_ids': [rid]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_items'] == 3
    assert data['to_buy'] == 3

    # Check categories
    names = {item['name'] for item in data['items']}
    assert 'chicken breast' in names
    assert 'brown rice' in names
    assert 'broccoli' in names


def test_grocery_list_deduplicates(client, sample_recipe_data):
    """Test that duplicate ingredients across recipes are combined."""
    from backend.models import insert_recipe

    r1 = dict(sample_recipe_data)
    r1['name'] = 'Recipe A'
    r1['ingredients'] = [{'item': 'chicken breast', 'amount': '200g', 'grams': 200}]
    rid1 = insert_recipe(r1)

    r2 = dict(sample_recipe_data)
    r2['name'] = 'Recipe B'
    r2['ingredients'] = [{'item': 'chicken breast', 'amount': '300g', 'grams': 300}]
    rid2 = insert_recipe(r2)

    resp = client.post('/api/recipes/grocery-list', json={'recipe_ids': [rid1, rid2]})
    data = resp.get_json()

    # Should be deduplicated into 1 item
    chicken = [i for i in data['items'] if 'chicken' in i['name'].lower()]
    assert len(chicken) == 1
    assert chicken[0]['amount'] == '500g'
    assert chicken[0]['recipe_count'] == 2


def test_grocery_list_pantry_filter(client, sample_recipe_data):
    """Test pantry items are flagged."""
    from backend.models import insert_recipe

    r = dict(sample_recipe_data)
    r['ingredients'] = [
        {'item': 'chicken breast', 'amount': '200g', 'grams': 200},
        {'item': 'olive oil', 'amount': '1 tbsp', 'grams': 0},
    ]
    rid = insert_recipe(r)

    resp = client.post('/api/recipes/grocery-list', json={
        'recipe_ids': [rid],
        'pantry': ['olive oil'],
    })
    data = resp.get_json()
    assert data['pantry_items'] == 1
    assert data['to_buy'] == 1


def test_grocery_list_no_ids(client):
    """Test error when no recipe IDs provided."""
    resp = client.post('/api/recipes/grocery-list', json={})
    assert resp.status_code == 400


def test_recipe_scaling(client, sample_recipe_data):
    """Test recipe scaling doubles macros and ingredients."""
    from backend.models import insert_recipe

    r = dict(sample_recipe_data)
    r['servings'] = 1
    r['calories'] = 400
    r['protein'] = 30
    r['carbs'] = 40
    r['fat'] = 15
    r['ingredients'] = [
        {'item': 'chicken breast', 'amount': '200g', 'grams': 200},
    ]
    rid = insert_recipe(r)

    resp = client.get(f'/api/recipes/{rid}/scale?servings=2')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['calories'] == 800
    assert data['protein'] == 60
    assert data['carbs'] == 80
    assert data['fat'] == 30
    assert data['ingredients'][0]['grams'] == 400
    assert data['scale_factor'] == 2.0


def test_recipe_scaling_half(client, sample_recipe_data):
    """Test scaling down to half."""
    from backend.models import insert_recipe

    r = dict(sample_recipe_data)
    r['servings'] = 2
    r['calories'] = 500
    r['protein'] = 40
    r['ingredients'] = [
        {'item': 'rice', 'amount': '200g', 'grams': 200},
    ]
    rid = insert_recipe(r)

    resp = client.get(f'/api/recipes/{rid}/scale?servings=1')
    data = resp.get_json()
    assert data['calories'] == 250
    assert data['protein'] == 20
    assert data['ingredients'][0]['grams'] == 100


def test_recipe_scaling_invalid_servings(client, sample_recipe_data):
    """Test error on invalid servings."""
    from backend.models import insert_recipe
    rid = insert_recipe(sample_recipe_data)

    resp = client.get(f'/api/recipes/{rid}/scale?servings=abc')
    assert resp.status_code == 400
