"""
Canvas plant routes — interactive 2D garden planner visual layer.
"""
import glob
import logging
import os
import re
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..db.models import CanvasPlant, Garden, Plant, PlantLibrary

logger = logging.getLogger(__name__)
from ..db.session import get_db
from ..services.helpers import STATIC_DIR, get_or_404
from ..services.files import save_plant_image

router = APIRouter(prefix='/api', tags=['canvas'])

_ALLOWED_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def _cp_color_for_type(plant_type: str | None) -> str:
    return {
        'vegetable': '#5a9e54',
        'herb':      '#8bc34a',
        'fruit':     '#ff8c42',
        'flower':    '#e91e8c',
    }.get((plant_type or '').lower(), '#5a9e54')


def _serialize_cp(cp: CanvasPlant, svg_files: set | None = None, ai_files: set | None = None) -> dict:
    """Serialize a CanvasPlant.

    svg_files / ai_files: pre-scanned directory listing sets (for bulk serialization).
    Pass None to fall back to glob.glob() (for single-plant endpoints).
    """
    lib = cp.library_entry
    svg_icon_url = None
    ai_icon_url  = None
    if cp.library_id:
        prefix = str(cp.library_id)
        if svg_files is not None:
            svg_match = next((f for f in svg_files if f.startswith(f'{prefix}_') and f.endswith('.svg')), None)
            if svg_match:
                svg_icon_url = f'/static/plant_svg_icons/{svg_match}'
        else:
            svg_matches = glob.glob(str(STATIC_DIR / 'plant_svg_icons' / f'{cp.library_id}_*.svg'))
            if svg_matches:
                svg_icon_url = f'/static/plant_svg_icons/{os.path.basename(svg_matches[0])}'

        if ai_files is not None:
            ai_candidates = [f for f in ai_files if f.startswith(f'{prefix}_') and f.endswith('.png')]
            canonical = [f for f in ai_candidates if not re.search(r'_s\d+\.png$', f)]
            chosen = canonical[0] if canonical else (ai_candidates[0] if ai_candidates else None)
            if chosen:
                ai_icon_url = f'/static/plant_ai_images/{chosen}'
        else:
            ai_matches = glob.glob(str(STATIC_DIR / 'plant_ai_images' / f'{cp.library_id}_*.png'))
            canonical = [m for m in ai_matches if not re.search(r'_s\d+\.png$', m)]
            chosen = canonical[0] if canonical else (ai_matches[0] if ai_matches else None)
            if chosen:
                ai_icon_url = f'/static/plant_ai_images/{os.path.basename(chosen)}'
    return {
        'id':              cp.id,
        'pos_x':           cp.pos_x,
        'pos_y':           cp.pos_y,
        'radius_ft':       cp.radius_ft,
        'color':           cp.color or '#5a9e54',
        'display_mode':    cp.display_mode or 'color',
        'library_id':      cp.library_id,
        'plant_id':        cp.plant_id,
        'name':            cp.label or (lib.name if lib else (cp.plant.name if cp.plant else '?')),
        'image_filename':  cp.custom_image or (lib.image_filename if lib else None),
        'custom_image':    cp.custom_image,
        'svg_icon_url':    svg_icon_url,
        'ai_icon_url':     ai_icon_url,
        'scientific_name': lib.scientific_name if lib else None,
        'sunlight':        lib.sunlight   if lib else None,
        'water':           lib.water      if lib else None,
        'spacing_in':      lib.spacing_in if lib else None,
        'lib_notes':       lib.notes      if lib else None,
        'planted_date':    cp.plant.planted_date.isoformat()    if cp.plant and cp.plant.planted_date    else None,
        'transplant_date': cp.plant.transplant_date.isoformat() if cp.plant and cp.plant.transplant_date else None,
        'plant_notes':     cp.plant.notes or ''                 if cp.plant                              else '',
        'status':          cp.plant.status                                         if cp.plant                              else 'planning',
        'last_watered':    cp.plant.last_watered.isoformat()                       if cp.plant and cp.plant.last_watered    else None,
        'watering_amount': cp.plant.watering_amount                                if cp.plant                              else None,
        'last_fertilized': cp.plant.last_fertilized.isoformat()                    if cp.plant and cp.plant.last_fertilized else None,
        'fertilizer_type': cp.plant.fertilizer_type                                if cp.plant                              else None,
        'fertilizer_npk':  cp.plant.fertilizer_npk                                 if cp.plant                              else None,
    }


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get('/gardens/{garden_id}/canvas-plants')
def api_canvas_plants_list(garden_id: int, db: Session = Depends(get_db)):
    t0 = time.monotonic()
    get_or_404(db, Garden, garden_id)
    cps = (
        db.query(CanvasPlant)
        .filter_by(garden_id=garden_id)
        .options(
            joinedload(CanvasPlant.library_entry),
            joinedload(CanvasPlant.plant),
        )
        .all()
    )

    # Pre-scan icon directories once instead of glob()-ing per plant
    svg_dir = STATIC_DIR / 'plant_svg_icons'
    ai_dir  = STATIC_DIR / 'plant_ai_images'
    svg_files = set(os.listdir(svg_dir)) if svg_dir.exists() else set()
    ai_files  = set(os.listdir(ai_dir))  if ai_dir.exists()  else set()

    result = [_serialize_cp(cp, svg_files, ai_files) for cp in cps]
    logger.info('[canvas_plants_list] garden %d: %d plants in %.0fms', garden_id, len(cps), (time.monotonic() - t0) * 1000)
    return result


@router.post('/gardens/{garden_id}/canvas-plants')
def api_canvas_plants_create(garden_id: int, body: dict, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    library_id = body.get('library_id')
    plant_id   = body.get('plant_id')
    pos_x      = float(body.get('pos_x', 0))
    pos_y      = float(body.get('pos_y', 0))

    lib   = db.get(PlantLibrary, library_id) if library_id else None
    plant = db.get(Plant, plant_id)          if plant_id   else None

    if lib and not plant:
        plant = Plant(name=lib.name, library_id=lib.id, garden_id=garden_id, status='planning')
        db.add(plant)
        db.flush()

    if lib and lib.spacing_in:
        radius_ft = round((lib.spacing_in / 12) / 2, 2)
    else:
        radius_ft = 1.0
    radius_ft = max(0.25, radius_ft)

    cp = CanvasPlant(
        garden_id=garden_id,
        library_id=library_id,
        plant_id=plant.id if plant else None,
        pos_x=pos_x,
        pos_y=pos_y,
        radius_ft=radius_ft,
        color=_cp_color_for_type(lib.type if lib else None),
        display_mode='color',
    )
    db.add(cp)
    db.commit()
    return {'ok': True, 'canvas_plant': _serialize_cp(cp)}


# ── Detail / Update ───────────────────────────────────────────────────────────

@router.get('/canvas-plants/{cp_id}')
def api_canvas_plant_detail(cp_id: int, db: Session = Depends(get_db)):
    return _serialize_cp(get_or_404(db, CanvasPlant, cp_id))


@router.post('/canvas-plants/{cp_id}/position')
def api_canvas_plant_position(cp_id: int, body: dict, db: Session = Depends(get_db)):
    cp = get_or_404(db, CanvasPlant, cp_id)
    cp.pos_x = float(body.get('x', cp.pos_x))
    cp.pos_y = float(body.get('y', cp.pos_y))
    db.commit()
    return {'ok': True}


@router.post('/canvas-plants/{cp_id}/radius')
def api_canvas_plant_radius(cp_id: int, body: dict, db: Session = Depends(get_db)):
    cp = get_or_404(db, CanvasPlant, cp_id)
    cp.radius_ft = max(0.1, float(body.get('radius_ft', cp.radius_ft)))
    db.commit()
    return {'ok': True}


@router.post('/canvas-plants/{cp_id}/appearance')
def api_canvas_plant_appearance(cp_id: int, body: dict, db: Session = Depends(get_db)):
    cp = get_or_404(db, CanvasPlant, cp_id)
    if 'color'        in body: cp.color        = body['color']        or cp.color
    if 'display_mode' in body: cp.display_mode = body['display_mode'] or cp.display_mode
    if 'label'        in body: cp.label        = body['label']        or None
    db.commit()
    return {'ok': True}


@router.post('/canvas-plants/{cp_id}/upload-image')
async def api_canvas_plant_upload_image(
    cp_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    cp  = get_or_404(db, CanvasPlant, cp_id)
    ext = os.path.splitext(image.filename or '')[1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail='Unsupported file type')

    img_dir = STATIC_DIR / 'canvas_plant_images'
    img_dir.mkdir(parents=True, exist_ok=True)

    if cp.custom_image:
        old_path = img_dir / cp.custom_image
        if old_path.exists():
            old_path.unlink()

    filename = f'cp_{cp_id}{ext}'
    contents = await image.read()
    (img_dir / filename).write_bytes(contents)

    cp.custom_image = filename
    cp.display_mode = 'image'
    db.commit()
    return {'ok': True, 'filename': filename, 'url': f'/static/canvas_plant_images/{filename}'}


@router.post('/canvas-plants/{cp_id}/save-image-to-library')
def api_canvas_plant_save_image_to_library(cp_id: int, db: Session = Depends(get_db)):
    cp = get_or_404(db, CanvasPlant, cp_id)
    if not cp.custom_image or not cp.library_id:
        raise HTTPException(status_code=400, detail='No custom image or library entry')
    lib = get_or_404(db, PlantLibrary, cp.library_id)
    src = STATIC_DIR / 'canvas_plant_images' / cp.custom_image
    if not src.exists():
        raise HTTPException(status_code=404, detail='Image file not found')
    ext       = os.path.splitext(cp.custom_image)[1]
    img_bytes = src.read_bytes()
    img_row, _ = save_plant_image(db, lib, img_bytes, 'manual', ext=ext, make_primary=True)
    db.commit()
    return {'ok': True, 'library_image': img_row.filename}


@router.post('/canvas-plants/{cp_id}/delete')
def api_canvas_plant_delete(cp_id: int, db: Session = Depends(get_db)):
    cp = get_or_404(db, CanvasPlant, cp_id)
    if cp.custom_image:
        img_path = STATIC_DIR / 'canvas_plant_images' / cp.custom_image
        if img_path.exists():
            img_path.unlink()
    db.delete(cp)
    db.commit()
    return {'ok': True}
