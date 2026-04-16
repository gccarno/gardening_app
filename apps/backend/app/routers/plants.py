"""
Plant CRUD API routes.
"""
import json
import re
from datetime import date, timedelta, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db.models import Garden, GardenBed, Plant, BedPlant, PlantLibrary
from ..db.session import get_db
from ..services.helpers import FROST_DATES, get_or_404

router = APIRouter(prefix='/api', tags=['plants'])

_MONTH_NAMES = {
    'jan': 'January', 'feb': 'February', 'mar': 'March',    'apr': 'April',
    'may': 'May',     'jun': 'June',     'jul': 'July',      'aug': 'August',
    'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December',
}


def _parse_json(col):
    try:
        return json.loads(col) if col else None
    except Exception:
        return None


def _months_str(col) -> Optional[str]:
    raw = _parse_json(col)
    if not raw:
        return None
    return ', '.join(_MONTH_NAMES.get(str(m).lower(), str(m)) for m in raw)


def _calendar_rows(entry) -> list:
    if entry is None:
        return []
    if entry.sow_indoor_weeks is None and entry.direct_sow_offset is None and entry.transplant_offset is None:
        return []
    rows = []
    for zone_num in range(1, 14):
        last_spring, first_fall = FROST_DATES.get(str(zone_num), ('unknown', 'unknown'))
        if last_spring in ('none', 'rare', 'unknown'):
            continue
        try:
            frost = datetime.strptime(f'{last_spring} 2024', '%b %d %Y')
        except Exception:
            continue
        row: dict = {'zone': zone_num, 'last_frost': last_spring, 'first_fall_frost': first_fall}
        if entry.sow_indoor_weeks is not None:
            row['start_indoors'] = (frost - timedelta(weeks=entry.sow_indoor_weeks)).strftime('%b %d')
        if entry.direct_sow_offset is not None:
            row['direct_sow'] = (frost + timedelta(weeks=entry.direct_sow_offset)).strftime('%b %d')
        if entry.transplant_offset is not None:
            row['transplant'] = (frost + timedelta(weeks=entry.transplant_offset)).strftime('%b %d')
        rows.append(row)
    return rows


def _serialize_plant(p: Plant) -> dict:
    return {
        'id':              p.id,
        'name':            p.name,
        'type':            p.type,
        'status':          p.status,
        'notes':           p.notes,
        'planted_date':    p.planted_date.isoformat()    if p.planted_date    else None,
        'transplant_date': p.transplant_date.isoformat() if p.transplant_date else None,
        'expected_harvest': p.expected_harvest.isoformat() if p.expected_harvest else None,
        'last_watered':    p.last_watered.isoformat()    if p.last_watered    else None,
        'watering_amount': p.watering_amount,
        'last_fertilized': p.last_fertilized.isoformat() if p.last_fertilized else None,
        'fertilizer_type': p.fertilizer_type,
        'fertilizer_npk':  p.fertilizer_npk,
        'garden_id':       p.garden_id,
        'library_id':      p.library_id,
        'image_filename':      p.library_entry.image_filename      if p.library_entry else None,
        'scientific_name':     p.library_entry.scientific_name     if p.library_entry else None,
        'sunlight':            p.library_entry.sunlight            if p.library_entry else None,
        'days_to_harvest':     p.library_entry.days_to_harvest     if p.library_entry else None,
        'days_to_germination': p.library_entry.days_to_germination if p.library_entry else None,
        'sow_indoor_weeks':    p.library_entry.sow_indoor_weeks    if p.library_entry else None,
        'direct_sow_offset':   p.library_entry.direct_sow_offset   if p.library_entry else None,
        'transplant_offset':   p.library_entry.transplant_offset   if p.library_entry else None,
        'temp_max_f':          p.library_entry.temp_max_f          if p.library_entry else None,
        'bed_names':           [bp.bed.name for bp in p.bed_plants if bp.bed],
    }


# ── Plant CRUD ────────────────────────────────────────────────────────────────

@router.get('/plants')
def api_plants_list(
    garden_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Plant)
    if garden_id:
        in_bed_ids = (
            db.query(BedPlant.plant_id)
            .join(GardenBed, BedPlant.bed_id == GardenBed.id)
            .filter(GardenBed.garden_id == garden_id)
            .distinct()
        )
        q = q.filter(or_(Plant.garden_id == garden_id, Plant.id.in_(in_bed_ids)))
    if status:
        q = q.filter(Plant.status == status)
    plants = q.order_by(Plant.name).all()
    return [_serialize_plant(p) for p in plants]


@router.post('/plants')
def api_plants_create(body: dict, db: Session = Depends(get_db)):
    planted = body.get('planted_date')
    harvest = body.get('expected_harvest')
    plant = Plant(
        name=body['name'],
        type=body.get('type'),
        notes=body.get('notes'),
        status=body.get('status', 'planning'),
        garden_id=body.get('garden_id') or None,
        library_id=body.get('library_id') or None,
        planted_date=date.fromisoformat(planted) if planted else None,
        expected_harvest=date.fromisoformat(harvest) if harvest else None,
    )
    db.add(plant)
    db.commit()
    return _serialize_plant(plant)


@router.get('/plants/{plant_id}')
def api_plant_get(plant_id: int, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)
    entry = plant.library_entry
    today = date.today()

    # Selected zone: first garden with a zone
    selected_zone = None
    g = db.query(Garden).filter(Garden.usda_zone.isnot(None)).first()
    if g and g.usda_zone:
        z = ''.join(filter(str.isdigit, g.usda_zone))
        selected_zone = int(z) if z else None

    lib = None
    if entry:
        lib = {
            'id': entry.id,
            'name': entry.name,
            'scientific_name': entry.scientific_name,
            'type': entry.type,
            'sunlight': entry.sunlight,
            'water': entry.water,
            'spacing_in': entry.spacing_in,
            'days_to_germination': entry.days_to_germination,
            'days_to_harvest': entry.days_to_harvest,
            'min_zone': entry.min_zone,
            'max_zone': entry.max_zone,
            'temp_min_f': entry.temp_min_f,
            'temp_max_f': entry.temp_max_f,
            'soil_ph_min': entry.soil_ph_min,
            'soil_ph_max': entry.soil_ph_max,
            'soil_type': entry.soil_type,
            'notes': entry.notes,
            'family': entry.family,
            'layer': entry.layer,
            'edible_parts': entry.edible_parts,
            'permapeople_description': entry.permapeople_description,
            'permapeople_link': entry.permapeople_link,
            'image_filename': entry.image_filename,
            'difficulty': entry.difficulty,
            'observations': entry.observations,
            'vegetable': entry.vegetable,
            'toxicity': entry.toxicity,
            'duration': entry.duration,
            'growth_habit': entry.growth_habit,
            'growth_form': entry.growth_form,
            'growth_rate': entry.growth_rate,
            'ligneous_type': entry.ligneous_type,
            'nitrogen_fixation': entry.nitrogen_fixation,
            'average_height_cm': entry.average_height_cm,
            'maximum_height_cm': entry.maximum_height_cm,
            'spread_cm': entry.spread_cm,
            'flower_color': entry.flower_color,
            'flower_conspicuous': entry.flower_conspicuous,
            'foliage_color': entry.foliage_color,
            'foliage_texture': entry.foliage_texture,
            'leaf_retention': entry.leaf_retention,
            'fruit_color': entry.fruit_color,
            'fruit_conspicuous': entry.fruit_conspicuous,
            'fruit_shape': entry.fruit_shape,
            'soil_nutriments': entry.soil_nutriments,
            'soil_salinity': entry.soil_salinity,
            'atmospheric_humidity': entry.atmospheric_humidity,
            'precipitation_min_mm': entry.precipitation_min_mm,
            'precipitation_max_mm': entry.precipitation_max_mm,
            'row_spacing_cm': entry.row_spacing_cm,
            'minimum_root_depth_cm': entry.minimum_root_depth_cm,
            'sow_indoor_weeks': entry.sow_indoor_weeks,
            'direct_sow_offset': entry.direct_sow_offset,
            'transplant_offset': entry.transplant_offset,
            # Parsed JSON fields
            'good_neighbors': _parse_json(entry.good_neighbors),
            'bad_neighbors':  _parse_json(entry.bad_neighbors),
            'how_to_grow':    _parse_json(entry.how_to_grow),
            'faqs':           _parse_json(entry.faqs),
            'nutrition':      _parse_json(entry.nutrition),
            'bloom_months':   _months_str(entry.bloom_months),
            'fruit_months':   _months_str(entry.fruit_months),
            'growth_months':  _months_str(entry.growth_months),
            # Planting calendar
            'calendar_rows':  _calendar_rows(entry),
            'selected_zone':  selected_zone,
        }

    return {
        'id':              plant.id,
        'name':            plant.name,
        'type':            plant.type,
        'status':          plant.status,
        'notes':           plant.notes,
        'planted_date':    plant.planted_date.isoformat()    if plant.planted_date    else None,
        'transplant_date': plant.transplant_date.isoformat() if plant.transplant_date else None,
        'expected_harvest': plant.expected_harvest.isoformat() if plant.expected_harvest else None,
        'garden_id':       plant.garden_id,
        'library_id':      plant.library_id,
        'bed_assignments': [{
            'bp_id':       bp.id,
            'bed_id':      bp.bed.id,
            'bed_name':    bp.bed.name,
            'garden_name': bp.bed.garden.name if bp.bed.garden else None,
        } for bp in plant.bed_plants if bp.bed],
        'tasks': [{
            'id':        t.id,
            'title':     t.title,
            'task_type': t.task_type,
            'due_date':  t.due_date.isoformat() if t.due_date else None,
            'completed': t.completed,
        } for t in plant.tasks],
        'today':   today.isoformat(),
        'library': lib,
    }


# NOTE: bulk-status must be registered BEFORE /{plant_id} routes
@router.post('/plants/bulk-status')
def api_plants_bulk_status(body: dict, db: Session = Depends(get_db)):
    ids        = body.get('ids', [])
    new_status = body.get('status')
    if new_status not in ('planning', 'growing', 'harvested'):
        raise HTTPException(400, 'Invalid status')
    updated = 0
    for plant_id in ids:
        plant = db.get(Plant, plant_id)
        if not plant:
            continue
        plant.status = new_status
        if new_status == 'growing' and not plant.planted_date:
            plant.planted_date = date.today()
        updated += 1
    db.commit()
    return {'ok': True, 'updated': updated}


# NOTE: must be registered BEFORE /{plant_id} routes
@router.post('/plants/bulk-care')
def api_plants_bulk_care(body: dict, db: Session = Depends(get_db)):
    ids = body.get('ids', [])

    def _d(val):
        return date.fromisoformat(val) if val else None

    def _apply_care(obj):
        if 'last_watered'    in body: obj.last_watered    = _d(body['last_watered'])
        if 'watering_amount' in body: obj.watering_amount = body.get('watering_amount') or None
        if 'last_fertilized' in body: obj.last_fertilized = _d(body['last_fertilized'])
        if 'fertilizer_type' in body: obj.fertilizer_type = body.get('fertilizer_type') or None
        if 'fertilizer_npk'  in body: obj.fertilizer_npk  = body.get('fertilizer_npk') or None

    updated = 0
    for plant_id in ids:
        plant = db.get(Plant, plant_id)
        if not plant:
            continue
        _apply_care(plant)
        for bp in plant.bed_plants:
            _apply_care(bp)
        updated += 1
    db.commit()
    return {'ok': True, 'updated': updated}


@router.put('/plants/{plant_id}')
def api_plant_update(plant_id: int, body: dict, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)
    if 'name'            in body: plant.name            = body['name']
    if 'type'            in body: plant.type            = body.get('type') or None
    if 'notes'           in body: plant.notes           = body.get('notes') or None
    if 'planted_date'    in body:
        v = body.get('planted_date')
        plant.planted_date = date.fromisoformat(v) if v else None
    if 'expected_harvest' in body:
        v = body.get('expected_harvest')
        plant.expected_harvest = date.fromisoformat(v) if v else None
    db.commit()
    return _serialize_plant(plant)


@router.delete('/plants/{plant_id}')
def api_plant_delete_rest(plant_id: int, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)
    db.delete(plant)
    db.commit()
    return {'ok': True}


@router.post('/plants/{plant_id}/status')
def api_plant_set_status(plant_id: int, body: dict, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)
    new_status = body.get('status')
    if new_status in ('planning', 'growing', 'harvested'):
        plant.status = new_status
        if new_status == 'growing' and not plant.planted_date:
            plant.planted_date = date.today()
    db.commit()
    return _serialize_plant(plant)


# ── Legacy endpoints (kept for planner compatibility) ─────────────────────────

@router.get('/plants/{plant_id}/detail')
def api_plant_detail(plant_id: int, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)
    entry = plant.library_entry
    bp    = plant.bed_plants[0] if plant.bed_plants else None
    return {
        'id':              plant.id,
        'plant_name':      plant.name,
        'bp_id':           bp.id if bp else None,
        'image_filename':  entry.image_filename if entry else None,
        'scientific_name': entry.scientific_name if entry else None,
        'spacing_in':      entry.spacing_in if entry else None,
        'sunlight':        entry.sunlight if entry else None,
        'water':           entry.water if entry else None,
        'days_to_harvest': entry.days_to_harvest if entry else None,
        'planted_date':    plant.planted_date.isoformat()    if plant.planted_date    else None,
        'transplant_date': plant.transplant_date.isoformat() if plant.transplant_date else None,
        'plant_notes':     plant.notes or '',
        'last_watered':    bp.last_watered.isoformat()    if bp and bp.last_watered    else None,
        'last_fertilized': bp.last_fertilized.isoformat() if bp and bp.last_fertilized else None,
        'last_harvest':    bp.last_harvest.isoformat()    if bp and bp.last_harvest    else None,
        'health_notes':    bp.health_notes or '' if bp else '',
    }


@router.post('/plants/{plant_id}/care')
def api_plant_care(plant_id: int, body: dict, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)

    def _d(val):
        return date.fromisoformat(val) if val else None

    if 'planted_date'    in body: plant.planted_date    = _d(body['planted_date'])
    if 'transplant_date' in body: plant.transplant_date = _d(body['transplant_date'])
    if 'plant_notes'     in body: plant.notes           = body['plant_notes'] or None
    # Care fields — set on Plant directly (fixes canvas plants with no BedPlant)
    if 'last_watered'    in body: plant.last_watered    = _d(body['last_watered'])
    if 'watering_amount' in body: plant.watering_amount = body.get('watering_amount') or None
    if 'last_fertilized' in body: plant.last_fertilized = _d(body['last_fertilized'])
    if 'fertilizer_type' in body: plant.fertilizer_type = body.get('fertilizer_type') or None
    if 'fertilizer_npk'  in body: plant.fertilizer_npk  = body.get('fertilizer_npk') or None
    # Propagate to BedPlants for consistency
    for bp in plant.bed_plants:
        if 'last_watered'    in body: bp.last_watered    = _d(body['last_watered'])
        if 'watering_amount' in body: bp.watering_amount = body.get('watering_amount') or None
        if 'last_fertilized' in body: bp.last_fertilized = _d(body['last_fertilized'])
        if 'fertilizer_type' in body: bp.fertilizer_type = body.get('fertilizer_type') or None
        if 'fertilizer_npk'  in body: bp.fertilizer_npk  = body.get('fertilizer_npk') or None
    db.commit()
    return {'ok': True}


@router.post('/plants/{plant_id}/delete')
def api_delete_plant(plant_id: int, db: Session = Depends(get_db)):
    plant = get_or_404(db, Plant, plant_id)
    db.delete(plant)
    db.commit()
    return {'ok': True}
