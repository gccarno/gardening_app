"""Bed CRUD endpoint tests via TestClient."""


def test_create_bed(client, garden):
    r = client.post('/api/beds', json={'name': 'New Bed', 'garden_id': garden.id,
                                       'width_ft': 3, 'height_ft': 6})
    assert r.status_code == 200
    data = r.json()
    assert data['name'] == 'New Bed'
    assert data['width_ft'] == 3.0
    assert data['garden_id'] == garden.id


def test_create_bed_requires_name(client, garden):
    r = client.post('/api/beds', json={'garden_id': garden.id})
    assert r.status_code == 400


def test_create_bed_requires_garden(client):
    r = client.post('/api/beds', json={'name': 'Orphan'})
    assert r.status_code == 400


def test_create_bed_rejects_nonpositive_dimensions(client, garden):
    r = client.post('/api/beds', json={'name': 'Bad', 'garden_id': garden.id,
                                       'width_ft': 0, 'height_ft': 8})
    assert r.status_code == 400
    r = client.post('/api/beds', json={'name': 'Bad', 'garden_id': garden.id,
                                       'width_ft': 4, 'height_ft': -2})
    assert r.status_code == 400


def test_update_bed_rejects_nonpositive_dimensions(client, bed):
    r = client.put(f'/api/beds/{bed.id}', json={'width_ft': -1})
    assert r.status_code == 400


def test_get_bed(client, bed):
    r = client.get(f'/api/beds/{bed.id}')
    assert r.status_code == 200
    assert r.json()['name'] == bed.name


def test_get_bed_404(client):
    assert client.get('/api/beds/99999').status_code == 404


def test_list_beds_filters_by_garden(client, db, garden, bed):
    from apps.backend.app.db.models import GardenBed
    db.add(GardenBed(name='Unassigned', width_ft=2, height_ft=2))
    db.flush()

    all_beds = client.get('/api/beds').json()
    assert len(all_beds) == 2

    scoped = client.get(f'/api/beds?garden_id={garden.id}').json()
    assert len(scoped) == 1
    assert scoped[0]['id'] == bed.id


def test_update_bed_fields(client, bed):
    r = client.put(f'/api/beds/{bed.id}', json={
        'name': 'Renamed', 'soil_ph': 6.5, 'depth_ft': 1.5,
    })
    assert r.status_code == 200
    data = r.json()
    assert data['name'] == 'Renamed'
    assert data['soil_ph'] == 6.5
    assert data['depth_ft'] == 1.5


def test_bed_position(client, bed):
    r = client.post(f'/api/beds/{bed.id}/position', json={'x': 5.0, 'y': 3.0})
    assert r.status_code == 200
    r = client.post(f'/api/beds/{bed.id}/position', json={'x': 5.0})
    assert r.status_code == 400


def test_delete_bed(client, bed):
    assert client.post(f'/api/beds/{bed.id}/delete').json()['ok'] is True
    assert client.get(f'/api/beds/{bed.id}').status_code == 404


def test_delete_bed_clears_watering_rows(client, db, garden, bed):
    """A watered bed must still delete.

    watering_event.bed_id / ml_watering_snapshot.bed_id are plain FKs with no
    cascade, so leaving the rows behind is a ForeignKeyViolation 500 on
    Postgres. SQLite does not enforce FKs here, so assert the rows are gone
    rather than relying on the IntegrityError.
    """
    from datetime import date

    from apps.backend.app.db.models import MlWateringSnapshot, WateringEvent

    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id,
                         event_date=date.today(), amount='moderate', source='user'))
    db.add(MlWateringSnapshot(garden_id=garden.id, bed_id=bed.id,
                              snapshot_date=date.today()))
    db.flush()

    assert client.post(f'/api/beds/{bed.id}/delete').json()['ok'] is True
    assert db.query(WateringEvent).filter_by(bed_id=bed.id).count() == 0
    assert db.query(MlWateringSnapshot).filter_by(bed_id=bed.id).count() == 0
