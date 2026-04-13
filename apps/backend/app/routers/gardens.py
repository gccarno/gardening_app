"""
Garden CRUD + garden-scoped API routes: tasks, quick-task, bulk-care, annotations,
background image, dashboard summary, and app settings.
Weather and watering-status live in weather.py.
Canvas-plants live in canvas.py.
"""
import json
import os
from datetime import date, timedelta
from typing import Optional

import requests as http
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db.models import Garden, GardenBed, Plant, Task, BedPlant, AppSetting
from ..db.session import get_db
from ..services.helpers import STATIC_DIR, FROST_DATES, get_or_404, get_season

router = APIRouter(prefix='/api', tags=['gardens'])

_ALLOWED_IMG_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

_PLANTING_HINTS = {
    1:  ('Plan & Order',    'Order seeds and sketch your layout for the coming season.',
         'Onions, celery, peppers — start indoors late month'),
    2:  ('Start Indoors',   'Begin slow-growing crops under lights.',
         'Tomatoes, peppers, eggplant'),
    3:  ('Sow Cool Crops',  'Direct-sow cold-tolerant crops when soil is workable.',
         'Peas, spinach, lettuce, kale, carrots'),
    4:  ('Harden & Plant',  'Harden off starts; transplant cold-hardy crops.',
         'Broccoli, cabbage, onion sets, lettuce'),
    5:  ('Peak Planting',   'Last frost passes for most zones — time for warm-season crops.',
         'Tomatoes, basil, beans, squash, cucumbers'),
    6:  ('Direct Sow',      'Sow warm-season crops; succession-plant salad greens.',
         'Beans, cucumbers, squash, corn, herbs'),
    7:  ('Maintain',        'Harvest regularly; start fall brassica seeds indoors.',
         'Broccoli, kale, chard — start for fall'),
    8:  ('Fall Prep',       'Sow fast-maturing crops for a fall harvest.',
         'Carrots, radishes, arugula, spinach'),
    9:  ('Fall Planting',   'Plant garlic and overwintering crops before first frost.',
         'Garlic, spinach, kale, cover crops'),
    10: ('Wrap Up',         'Plant spring bulbs and cover crops to protect soil.',
         'Garlic, cover crops, spring bulbs'),
    11: ('Rest & Compost',  'Mulch beds, add compost, and plan for next year.',
         'Cover crops, soil amendments'),
    12: ('Plan Ahead',      'Review the season and browse seed catalogs.',
         'Start planning and ordering seeds'),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_frost_date(mm_dd: str, year: int) -> date | None:
    """Convert 'MM/DD' string to a date object for the given year."""
    try:
        m, d = mm_dd.split('/')
        return date(year, int(m), int(d))
    except Exception:
        return None


def _apply_frost(garden: Garden, zip_code: str) -> None:
    """Fetch NOAA frost dates from apis.joelgrant.dev and apply to garden."""
    try:
        r = http.get(f'https://apis.joelgrant.dev/api/v1/frost/{zip_code}', timeout=8)
        r.raise_for_status()
        data = r.json().get('data', {})
    except Exception:
        return

    garden.frost_free = data.get('frost_free', False)

    station = data.get('weather_station', {})
    garden.frost_station_id          = station.get('station_id')
    garden.frost_station_name        = station.get('name')
    garden.frost_station_distance_km = station.get('distance_km')

    frost_dates = data.get('frost_dates', {})
    last_frost_probs  = frost_dates.get('last_frost_32f', {})   # spring: last frost
    first_frost_probs = frost_dates.get('first_frost_32f', {})  # fall: first frost

    if last_frost_probs:
        garden.last_frost_dates_json = json.dumps(last_frost_probs)
        fifty = last_frost_probs.get('50%')
        if fifty:
            garden.last_frost_date = _parse_frost_date(fifty, date.today().year)

    if first_frost_probs:
        garden.first_frost_dates_json = json.dumps(first_frost_probs)
        fifty = first_frost_probs.get('50%')
        if fifty:
            garden.first_frost_date = _parse_frost_date(fifty, date.today().year)


def _apply_zip(garden: Garden, zip_code: str) -> None:
    """Fetch USDA zone + city/state for a ZIP code and apply to garden."""
    zip_code = zip_code.strip()
    if not zip_code:
        return
    try:
        z = http.get(f'https://phzmapi.org/{zip_code}.json', timeout=6)
        z.raise_for_status()
        zdata = z.json()
        garden.usda_zone       = zdata.get('zone')
        garden.zone_temp_range = zdata.get('temperature_range')
        coords = zdata.get('coordinates', {})
        garden.latitude  = float(coords.get('lat', 0)) or None
        garden.longitude = float(coords.get('lon', 0)) or None
    except Exception:
        pass
    try:
        p = http.get(f'http://api.zippopotam.us/us/{zip_code}', timeout=6)
        p.raise_for_status()
        pdata = p.json()
        place = (pdata.get('places') or [{}])[0]
        garden.city  = place.get('place name')
        garden.state = place.get('state abbreviation')
        if not garden.latitude:
            garden.latitude  = float(place.get('latitude',  0)) or None
            garden.longitude = float(place.get('longitude', 0)) or None
    except Exception:
        pass
    garden.zip_code = zip_code
    _apply_frost(garden, zip_code)


def _serialize_garden(g: Garden) -> dict:
    return {
        'id':                          g.id,
        'name':                        g.name,
        'description':                 g.description,
        'unit':                        g.unit,
        'zip_code':                    g.zip_code,
        'city':                        g.city,
        'state':                       g.state,
        'latitude':                    g.latitude,
        'longitude':                   g.longitude,
        'usda_zone':                   g.usda_zone,
        'zone_temp_range':             g.zone_temp_range,
        'last_frost_date':             g.last_frost_date.isoformat() if g.last_frost_date else None,
        'first_frost_date':            g.first_frost_date.isoformat() if g.first_frost_date else None,
        'frost_free':                  g.frost_free,
        'frost_station_id':            g.frost_station_id,
        'frost_station_name':          g.frost_station_name,
        'frost_station_distance_km':   g.frost_station_distance_km,
        'last_frost_dates':            json.loads(g.last_frost_dates_json) if g.last_frost_dates_json else None,
        'first_frost_dates':           json.loads(g.first_frost_dates_json) if g.first_frost_dates_json else None,
        'watering_frequency_days':     g.watering_frequency_days,
        'water_source':                g.water_source,
        'background_image':            g.background_image,
    }


# ── Garden CRUD ───────────────────────────────────────────────────────────────

@router.get('/gardens')
def api_gardens_list(db: Session = Depends(get_db)):
    gardens = db.query(Garden).order_by(Garden.name).all()
    return [_serialize_garden(g) for g in gardens]


@router.post('/gardens')
def api_gardens_create(body: dict, db: Session = Depends(get_db)):
    garden = Garden(
        name=body['name'],
        description=body.get('description'),
        unit=body.get('unit', 'ft'),
    )
    db.add(garden)
    db.flush()
    zip_code = (body.get('zip_code') or '').strip()
    if zip_code:
        _apply_zip(garden, zip_code)
    db.commit()
    return _serialize_garden(garden)


@router.get('/gardens/{garden_id}')
def api_garden_detail(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    return _serialize_garden(garden)


@router.put('/gardens/{garden_id}')
def api_garden_update(garden_id: int, body: dict, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    if 'name'                    in body: garden.name                    = body['name']
    if 'description'             in body: garden.description             = body.get('description')
    if 'unit'                    in body: garden.unit                    = body.get('unit', 'ft')
    if 'watering_frequency_days' in body: garden.watering_frequency_days = body.get('watering_frequency_days') or 7
    if 'water_source'            in body: garden.water_source            = body.get('water_source') or None
    if 'last_frost_date' in body:
        f = body.get('last_frost_date')
        garden.last_frost_date = date.fromisoformat(f) if f else None
    if 'first_frost_date' in body:
        f = body.get('first_frost_date')
        garden.first_frost_date = date.fromisoformat(f) if f else None
    zip_code = (body.get('zip_code') or '').strip()
    if zip_code and zip_code != garden.zip_code:
        _apply_zip(garden, zip_code)
    db.commit()
    return _serialize_garden(garden)


@router.delete('/gardens/{garden_id}')
def api_garden_delete(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    db.delete(garden)
    db.commit()
    return {'ok': True}


# ── App settings ──────────────────────────────────────────────────────────────

@router.get('/settings/default-garden')
def api_get_default_garden(db: Session = Depends(get_db)):
    setting = db.get(AppSetting, 'default_garden_id')
    gid = int(setting.value) if setting and setting.value else None
    return {'garden_id': gid}


@router.post('/settings/default-garden')
def api_set_default_garden(body: dict, db: Session = Depends(get_db)):
    gid = body.get('garden_id')
    setting = db.get(AppSetting, 'default_garden_id')
    if setting is None:
        setting = AppSetting(key='default_garden_id', value=str(gid) if gid else None)
        db.add(setting)
    else:
        setting.value = str(gid) if gid else None
    db.commit()
    return {'ok': True, 'garden_id': gid}


# ── Dashboard summary ─────────────────────────────────────────────────────────

@router.get('/dashboard')
def api_dashboard(garden_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Return all data needed to render the dashboard for the given garden."""
    garden = db.get(Garden, garden_id) if garden_id else None
    today = date.today()

    q_beds   = db.query(GardenBed)
    q_plants = db.query(Plant)
    q_tasks  = db.query(Task).filter(Task.completed == False)
    if garden:
        q_beds   = q_beds.filter(GardenBed.garden_id == garden_id)
        q_plants = q_plants.filter(Plant.garden_id == garden_id)
        q_tasks  = q_tasks.filter(Task.garden_id == garden_id)

    metrics = {
        'bed_count':     q_beds.count(),
        'plant_count':   q_plants.count(),
        'plants_active': q_plants.filter(Plant.status == 'active').count(),
        'task_count':    q_tasks.count(),
        'overdue_tasks': q_tasks.filter(Task.due_date < today).count(),
    }

    upcoming_tasks = (q_tasks
                      .order_by(Task.due_date.asc().nullslast())
                      .limit(5).all())

    recent_plants = q_plants.order_by(Plant.id.desc()).limit(5).all()

    activity_cutoff = today - timedelta(days=14)
    q_done = db.query(Task).filter(
        Task.completed == True,
        Task.completed_date >= activity_cutoff,
    )
    if garden:
        q_done = q_done.filter(Task.garden_id == garden_id)
    recent_activity = q_done.order_by(Task.completed_date.desc()).limit(8).all()

    season, season_icon = get_season(today)
    hint_action, hint_text, hint_crops = _PLANTING_HINTS[today.month]

    frost_context = None
    if garden and garden.last_frost_date:
        days = (garden.last_frost_date - today).days
        if days > 0:
            frost_context = f'Last frost in {days} day{"s" if days != 1 else ""} ({garden.last_frost_date.strftime("%b %d")})'
        elif days >= -30:
            frost_context = f'Last frost passed {-days} day{"s" if days != -1 else ""} ago'

    return {
        'metrics': metrics,
        'upcoming_tasks': [{
            'id':        t.id,
            'title':     t.title,
            'task_type': t.task_type,
            'due_date':  t.due_date.isoformat() if t.due_date else None,
            'plant_name': t.plant.name if t.plant else None,
        } for t in upcoming_tasks],
        'recent_plants': [{
            'id':     p.id,
            'name':   p.name,
            'type':   p.type,
            'status': p.status,
        } for p in recent_plants],
        'recent_activity': [{
            'id':             t.id,
            'title':          t.title,
            'completed_date': t.completed_date.strftime('%b %d') if t.completed_date else None,
        } for t in recent_activity],
        'season':       season,
        'season_icon':  season_icon,
        'hint_action':  hint_action,
        'hint_text':    hint_text,
        'hint_crops':   hint_crops,
        'frost_context': frost_context,
    }


# ── Tasks for a garden ────────────────────────────────────────────────────────

@router.get('/gardens/{garden_id}/tasks')
def api_garden_tasks(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    plant_ids = [p.id for p in garden.plants]
    bed_ids   = [b.id for b in garden.beds]
    tasks = (db.query(Task)
             .filter(
                 or_(
                     Task.plant_id.in_(plant_ids),
                     Task.garden_id == garden_id,
                     Task.bed_id.in_(bed_ids),
                 ),
                 Task.completed == False,
             )
             .order_by(Task.due_date)
             .limit(20).all())
    return [{
        'id':        t.id,
        'title':     t.title,
        'task_type': t.task_type,
        'due_date':  t.due_date.isoformat() if t.due_date else None,
        'plant_name': t.plant.name if t.plant else None,
        'scope': 'plant' if t.plant_id else ('bed' if t.bed_id else 'garden'),
    } for t in tasks]


# ── Quick task creation ───────────────────────────────────────────────────────

@router.post('/gardens/{garden_id}/quick-task')
def api_quick_task(garden_id: int, body: dict, db: Session = Depends(get_db)):
    garden    = get_or_404(db, Garden, garden_id)
    task_type = body.get('task_type', 'other')
    plant_id  = body.get('plant_id')
    bed_id    = body.get('bed_id')
    title     = body.get('title')
    description = body.get('description')
    due_date_override = body.get('due_date')
    due_date = None

    plant = db.get(Plant, plant_id) if plant_id else None
    lib   = plant.library_entry if plant else None

    # Resolve frost date
    frost = garden.last_frost_date
    if not frost and garden.usda_zone:
        zone_num = ''.join(filter(str.isdigit, garden.usda_zone or ''))
        spring_str, _ = FROST_DATES.get(zone_num, (None, None))
        if spring_str and spring_str not in ('none', 'rare', 'unknown'):
            from datetime import datetime
            try:
                frost = datetime.strptime(f'{spring_str} {date.today().year}', '%b %d %Y').date()
            except ValueError:
                frost = None

    # Auto-calculate due date
    if task_type == 'seeding' and lib and lib.sow_indoor_weeks and frost:
        due_date = frost - timedelta(weeks=lib.sow_indoor_weeks)
    elif task_type == 'transplanting' and lib and lib.transplant_offset and frost:
        due_date = frost + timedelta(weeks=lib.transplant_offset)
    elif task_type == 'harvest':
        if plant and plant.planted_date and lib and lib.days_to_harvest:
            due_date = plant.planted_date + timedelta(days=lib.days_to_harvest)
        elif plant and plant.expected_harvest:
            due_date = plant.expected_harvest

    if due_date_override:
        try:
            due_date = date.fromisoformat(due_date_override)
        except ValueError:
            pass

    # Auto-title
    if not title:
        plant_name = plant.name if plant else ''
        type_labels = {
            'seeding':      f'Seed {plant_name}'.strip(),
            'transplanting': f'Transplant {plant_name}'.strip(),
            'harvest':      f'Harvest {plant_name}'.strip(),
            'watering':     f'Water {plant_name or garden.name}'.strip(),
            'fertilizing':  f'Fertilize {plant_name or garden.name}'.strip(),
            'mulching':     f'Mulch {plant_name or garden.name}'.strip(),
            'weeding':      f'Weed {garden.name}',
            'pruning':      f'Prune {plant_name or garden.name}'.strip(),
        }
        title = type_labels.get(task_type, 'Task')

    task = Task(
        title=title,
        description=description,
        task_type=task_type,
        due_date=due_date,
        plant_id=plant_id,
        garden_id=garden_id,
        bed_id=bed_id,
    )
    db.add(task)
    db.commit()
    return {'ok': True, 'task_id': task.id,
            'due_date': due_date.isoformat() if due_date else None}


# ── Bulk care ─────────────────────────────────────────────────────────────────

@router.post('/gardens/{garden_id}/bulk-care')
def api_bulk_care(garden_id: int, body: dict, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    action = body.get('action')
    if action not in ('water', 'fertilize', 'mulch'):
        raise HTTPException(status_code=400, detail='Invalid action')
    care_date_str = body.get('date')
    care_date = date.fromisoformat(care_date_str) if care_date_str else date.today()
    create_task = body.get('create_task', True)

    bed_ids = [b.id for b in garden.beds]
    bps = db.query(BedPlant).filter(BedPlant.bed_id.in_(bed_ids)).all() if bed_ids else []
    field_map = {'water': 'last_watered', 'fertilize': 'last_fertilized'}

    if action in field_map:
        for bp in bps:
            setattr(bp, field_map[action], care_date)

    if create_task:
        type_map = {'water': 'watering', 'fertilize': 'fertilizing', 'mulch': 'mulching'}
        task = Task(
            title=f'{action.capitalize()} all plants — {garden.name}',
            task_type=type_map[action],
            garden_id=garden_id,
            due_date=care_date,
            completed=True,
            completed_date=care_date,
        )
        db.add(task)

    db.commit()
    return {'ok': True, 'updated': len(bps)}


# ── Annotations ───────────────────────────────────────────────────────────────

@router.get('/gardens/{garden_id}/annotations')
def api_get_annotations(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    shapes = json.loads(garden.annotations or '[]')
    return {'shapes': shapes}


@router.post('/gardens/{garden_id}/annotations')
def api_save_annotations(garden_id: int, body: dict, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    garden.annotations = json.dumps(body.get('shapes', []))
    db.commit()
    return {'ok': True}


# ── Garden background image ───────────────────────────────────────────────────

@router.post('/gardens/{garden_id}/upload-background')
async def upload_garden_background(
    garden_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    garden = get_or_404(db, Garden, garden_id)
    ext = os.path.splitext(image.filename or '')[1].lower()
    if ext not in _ALLOWED_IMG_EXTS:
        raise HTTPException(status_code=400, detail='Unsupported file type')

    bg_dir = STATIC_DIR / 'garden_backgrounds'
    bg_dir.mkdir(parents=True, exist_ok=True)

    if garden.background_image:
        old_path = bg_dir / garden.background_image
        if old_path.exists():
            old_path.unlink()

    filename = f'garden_{garden_id}{ext}'
    dest = bg_dir / filename
    contents = await image.read()
    dest.write_bytes(contents)

    garden.background_image = filename
    db.commit()
    return {'filename': filename, 'url': f'/static/garden_backgrounds/{filename}'}


@router.post('/gardens/{garden_id}/remove-background')
def remove_garden_background(garden_id: int, db: Session = Depends(get_db)):
    garden = get_or_404(db, Garden, garden_id)
    if garden.background_image:
        bg_dir = STATIC_DIR / 'garden_backgrounds'
        old_path = bg_dir / garden.background_image
        if old_path.exists():
            old_path.unlink()
        garden.background_image = None
        db.commit()
    return {'ok': True}
