"""Plant library browse, search, clone, and patch tests."""
import pytest

from apps.backend.app.db.models import PlantLibrary


@pytest.fixture
def entries(db):
    rows = [
        PlantLibrary(name='Tomato', type='vegetable', spacing_in=24),
        PlantLibrary(name='Cherry Tomato', type='vegetable', spacing_in=18),
        PlantLibrary(name='Basil', type='herb', spacing_in=10),
        PlantLibrary(name='Marigold', type='flower', spacing_in=8),
    ]
    db.add_all(rows)
    db.flush()
    return rows


def test_browse_pagination(client, entries):
    r = client.get('/api/library?per_page=2&page=1')
    data = r.json()
    assert data['total'] == 4
    assert data['pages'] == 2
    assert len(data['entries']) == 2

    page2 = client.get('/api/library?per_page=2&page=2').json()
    assert len(page2['entries']) == 2
    assert {e['id'] for e in data['entries']} != {e['id'] for e in page2['entries']}


def test_search_case_insensitive(client, entries):
    data = client.get('/api/library?q=tomato').json()
    assert data['total'] == 2
    names = {e['name'] for e in data['entries']}
    assert names == {'Tomato', 'Cherry Tomato'}


def test_filter_by_type(client, entries):
    data = client.get('/api/library?type=herb').json()
    assert data['total'] == 1
    assert data['entries'][0]['name'] == 'Basil'


def test_detail_404(client):
    assert client.get('/api/library/99999').status_code == 404


def test_clone_marks_custom(client, db, library_plant):
    r = client.post(f'/api/library/{library_plant.id}/clone', json={'name': 'My Tomato'})
    assert r.status_code == 200
    clone_id = r.json()['id']
    clone = db.get(PlantLibrary, clone_id)
    assert clone.name == 'My Tomato'
    assert clone.is_custom is True
    assert clone.cloned_from_id == library_plant.id
    assert clone.spacing_in == library_plant.spacing_in


def test_clone_requires_name(client, library_plant):
    r = client.post(f'/api/library/{library_plant.id}/clone', json={})
    assert r.status_code == 400


def test_quick_edit(client, db, library_plant):
    r = client.post(f'/api/library/{library_plant.id}/quick-edit', json={
        'sunlight': 'Partial shade', 'spacing_in': 30,
    })
    assert r.json()['ok'] is True
    db.expire_all()
    assert library_plant.sunlight == 'Partial shade'
    assert library_plant.spacing_in == 30


def test_patch_rejects_unknown_fields(client, library_plant):
    r = client.post(f'/api/library/{library_plant.id}/patch', json={'hacker_field': 1})
    assert r.status_code == 400


def test_patch_serializes_json_fields(client, db, library_plant):
    r = client.post(f'/api/library/{library_plant.id}/patch', json={
        'good_neighbors': ['Basil', 'Chives'],
        'difficulty': 'easy',
    })
    assert r.json()['ok'] is True
    db.expire_all()
    assert library_plant.difficulty == 'easy'
    import json
    assert json.loads(library_plant.good_neighbors) == ['Basil', 'Chives']
