"""
Plant library image management and quick-edit routes.
"""
import os

import requests as http
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db.models import PlantLibrary, PlantLibraryImage
from ..db.session import get_db
from ..services.helpers import STATIC_DIR, ext_from_content_type, get_or_404
from ..services.files import save_plant_image

router = APIRouter(prefix='/api', tags=['library'])


@router.get('/library/{entry_id}/images')
def api_library_images_list(entry_id: int, db: Session = Depends(get_db)):
    entry = get_or_404(db, PlantLibrary, entry_id)
    return [{
        'id':          img.id,
        'filename':    img.filename,
        'source':      img.source,
        'attribution': img.attribution,
        'is_primary':  img.is_primary,
        'created_at':  img.created_at.isoformat(),
    } for img in entry.images]


@router.post('/library/{entry_id}/images')
async def api_library_images_add(
    entry_id: int,
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    entry = get_or_404(db, PlantLibrary, entry_id)

    if file and file.filename:
        ext        = os.path.splitext(file.filename)[1].lower() or '.jpg'
        img_bytes  = await file.read()
        source     = 'manual'
        attribution = None
        source_url  = None
    else:
        # Expect JSON body via query params fallback — handled by the client sending JSON
        raise HTTPException(status_code=400, detail='file required for this endpoint')

    img_row, was_dup = save_plant_image(db, entry, img_bytes, source, ext=ext,
                                        source_url=source_url, attribution=attribution)
    db.commit()
    return {'ok': True, 'image_id': img_row.id,
            'filename': img_row.filename, 'was_duplicate': was_dup}


@router.post('/library/{entry_id}/images/url')
def api_library_images_add_url(entry_id: int, body: dict, db: Session = Depends(get_db)):
    """Add an image from a URL (JSON body: {url, source?, attribution?})."""
    entry = get_or_404(db, PlantLibrary, entry_id)
    url = (body.get('url') or '').strip()
    if not url:
        raise HTTPException(status_code=400, detail='url required')
    source      = body.get('source', 'manual')
    attribution = body.get('attribution') or None
    try:
        r = http.get(url, timeout=15)
        r.raise_for_status()
        ext       = ext_from_content_type(r.headers.get('content-type', ''))
        img_bytes = r.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    img_row, was_dup = save_plant_image(db, entry, img_bytes, source, ext=ext,
                                        source_url=url, attribution=attribution)
    db.commit()
    return {'ok': True, 'image_id': img_row.id,
            'filename': img_row.filename, 'was_duplicate': was_dup}


@router.post('/library/images/{image_id}/set-primary')
def api_library_image_set_primary(image_id: int, db: Session = Depends(get_db)):
    img = get_or_404(db, PlantLibraryImage, image_id)
    db.query(PlantLibraryImage).filter_by(
        plant_library_id=img.plant_library_id, is_primary=True
    ).update({'is_primary': False})
    img.is_primary = True
    entry = db.get(PlantLibrary, img.plant_library_id)
    entry.image_filename = img.filename
    db.commit()
    return {'ok': True, 'filename': img.filename}


@router.post('/library/images/{image_id}/delete')
def api_library_image_delete(image_id: int, db: Session = Depends(get_db)):
    img              = get_or_404(db, PlantLibraryImage, image_id)
    was_primary      = img.is_primary
    plant_library_id = img.plant_library_id
    filename         = img.filename

    db.delete(img)
    db.flush()

    remaining = db.query(PlantLibraryImage).filter_by(filename=filename).count()
    if remaining == 0:
        fpath = STATIC_DIR / 'plant_images' / filename
        if fpath.exists():
            fpath.unlink()

    new_primary_filename = None
    if was_primary:
        next_img = (db.query(PlantLibraryImage)
                    .filter_by(plant_library_id=plant_library_id)
                    .order_by(PlantLibraryImage.created_at)
                    .first())
        if next_img:
            next_img.is_primary  = True
            new_primary_filename = next_img.filename
        entry = db.get(PlantLibrary, plant_library_id)
        entry.image_filename = new_primary_filename

    db.commit()
    return {'ok': True, 'new_primary_filename': new_primary_filename}


@router.post('/library/{entry_id}/quick-edit')
def api_library_quick_edit(entry_id: int, body: dict, db: Session = Depends(get_db)):
    lib = get_or_404(db, PlantLibrary, entry_id)
    if 'sunlight'   in body and body['sunlight']   is not None: lib.sunlight   = body['sunlight']
    if 'water'      in body and body['water']      is not None: lib.water      = body['water']
    if 'spacing_in' in body and body['spacing_in'] is not None: lib.spacing_in = int(body['spacing_in'])
    if 'notes'      in body and body['notes']      is not None: lib.notes      = body['notes']
    db.commit()
    return {'ok': True}


# Fields excluded from clone (external source IDs) and patch (identity fields)
_EXTERNAL_IDS = {'id', 'perenual_id', 'trefle_id', 'permapeople_id', 'usda_fdc_id',
                 'openfarm_id', 'openfarm_slug', 'trefle_slug', 'permapeople_link',
                 'cloned_from_id', 'is_custom'}

# All patchable scalar columns on PlantLibrary (excludes external IDs and relationship attrs)
_PATCHABLE_FIELDS = {
    'name', 'scientific_name', 'image_filename', 'type', 'spacing_in', 'sunlight', 'water',
    'days_to_germination', 'days_to_harvest', 'notes', 'difficulty', 'min_zone', 'max_zone',
    'temp_min_f', 'temp_max_f', 'soil_ph_min', 'soil_ph_max', 'soil_type',
    'good_neighbors', 'bad_neighbors', 'sow_indoor_weeks', 'direct_sow_offset',
    'transplant_offset', 'how_to_grow', 'faqs', 'nutrition',
    'permapeople_description', 'family', 'layer', 'edible_parts',
    'genus', 'edible', 'toxicity', 'duration', 'ligneous_type', 'growth_habit',
    'growth_form', 'growth_rate', 'nitrogen_fixation', 'vegetable', 'observations',
    'average_height_cm', 'maximum_height_cm', 'spread_cm', 'row_spacing_cm',
    'minimum_root_depth_cm', 'soil_nutriments', 'soil_salinity', 'atmospheric_humidity',
    'precipitation_min_mm', 'precipitation_max_mm', 'bloom_months', 'fruit_months',
    'growth_months', 'flower_color', 'flower_conspicuous', 'foliage_color', 'foliage_texture',
    'leaf_retention', 'fruit_color', 'fruit_conspicuous', 'fruit_shape', 'seed_persistence',
    'poisonous_to_pets', 'poisonous_to_humans', 'drought_tolerant', 'salt_tolerant',
    'thorny', 'invasive', 'rare', 'tropical', 'indoor', 'cuisine', 'medicinal',
    'attracts', 'propagation_methods', 'harvest_season', 'harvest_method',
    'fruiting_season', 'pruning_months',
}


@router.post('/library/{entry_id}/clone')
def api_library_clone(entry_id: int, body: dict, db: Session = Depends(get_db)):
    """Clone a plant library entry, giving the clone a new name."""
    source = get_or_404(db, PlantLibrary, entry_id)
    new_name = (body.get('name') or '').strip()
    if not new_name:
        raise HTTPException(status_code=400, detail='name is required')

    # Copy all scalar columns except external IDs
    clone_data = {}
    for col in PlantLibrary.__table__.columns:
        if col.name in _EXTERNAL_IDS:
            continue
        clone_data[col.name] = getattr(source, col.name)

    clone_data['name'] = new_name
    clone_data['cloned_from_id'] = entry_id
    clone_data['is_custom'] = True

    new_entry = PlantLibrary(**clone_data)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {'id': new_entry.id, 'name': new_entry.name}


@router.post('/library/{entry_id}/patch')
def api_library_patch(entry_id: int, body: dict, db: Session = Depends(get_db)):
    """Patch any patchable fields on a plant library entry."""
    lib = get_or_404(db, PlantLibrary, entry_id)
    unknown = set(body.keys()) - _PATCHABLE_FIELDS
    if unknown:
        raise HTTPException(status_code=400, detail=f'Unknown or non-patchable fields: {sorted(unknown)}')
    for field, value in body.items():
        setattr(lib, field, value)
    db.commit()
    return {'ok': True}


# ── Library browse (paginated) ────────────────────────────────────────────────

from typing import Optional


@router.get('/library')
def api_library_list(
    q: Optional[str] = None,
    type: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(PlantLibrary)
    if q:
        query = query.filter(PlantLibrary.name.ilike(f'%{q}%'))
    if type and type != 'all':
        query = query.filter(PlantLibrary.type == type)
    total = query.count()
    entries = (query
               .order_by(PlantLibrary.type, PlantLibrary.name)
               .offset((page - 1) * per_page)
               .limit(per_page)
               .all())
    return {
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'entries': [{
            'id':                  e.id,
            'name':                e.name,
            'type':                e.type,
            'spacing_in':          e.spacing_in,
            'sunlight':            e.sunlight,
            'water':               e.water,
            'days_to_germination': e.days_to_germination,
            'days_to_harvest':     e.days_to_harvest,
            'image_filename':      e.image_filename,
            'difficulty':          e.difficulty,
            'min_zone':            e.min_zone,
            'max_zone':            e.max_zone,
            'is_custom':           e.is_custom,
            'cloned_from_id':      e.cloned_from_id,
        } for e in entries],
    }


# ── Library entry detail ──────────────────────────────────────────────────────

@router.get('/library/{entry_id}')
def api_library_detail(entry_id: int, db: Session = Depends(get_db)):
    import json as _json
    from datetime import timedelta, datetime
    from ..services.helpers import FROST_DATES

    entry = get_or_404(db, PlantLibrary, entry_id)

    def _parse(col):
        try:
            return _json.loads(col) if col else None
        except Exception:
            return None

    _MONTH_NAMES = {
        'jan':'January','feb':'February','mar':'March','apr':'April',
        'may':'May','jun':'June','jul':'July','aug':'August',
        'sep':'September','oct':'October','nov':'November','dec':'December'
    }
    def _months(col):
        raw = _parse(col)
        if not raw: return None
        return ', '.join(_MONTH_NAMES.get(str(m).lower(), str(m)) for m in raw)

    calendar_rows = []
    if entry.sow_indoor_weeks is not None or entry.direct_sow_offset is not None or entry.transplant_offset is not None:
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
            calendar_rows.append(row)

    from ..db.models import Garden
    selected_zone = None
    g = db.query(Garden).filter(Garden.usda_zone.isnot(None)).first()
    if g and g.usda_zone:
        z = ''.join(filter(str.isdigit, g.usda_zone))
        selected_zone = int(z) if z else None

    images = [{
        'id': img.id,
        'filename': img.filename,
        'source': img.source,
        'attribution': img.attribution,
        'is_primary': img.is_primary,
    } for img in entry.images]

    cloned_from_name = None
    if entry.cloned_from_id:
        src = db.get(PlantLibrary, entry.cloned_from_id)
        cloned_from_name = src.name if src else None

    return {
        'id': entry.id,
        'name': entry.name,
        'scientific_name': entry.scientific_name,
        'is_custom': entry.is_custom,
        'cloned_from_id': entry.cloned_from_id,
        'cloned_from_name': cloned_from_name,
        'type': entry.type,
        'sunlight': entry.sunlight,
        'water': entry.water,
        'spacing_in': entry.spacing_in,
        'days_to_germination': entry.days_to_germination,
        'days_to_harvest': entry.days_to_harvest,
        'image_filename': entry.image_filename,
        'difficulty': entry.difficulty,
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
        'good_neighbors': _parse(entry.good_neighbors),
        'bad_neighbors':  _parse(entry.bad_neighbors),
        'how_to_grow':    _parse(entry.how_to_grow),
        'faqs':           _parse(entry.faqs),
        'nutrition':      _parse(entry.nutrition),
        'bloom_months':   _months(entry.bloom_months),
        'fruit_months':   _months(entry.fruit_months),
        'growth_months':  _months(entry.growth_months),
        'calendar_rows':  calendar_rows,
        'selected_zone':  selected_zone,
        'images':         images,
    }
