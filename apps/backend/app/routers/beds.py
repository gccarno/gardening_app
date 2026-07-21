"""
Bed and BedPlant API routes.
"""
import logging
import os
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..db.models import Garden, GardenBed, Plant, BedPlant, PlantLibrary, User

logger = logging.getLogger(__name__)
from ..db.session import get_db
from ..services.auth import (
    get_current_user, member_garden_ids, require_garden, require_resource,
)
from ..services.helpers import get_or_404, record_watering_event
from ..services.storage import delete_static, save_static
from sqlalchemy import or_

_ALLOWED_IMG_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

router = APIRouter(prefix='/api', tags=['beds'])


# ── Internal helper ───────────────────────────────────────────────────────────

def _plant_from_library(db: Session, library_id: int):
    """Find a PlantLibrary entry and create a new Plant from it. Caller must flush/commit."""
    entry = db.get(PlantLibrary, library_id)
    if not entry:
        return None
    plant = Plant(name=entry.name, type=entry.type, library_id=entry.id)
    db.add(plant)
    db.flush()
    return plant


# ── Bed CRUD ──────────────────────────────────────────────────────────────────

@router.post('/beds')
def api_create_bed(body: dict,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if not body or not body.get('name'):
        raise HTTPException(status_code=400, detail='name required')
    garden_id = body.get('garden_id')
    if not garden_id:
        raise HTTPException(status_code=400, detail='garden_id required')
    require_garden(db, user, int(garden_id), 'editor')
    width_ft  = float(body.get('width_ft', 4.0))
    height_ft = float(body.get('height_ft', 8.0))
    if width_ft <= 0 or height_ft <= 0:
        raise HTTPException(status_code=400, detail='width_ft and height_ft must be positive')
    bed = GardenBed(
        name=body['name'],
        width_ft=width_ft,
        height_ft=height_ft,
        garden_id=int(garden_id),
    )
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return _serialize_bed(bed)


@router.post('/beds/{bed_id}/position')
def api_bed_position(bed_id: int, body: dict,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    if body is None or 'x' not in body or 'y' not in body:
        raise HTTPException(status_code=400, detail='x and y required')
    bed.pos_x = float(body['x'])
    bed.pos_y = float(body['y'])
    db.commit()
    return {'ok': True}


@router.post('/beds/{bed_id}/assign-garden')
def api_bed_assign_garden(bed_id: int, body: dict,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    if not body or 'garden_id' not in body:
        raise HTTPException(status_code=400, detail='garden_id required')
    require_garden(db, user, int(body['garden_id']), 'editor')
    bed.garden_id = int(body['garden_id'])
    db.commit()
    return {'ok': True}


@router.post('/beds/{bed_id}/delete')
def api_delete_bed(bed_id: int,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    db.delete(bed)
    db.commit()
    return {'ok': True}


# ── Bed grid ──────────────────────────────────────────────────────────────────

@router.get('/beds/{bed_id}/grid')
def api_bed_grid(bed_id: int,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    t0 = time.monotonic()
    require_resource(db, user, GardenBed, bed_id, 'viewer')
    bed = (
        db.query(GardenBed)
        .options(
            joinedload(GardenBed.bed_plants)
            .joinedload(BedPlant.plant)
            .joinedload(Plant.library_entry)
        )
        .filter(GardenBed.id == bed_id)
        .first()
    )
    if not bed:
        raise HTTPException(status_code=404, detail='Not found')
    placed = []
    for bp in bed.bed_plants:
        if bp.grid_x is None or bp.grid_y is None:
            continue
        entry = bp.plant.library_entry if bp.plant else None
        placed.append({
            'id':             bp.id,
            'plant_id':       bp.plant_id,
            'plant_name':     bp.plant.name if bp.plant else '?',
            'image_filename': entry.image_filename if entry else None,
            'spacing_in':     entry.spacing_in if entry and entry.spacing_in else 12,
            'grid_x':         bp.grid_x,
            'grid_y':         bp.grid_y,
        })
    logger.info('[bed_grid] bed %d: %d placed in %.0fms', bed_id, len(placed), (time.monotonic() - t0) * 1000)
    return {
        'bed': {'id': bed.id, 'name': bed.name,
                'width_ft': bed.width_ft, 'height_ft': bed.height_ft},
        'placed': placed,
    }


@router.post('/beds/{bed_id}/grid-plant')
def api_bed_grid_plant(bed_id: int, body: dict,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    if not body or 'grid_x' not in body or 'grid_y' not in body:
        raise HTTPException(status_code=400, detail='grid_x and grid_y required')
    grid_x     = int(body['grid_x'])
    grid_y     = int(body['grid_y'])
    spacing_in = int(body.get('spacing_in', 12))

    # Bounds check
    bed_w_in = bed.width_ft * 12
    bed_h_in = bed.height_ft * 12
    if grid_x + spacing_in > bed_w_in or grid_y + spacing_in > bed_h_in:
        raise HTTPException(status_code=400, detail='plant does not fit within bed bounds')

    # Overlap check (AABB)
    for existing in bed.bed_plants:
        if existing.grid_x is None or existing.grid_y is None:
            continue
        ex_entry   = existing.plant.library_entry if existing.plant else None
        ex_spacing = ex_entry.spacing_in if ex_entry and ex_entry.spacing_in else 12
        if not (grid_x >= existing.grid_x + ex_spacing or
                existing.grid_x >= grid_x + spacing_in or
                grid_y >= existing.grid_y + ex_spacing or
                existing.grid_y >= grid_y + spacing_in):
            raise HTTPException(status_code=409, detail='overlaps existing plant')

    if 'library_id' in body:
        plant = _plant_from_library(db, int(body['library_id']))
        if not plant:
            raise HTTPException(status_code=404, detail='library entry not found')
    elif 'plant_id' in body:
        plant = get_or_404(db, Plant, int(body['plant_id']))
    else:
        raise HTTPException(status_code=400, detail='library_id or plant_id required')

    bp = BedPlant(bed_id=bed_id, plant_id=plant.id, grid_x=grid_x, grid_y=grid_y)
    db.add(bp)
    db.commit()
    entry = plant.library_entry
    return {
        'ok':             True,
        'id':             bp.id,
        'plant_id':       plant.id,
        'library_id':     plant.library_id,
        'plant_name':     plant.name,
        'image_filename': entry.image_filename if entry else None,
        'spacing_in':     entry.spacing_in if entry and entry.spacing_in else 12,
        'grid_x':         grid_x,
        'grid_y':         grid_y,
    }


@router.post('/beds/{bed_id}/grid-plant-bulk')
def api_bed_grid_plant_bulk(bed_id: int, body: dict,
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """Place multiple plants at once (best-effort: skips overlapping/out-of-bounds positions)."""
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    positions  = body.get('positions', [])
    spacing_in = int(body.get('spacing_in', 12))
    bed_w_in   = bed.width_ft * 12
    bed_h_in   = bed.height_ft * 12

    if 'library_id' in body:
        lib_entry = db.get(PlantLibrary, int(body['library_id']))
        if not lib_entry:
            raise HTTPException(status_code=404, detail='library entry not found')
    elif 'plant_id' in body:
        source = get_or_404(db, Plant, int(body['plant_id']))
        lib_entry = source.library_entry
    else:
        raise HTTPException(status_code=400, detail='library_id or plant_id required')

    # Build inch-level occupancy set from existing plants
    occupied: set[tuple[int, int]] = set()
    for existing in bed.bed_plants:
        if existing.grid_x is None or existing.grid_y is None:
            continue
        ex_entry   = existing.plant.library_entry if existing.plant else None
        ex_spacing = ex_entry.spacing_in if ex_entry and ex_entry.spacing_in else 12
        for dy in range(ex_spacing):
            for dx in range(ex_spacing):
                occupied.add((existing.grid_x + dx, existing.grid_y + dy))

    placed_results = []
    skipped = 0

    for pos in positions:
        gx, gy = int(pos['grid_x']), int(pos['grid_y'])
        if gx + spacing_in > bed_w_in or gy + spacing_in > bed_h_in:
            skipped += 1
            continue
        if any((gx + dx, gy + dy) in occupied for dx in range(spacing_in) for dy in range(spacing_in)):
            skipped += 1
            continue

        plant = _plant_from_library(db, lib_entry.id)
        db.flush()
        bp = BedPlant(bed_id=bed_id, plant_id=plant.id, grid_x=gx, grid_y=gy)
        db.add(bp)
        db.flush()

        # Mark newly occupied cells so later positions in this batch respect them
        for dy in range(spacing_in):
            for dx in range(spacing_in):
                occupied.add((gx + dx, gy + dy))

        placed_results.append({
            'id':             bp.id,
            'grid_x':         gx,
            'grid_y':         gy,
            'plant_name':     plant.name,
            'image_filename': lib_entry.image_filename if lib_entry else None,
            'spacing_in':     spacing_in,
        })

    db.commit()
    return {'ok': True, 'placed': placed_results, 'skipped': skipped}


# ── BedPlant CRUD ─────────────────────────────────────────────────────────────

@router.post('/bedplants')
def api_create_bedplant(body: dict,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if not body or 'bed_id' not in body:
        raise HTTPException(status_code=400, detail='bed_id required')
    require_resource(db, user, GardenBed, int(body['bed_id']), 'editor')
    if 'library_id' in body:
        plant = _plant_from_library(db, int(body['library_id']))
        if not plant:
            raise HTTPException(status_code=404, detail='library entry not found')
    elif 'plant_id' in body:
        plant = get_or_404(db, Plant, int(body['plant_id']))
    else:
        raise HTTPException(status_code=400, detail='library_id or plant_id required')
    bp = BedPlant(bed_id=int(body['bed_id']), plant_id=plant.id)
    db.add(bp)
    db.commit()
    entry = plant.library_entry
    return {
        'ok': True, 'id': bp.id,
        'plant': {
            'id': plant.id, 'name': plant.name,
            'image_filename': entry.image_filename if entry else None,
        },
    }


# NOTE: bulk-care must be registered BEFORE /{bp_id} to avoid "bulk-care" matching as int ID
@router.post('/bedplants/bulk-care')
def api_bedplants_bulk_care(body: dict,
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    ids     = body.get('ids', [])
    updated = 0

    def _d(val):
        return date.fromisoformat(val) if val else None

    for bp_id in ids:
        try:
            bp = require_resource(db, user, BedPlant, bp_id, 'editor')
        except HTTPException:
            continue  # best-effort: skip missing/unauthorized ids
        if 'last_watered'    in body: bp.last_watered    = _d(body['last_watered'])
        if 'watering_amount' in body: bp.watering_amount = body.get('watering_amount') or None
        if 'last_fertilized' in body: bp.last_fertilized = _d(body['last_fertilized'])
        if 'fertilizer_type' in body: bp.fertilizer_type = body.get('fertilizer_type') or None
        if 'fertilizer_npk'  in body: bp.fertilizer_npk  = body.get('fertilizer_npk') or None
        if 'last_harvest'    in body: bp.last_harvest    = _d(body['last_harvest'])
        if 'health_notes'    in body: bp.health_notes    = body['health_notes'] or None
        if 'stage'           in body: bp.stage           = body['stage'] or None
        if bp.plant:
            if 'last_watered'    in body: bp.plant.last_watered    = _d(body['last_watered'])
            if 'watering_amount' in body: bp.plant.watering_amount = body.get('watering_amount') or None
            if 'last_fertilized' in body: bp.plant.last_fertilized = _d(body['last_fertilized'])
            if 'fertilizer_type' in body: bp.plant.fertilizer_type = body.get('fertilizer_type') or None
            if 'fertilizer_npk'  in body: bp.plant.fertilizer_npk  = body.get('fertilizer_npk') or None
            if 'planted_date'    in body: bp.plant.planted_date    = _d(body['planted_date'])
            if 'transplant_date' in body: bp.plant.transplant_date = _d(body['transplant_date'])
            if 'plant_notes'     in body: bp.plant.notes           = body['plant_notes'] or None
        if body.get('last_watered'):
            garden_id = bp.bed.garden_id if bp.bed else None
            record_watering_event(db, garden_id, bp.bed_id, body.get('watering_amount') or None, 'user')
        updated += 1
    db.commit()
    return {'ok': True, 'updated': updated}


@router.get('/bedplants/{bp_id}')
def api_bedplant_detail(bp_id: int,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    bp    = require_resource(db, user, BedPlant, bp_id, 'viewer')
    entry = bp.plant.library_entry if bp.plant else None
    plant = bp.plant
    return {
        'id':              bp.id,
        'plant_id':        plant.id if plant else None,
        'plant_name':      plant.name if plant else '?',
        'image_filename':  entry.image_filename if entry else None,
        'scientific_name': entry.scientific_name if entry else None,
        'spacing_in':      entry.spacing_in if entry else None,
        'sunlight':        entry.sunlight if entry else None,
        'water':           entry.water if entry else None,
        'days_to_harvest': entry.days_to_harvest if entry else None,
        'planted_date':    plant.planted_date.isoformat()    if plant and plant.planted_date    else None,
        'transplant_date': plant.transplant_date.isoformat() if plant and plant.transplant_date else None,
        'plant_notes':     plant.notes or '' if plant else '',
        'last_watered':    bp.last_watered.isoformat()    if bp.last_watered    else None,
        'last_fertilized': bp.last_fertilized.isoformat() if bp.last_fertilized else None,
        'last_harvest':    bp.last_harvest.isoformat()    if bp.last_harvest    else None,
        'health_notes':    bp.health_notes or '',
        'stage':           bp.stage or 'seedling',
    }


@router.post('/bedplants/{bp_id}/care')
def api_bedplant_care(bp_id: int, body: dict,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    bp = require_resource(db, user, BedPlant, bp_id, 'editor')

    def _d(val):
        return date.fromisoformat(val) if val else None

    if 'last_watered'    in body: bp.last_watered    = _d(body['last_watered'])
    if 'last_fertilized' in body: bp.last_fertilized = _d(body['last_fertilized'])
    if 'last_harvest'    in body: bp.last_harvest    = _d(body['last_harvest'])
    if 'health_notes'    in body: bp.health_notes    = body['health_notes'] or None
    if bp.plant:
        if 'planted_date'    in body: bp.plant.planted_date    = _d(body['planted_date'])
        if 'transplant_date' in body: bp.plant.transplant_date = _d(body['transplant_date'])
        if 'plant_notes'     in body: bp.plant.notes           = body['plant_notes'] or None
    if 'stage' in body: bp.stage = body['stage'] or None
    if body.get('last_watered'):
        garden_id = bp.bed.garden_id if bp.bed else None
        record_watering_event(db, garden_id, bp.bed_id, None, 'user')
    db.commit()
    return {'ok': True}


@router.post('/bedplants/{bp_id}/delete')
def api_delete_bedplant(bp_id: int,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    bp = require_resource(db, user, BedPlant, bp_id, 'editor')
    db.delete(bp)
    db.commit()
    return {'ok': True}


# ── Bed list / detail / update ────────────────────────────────────────────────

def _serialize_bed(b: GardenBed) -> dict:
    return {
        'id':          b.id,
        'name':        b.name,
        'garden_id':   b.garden_id,
        'garden_name': b.garden.name if b.garden else None,
        'width_ft':    b.width_ft,
        'height_ft':   b.height_ft,
        'depth_ft':    b.depth_ft,
        'location':    b.location,
        'description': b.description,
        'soil_notes':  b.soil_notes,
        'soil_ph':     b.soil_ph,
        'clay_pct':    b.clay_pct,
        'compost_pct': b.compost_pct,
        'sand_pct':    b.sand_pct,
        'pos_x':            b.pos_x,
        'pos_y':            b.pos_y,
        'plant_count':      len(b.bed_plants),
        'color':               b.color,
        'background_image':    b.background_image,
        'background_pattern':  b.background_pattern,
        'last_weeded':         b.last_weeded.isoformat() if b.last_weeded else None,
    }


@router.get('/beds')
def api_beds_list(garden_id: Optional[int] = None,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    t0 = time.monotonic()
    q = db.query(GardenBed).options(
        joinedload(GardenBed.garden),
        joinedload(GardenBed.bed_plants),
    )
    if garden_id:
        require_garden(db, user, garden_id, 'viewer')
        q = q.filter(GardenBed.garden_id == garden_id)
    else:
        member_ids = member_garden_ids(db, user)
        q = q.filter(or_(GardenBed.garden_id.in_(member_ids),
                         GardenBed.garden_id.is_(None)))
    beds = q.order_by(GardenBed.name).all()
    logger.info('[beds_list] %d beds in %.0fms', len(beds), (time.monotonic() - t0) * 1000)
    return [_serialize_bed(b) for b in beds]


@router.get('/beds/{bed_id}/rotation-warnings')
def api_bed_rotation_warnings(bed_id: int, library_id: Optional[int] = None,
                              user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """
    Returns botanical families currently growing in this bed.
    If library_id is given, also flags whether the candidate plant shares a family
    with any existing bed plant.
    """
    bed = require_resource(db, user, GardenBed, bed_id, 'viewer')
    bed_plants = (db.query(BedPlant)
                  .filter(BedPlant.bed_id == bed_id)
                  .join(Plant, BedPlant.plant_id == Plant.id)
                  .join(PlantLibrary, Plant.library_id == PlantLibrary.id)
                  .all())

    families_in_bed: list[dict] = []
    seen: set[str] = set()
    for bp in bed_plants:
        lib = bp.plant.library_entry if bp.plant else None
        fam = lib.family if lib else None
        if fam and fam not in seen:
            seen.add(fam)
            families_in_bed.append({'family': fam, 'plant_name': bp.plant.name})

    conflict = False
    candidate_family = None
    if library_id:
        candidate = db.get(PlantLibrary, library_id)
        if candidate and candidate.family:
            candidate_family = candidate.family
            conflict = candidate.family in seen

    return {
        'bed_id': bed_id,
        'families_in_bed': families_in_bed,
        'candidate_family': candidate_family,
        'conflict': conflict,
        'warning': (
            f'Crop rotation: {candidate_family} already growing in this bed.'
            if conflict else None
        ),
    }


@router.get('/beds/{bed_id}')
def api_bed_get(bed_id: int,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'viewer')
    return _serialize_bed(bed)


@router.put('/beds/{bed_id}')
def api_bed_update(bed_id: int, body: dict,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    for f in ('name', 'location', 'description', 'soil_notes'):
        if f in body: setattr(bed, f, body[f] or None)
    for f in ('soil_ph', 'clay_pct', 'compost_pct', 'sand_pct', 'depth_ft'):
        if f in body: setattr(bed, f, float(body[f]) if body[f] is not None else None)
    if 'width_ft'  in body and body['width_ft']:
        if float(body['width_ft']) <= 0:
            raise HTTPException(status_code=400, detail='width_ft must be positive')
        bed.width_ft = float(body['width_ft'])
    if 'height_ft' in body and body['height_ft']:
        if float(body['height_ft']) <= 0:
            raise HTTPException(status_code=400, detail='height_ft must be positive')
        bed.height_ft = float(body['height_ft'])
    if 'name'      in body and body['name']:       bed.name      = body['name']
    if 'color'              in body: bed.color              = body.get('color') or None
    if 'background_pattern' in body: bed.background_pattern = body.get('background_pattern') or None
    if 'last_weeded' in body:
        v = body.get('last_weeded')
        bed.last_weeded = date.fromisoformat(v) if v else None
    db.commit()
    return _serialize_bed(bed)


# ── Bed background image ───────────────────────────────────────────────────────

@router.post('/beds/{bed_id}/upload-background')
async def upload_bed_background(
    bed_id: int,
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    ext = os.path.splitext(image.filename or '')[1].lower()
    if ext not in _ALLOWED_IMG_EXTS:
        raise HTTPException(status_code=400, detail='Unsupported file type')

    if bed.background_image:
        delete_static(f'bed_images/{bed.background_image}')

    filename = f'bed_{bed_id}{ext}'
    contents = await image.read()
    save_static(f'bed_images/{filename}', contents)

    bed.background_image = filename
    db.commit()
    return {'filename': filename, 'url': f'/static/bed_images/{filename}'}


@router.post('/beds/{bed_id}/remove-background')
def remove_bed_background(bed_id: int,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    bed = require_resource(db, user, GardenBed, bed_id, 'editor')
    if bed.background_image:
        delete_static(f'bed_images/{bed.background_image}')
        bed.background_image = None
        db.commit()
    return {'ok': True}
