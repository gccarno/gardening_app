"""Soil moisture check-ins: the gardener's own dry/ok/wet reading per bed."""
from datetime import date, timedelta

from apps.backend.app.db.models import GardenBed, SoilMoistureCheckin


def _url(bed):
    return f'/api/beds/{bed.id}/moisture-checkins'


def test_create_and_list(client, bed):
    r = client.post(_url(bed), json={'level': 'dry', 'notes': 'cracked on top'})
    assert r.status_code == 200
    assert r.json()['level'] == 'dry'
    assert r.json()['check_date'] == date.today().isoformat()

    rows = client.get(_url(bed)).json()
    assert [(x['level'], x['notes']) for x in rows] == [('dry', 'cracked on top')]


def test_rejects_unknown_level(client, bed):
    assert client.post(_url(bed), json={'level': 'soggy'}).status_code == 400


def test_rejects_future_and_malformed_dates(client, bed):
    in_two_days = (date.today() + timedelta(days=2)).isoformat()
    assert client.post(_url(bed), json={'level': 'ok', 'check_date': in_two_days}).status_code == 400
    assert client.post(_url(bed), json={'level': 'ok', 'check_date': 'yesterday'}).status_code == 400


def test_allows_client_date_one_day_ahead_of_utc(client, bed):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert client.post(_url(bed), json={'level': 'ok', 'check_date': tomorrow}).status_code == 200


def test_second_reading_same_day_replaces_the_first(client, bed, db):
    client.post(_url(bed), json={'level': 'dry'})
    client.post(_url(bed), json={'level': 'wet'})

    rows = db.query(SoilMoistureCheckin).filter_by(bed_id=bed.id).all()
    assert [r.level for r in rows] == ['wet']


def test_list_is_newest_first_and_can_backdate(client, bed):
    old = (date.today() - timedelta(days=3)).isoformat()
    client.post(_url(bed), json={'level': 'dry', 'check_date': old})
    client.post(_url(bed), json={'level': 'ok'})

    assert [x['level'] for x in client.get(_url(bed)).json()] == ['ok', 'dry']


def test_notes_are_trimmed_to_the_column_width(client, bed):
    r = client.post(_url(bed), json={'level': 'ok', 'notes': 'x' * 500})
    assert len(r.json()['notes']) == 200


def test_unassigned_bed_is_rejected(client, db):
    orphan = GardenBed(name='Loose bed', width_ft=4.0, height_ft=4.0)
    db.add(orphan)
    db.flush()
    assert client.post(_url(orphan), json={'level': 'dry'}).status_code == 400


def test_missing_bed_is_404(client):
    assert client.post('/api/beds/99999/moisture-checkins', json={'level': 'dry'}).status_code == 404
    assert client.get('/api/beds/99999/moisture-checkins').status_code == 404


def test_deleting_a_bed_removes_its_checkins(client, bed, db):
    client.post(_url(bed), json={'level': 'dry'})
    bed_id = bed.id

    assert client.post(f'/api/beds/{bed_id}/delete').status_code == 200
    assert db.query(SoilMoistureCheckin).filter_by(bed_id=bed_id).count() == 0
