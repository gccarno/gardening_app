"""
Unit tests for planner-related API endpoints:
  - GET  /beds/{bed_id}/grid
  - POST /beds/{bed_id}/grid-plant
  - PUT  /beds/{bed_id}
  - GET  /library/{entry_id}

Functions are called directly (no HTTP layer) using the in-memory SQLite
session from conftest.py, following the same pattern as test_chat_tools.py.
"""
import pytest
from fastapi import HTTPException

from apps.backend.app.db.models import BedPlant, GardenBed
from apps.backend.app.routers.beds import (
    api_bed_grid,
    api_bed_grid_plant,
    api_bed_update,
)
from apps.backend.app.routers.library import api_library_detail


# ── 1. GET /beds/{bed_id}/grid — empty bed ────────────────────────────────────

def test_get_bed_grid_empty(db, bed):
    result = api_bed_grid(bed.id, db=db)
    assert result['bed']['id'] == bed.id
    assert result['bed']['width_ft'] == 4.0
    assert result['bed']['height_ft'] == 8.0
    assert result['placed'] == []


# ── 2. POST /beds/{bed_id}/grid-plant — success from library ─────────────────

def test_post_bed_grid_plant_from_library(db, bed, library_plant):
    result = api_bed_grid_plant(bed.id, body={
        'grid_x': 0,
        'grid_y': 0,
        'spacing_in': 12,
        'library_id': library_plant.id,
    }, db=db)

    assert result['ok'] is True
    assert result['plant_name'] == 'Tomato'
    assert result['library_id'] == library_plant.id

    # Verify BedPlant row was created in DB
    bp = db.get(BedPlant, result['id'])
    assert bp is not None
    assert bp.grid_x == 0
    assert bp.grid_y == 0


# ── 3. POST /beds/{bed_id}/grid-plant — out of bounds ────────────────────────

def test_post_bed_grid_plant_out_of_bounds(db, bed, library_plant):
    # A 4 ft wide bed = 48 inches. Placing at x=47 with spacing=12 → 47+12=59 > 48 → 400
    with pytest.raises(HTTPException) as exc_info:
        api_bed_grid_plant(bed.id, body={
            'grid_x': 47,
            'grid_y': 0,
            'spacing_in': 12,
            'library_id': library_plant.id,
        }, db=db)
    assert exc_info.value.status_code == 400


# ── 4. POST /beds/{bed_id}/grid-plant — overlap detection ────────────────────

def test_post_bed_grid_plant_overlap(db, bed, library_plant):
    # Place first plant at (0, 0) with 12" spacing
    api_bed_grid_plant(bed.id, body={
        'grid_x': 0, 'grid_y': 0, 'spacing_in': 12,
        'library_id': library_plant.id,
    }, db=db)

    # Second plant at same location should fail with 409
    with pytest.raises(HTTPException) as exc_info:
        api_bed_grid_plant(bed.id, body={
            'grid_x': 0, 'grid_y': 0, 'spacing_in': 12,
            'library_id': library_plant.id,
        }, db=db)
    assert exc_info.value.status_code == 409


# ── 5. PUT /beds/{bed_id} — update bed info ───────────────────────────────────

def test_put_bed_update(db, bed):
    result = api_bed_update(bed.id, body={
        'name': 'Updated Bed',
        'width_ft': 6.0,
        'height_ft': 10.0,
        'soil_ph': 6.5,
        'soil_notes': 'Sandy loam',
    }, db=db)

    assert result['name'] == 'Updated Bed'
    assert result['width_ft'] == 6.0
    assert result['height_ft'] == 10.0
    assert result['soil_ph'] == 6.5
    assert result['soil_notes'] == 'Sandy loam'

    # Verify persisted in DB
    db.refresh(bed)
    assert bed.name == 'Updated Bed'
    assert bed.width_ft == 6.0
    assert bed.soil_ph == 6.5


# ── 6. GET /library/{entry_id} — plant detail ────────────────────────────────

def test_get_library_detail(db, library_plant):
    result = api_library_detail(library_plant.id, db=db)

    assert result['id'] == library_plant.id
    assert result['name'] == 'Tomato'
    assert result['sunlight'] == 'Full sun'
    assert result['spacing_in'] == 24
    assert result['days_to_germination'] == 7
    assert result['days_to_harvest'] == 70
