"""Bed grid placement: bounds checking and AABB overlap collision."""


def _place(client, bed_id, library_id, x, y, spacing=None):
    body = {'grid_x': x, 'grid_y': y, 'library_id': library_id}
    if spacing is not None:
        body['spacing_in'] = spacing
    return client.post(f'/api/beds/{bed_id}/grid-plant', json=body)


def test_place_plant_on_grid(client, bed, library_plant):
    # bed is 4x8 ft = 48x96 in; tomato spacing 24 in
    r = _place(client, bed.id, library_plant.id, 0, 0)
    assert r.status_code == 200
    data = r.json()
    assert data['grid_x'] == 0 and data['grid_y'] == 0
    assert data['spacing_in'] == 24


def test_out_of_bounds_rejected(client, bed, library_plant):
    # 40 + 24 > 48 → does not fit in width
    r = _place(client, bed.id, library_plant.id, 40, 0)
    assert r.status_code == 400


def test_overlap_rejected(client, bed, library_plant):
    assert _place(client, bed.id, library_plant.id, 0, 0).status_code == 200
    # Second plant at (12, 12) overlaps the 24-in square at (0, 0)
    r = _place(client, bed.id, library_plant.id, 12, 12)
    assert r.status_code == 409


def test_edge_adjacency_allowed(client, bed, library_plant):
    assert _place(client, bed.id, library_plant.id, 0, 0).status_code == 200
    # Exactly touching at x=24 is legal (AABB is exclusive at the edge)
    r = _place(client, bed.id, library_plant.id, 24, 0)
    assert r.status_code == 200


def test_default_spacing_is_12(client, db, bed):
    from apps.backend.app.db.models import PlantLibrary
    entry = PlantLibrary(name='Mystery', type='vegetable')  # no spacing_in
    db.add(entry)
    db.flush()
    r = _place(client, bed.id, entry.id, 0, 0)
    assert r.status_code == 200
    assert r.json()['spacing_in'] == 12


def test_unknown_library_entry_404(client, bed):
    r = _place(client, bed.id, 99999, 0, 0)
    assert r.status_code == 404


def test_bulk_placement_skips_collisions(client, bed, library_plant):
    assert _place(client, bed.id, library_plant.id, 0, 0).status_code == 200
    r = client.post(f'/api/beds/{bed.id}/grid-plant-bulk', json={
        'library_id': library_plant.id,
        'spacing_in': 24,
        'positions': [
            {'grid_x': 0,  'grid_y': 0},   # collides with existing
            {'grid_x': 24, 'grid_y': 0},   # ok
            {'grid_x': 40, 'grid_y': 40},  # out of bounds (40+24 > 48)
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data['placed']) == 1
    assert data['skipped'] == 2
    assert data['placed'][0]['grid_x'] == 24


def test_grid_returns_placed_plants(client, bed, library_plant):
    _place(client, bed.id, library_plant.id, 0, 0)
    r = client.get(f'/api/beds/{bed.id}/grid')
    assert r.status_code == 200
    data = r.json()
    assert data['bed']['id'] == bed.id
    assert len(data['placed']) == 1
    assert data['placed'][0]['plant_name'] == 'Tomato'
