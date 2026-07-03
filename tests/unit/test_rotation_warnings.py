"""Crop rotation warnings: botanical family conflicts within a bed."""
import pytest

from apps.backend.app.db.models import Plant, BedPlant, PlantLibrary


@pytest.fixture
def solanaceae_in_bed(db, garden, bed):
    lib = PlantLibrary(name='Tomato', type='vegetable', family='Solanaceae')
    db.add(lib)
    db.flush()
    plant = Plant(name='Tomato', garden_id=garden.id, library_id=lib.id, status='growing')
    db.add(plant)
    db.flush()
    db.add(BedPlant(bed_id=bed.id, plant_id=plant.id, grid_x=0, grid_y=0))
    db.flush()
    return lib


def test_families_in_bed_listed(client, bed, solanaceae_in_bed):
    r = client.get(f'/api/beds/{bed.id}/rotation-warnings')
    assert r.status_code == 200
    data = r.json()
    assert data['conflict'] is False
    assert [f['family'] for f in data['families_in_bed']] == ['Solanaceae']


def test_conflict_flagged_for_same_family(client, db, bed, solanaceae_in_bed):
    pepper = PlantLibrary(name='Pepper', type='vegetable', family='Solanaceae')
    db.add(pepper)
    db.flush()
    r = client.get(f'/api/beds/{bed.id}/rotation-warnings?library_id={pepper.id}')
    data = r.json()
    assert data['conflict'] is True
    assert data['candidate_family'] == 'Solanaceae'
    assert 'Solanaceae' in data['warning']


def test_no_conflict_for_different_family(client, db, bed, solanaceae_in_bed):
    carrot = PlantLibrary(name='Carrot', type='vegetable', family='Apiaceae')
    db.add(carrot)
    db.flush()
    r = client.get(f'/api/beds/{bed.id}/rotation-warnings?library_id={carrot.id}')
    data = r.json()
    assert data['conflict'] is False
    assert data['warning'] is None


def test_empty_bed_no_families(client, bed):
    r = client.get(f'/api/beds/{bed.id}/rotation-warnings')
    data = r.json()
    assert data['families_in_bed'] == []
    assert data['conflict'] is False
