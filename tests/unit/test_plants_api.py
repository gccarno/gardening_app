"""Plant CRUD, status transitions, care sync, and bulk operations."""
from datetime import date, timedelta

from apps.backend.app.db.models import Plant


def test_create_plant(client, garden, library_plant):
    r = client.post('/api/plants', json={
        'name': 'Cherry Tomato', 'type': 'vegetable',
        'garden_id': garden.id, 'library_id': library_plant.id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data['name'] == 'Cherry Tomato'
    assert data['status'] == 'planning'
    assert data['scientific_name'] == library_plant.scientific_name


def test_list_plants_by_garden(client, db, garden, plant_in_bed):
    db.add(Plant(name='Elsewhere', status='planning'))
    db.flush()
    scoped = client.get(f'/api/plants?garden_id={garden.id}').json()
    assert [p['name'] for p in scoped] == ['Tomato']
    assert len(client.get('/api/plants').json()) == 2


def test_list_plants_by_status(client, plant_in_bed):
    assert len(client.get('/api/plants?status=growing').json()) == 1
    assert client.get('/api/plants?status=harvested').json() == []


def test_plant_detail_includes_beds_and_library(client, plant_in_bed):
    r = client.get(f'/api/plants/{plant_in_bed.id}')
    assert r.status_code == 200
    data = r.json()
    assert data['bed_assignments'][0]['bed_name'] == 'Raised Bed A'
    assert data['library']['name'] == 'Tomato'
    assert data['library']['good_neighbors'] == ['Basil', 'Carrot', 'Marigold']


def test_status_change_sets_planted_date(client, db, garden):
    p = Plant(name='Bean', garden_id=garden.id, status='planning')
    db.add(p)
    db.flush()
    r = client.post(f'/api/plants/{p.id}/status', json={'status': 'growing'})
    data = r.json()
    assert data['status'] == 'growing'
    assert data['planted_date'] == date.today().isoformat()


def test_bulk_status_rejects_invalid(client):
    r = client.post('/api/plants/bulk-status', json={'ids': [], 'status': 'dead'})
    assert r.status_code == 400


def test_bulk_care_updates_plant_and_bedplants(client, db, plant_in_bed):
    today = date.today().isoformat()
    r = client.post('/api/plants/bulk-care', json={
        'ids': [plant_in_bed.id], 'last_watered': today,
    })
    assert r.json()['updated'] == 1
    db.expire_all()
    assert plant_in_bed.last_watered == date.today()
    assert plant_in_bed.bed_plants[0].last_watered == date.today()


def test_sync_preview_detects_discrepancy(client, db, plant_in_bed):
    bp = plant_in_bed.bed_plants[0]
    bp.last_watered = date.today()
    plant_in_bed.last_watered = date.today() - timedelta(days=3)
    db.flush()

    changes = client.get('/api/plants/sync-preview').json()['changes']
    assert len(changes) == 1
    ch = changes[0]
    assert ch['field'] == 'last_watered'
    assert ch['direction'] == 'bed_to_plant'
    assert ch['proposed_value'] == date.today().isoformat()

    # Apply the sync and verify both sides converge
    r = client.post('/api/plants/sync', json={'changes': changes})
    assert r.json()['applied'] == 1
    db.expire_all()
    assert plant_in_bed.last_watered == date.today()
    assert client.get('/api/plants/sync-preview').json()['changes'] == []


def test_bulk_delete(client, db, garden):
    p1 = Plant(name='One', garden_id=garden.id)
    p2 = Plant(name='Two', garden_id=garden.id)
    db.add_all([p1, p2])
    db.flush()
    r = client.post('/api/plants/bulk-delete', json={'ids': [p1.id, p2.id, 99999]})
    assert r.json()['deleted'] == 2
    assert client.get('/api/plants').json() == []


def test_delete_plant(client, plant_in_bed):
    assert client.delete(f'/api/plants/{plant_in_bed.id}').json()['ok'] is True
    assert client.get(f'/api/plants/{plant_in_bed.id}').status_code == 404


def test_delete_plant_cascades_bed_placements_and_observations(client, db, plant_in_bed):
    # Regression: used to raise IntegrityError (bed_plant.plant_id NOT NULL)
    bp = plant_in_bed.bed_plants[0]
    client.post(f'/api/bedplants/{bp.id}/observations',
                json={'observation_type': 'healthy'})
    r = client.delete(f'/api/plants/{plant_in_bed.id}')
    assert r.status_code == 200
    from apps.backend.app.db.models import BedPlant, PlantObservation
    assert db.query(BedPlant).count() == 0
    assert db.query(PlantObservation).count() == 0
