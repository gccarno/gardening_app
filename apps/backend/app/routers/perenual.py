"""
Perenual and Permapeople plant database proxy routes.
"""
import requests as http
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.models import PlantLibrary
from ..db.session import get_db
from ..services.helpers import get_or_404, perenual_get, permapeople_post
from ..services.files import download_and_save_plant_image

router = APIRouter(prefix='/api', tags=['perenual'])


@router.get('/perenual/search')
def api_perenual_search(q: str = '', db: Session = Depends(get_db)):
    if not q.strip():
        return {'results': []}
    data, err_type, err_msg = perenual_get('species-list', {'q': q, 'page': 1})
    if err_type:
        status = 429 if err_type == 'rate_limit' else 502
        raise HTTPException(status_code=status, detail={'error': err_type, 'message': err_msg})
    results = []
    for p in data.get('data', []):
        name = p.get('common_name') or (p.get('scientific_name') or [None])[0]
        if not name or 'Upgrade Plans' in str(name):
            continue
        sunlight = ', '.join(p.get('sunlight') or [])
        if 'Upgrade Plans' in sunlight:
            sunlight = ''
        results.append({
            'perenual_id':     p.get('id'),
            'name':            name,
            'scientific_name': (p.get('scientific_name') or [None])[0],
            'sunlight':        sunlight,
            'watering':        p.get('watering'),
            'cycle':           p.get('cycle'),
            'image':           (p.get('default_image') or {}).get('thumbnail'),
        })
    return {'results': results}


@router.post('/perenual/fetch-image/{entry_id}')
def api_perenual_fetch_image(entry_id: int, db: Session = Depends(get_db)):
    entry = get_or_404(db, PlantLibrary, entry_id)
    if not entry.perenual_id:
        raise HTTPException(status_code=404, detail='No Perenual ID for this plant.')
    if entry.image_filename:
        return {'ok': True, 'filename': entry.image_filename}

    data, err_type, err_msg = perenual_get(f'species/details/{entry.perenual_id}', {})
    if err_type:
        status = 429 if err_type == 'rate_limit' else 502
        raise HTTPException(status_code=status, detail={'error': err_type, 'message': err_msg})

    img = data.get('default_image') or {}
    url = img.get('small_url') or img.get('thumbnail')
    if not url or 'Upgrade Plans' in str(url):
        raise HTTPException(status_code=404, detail='No image available.')
    try:
        img_row, _ = download_and_save_plant_image(db, entry, url, 'perenual')
        db.commit()
    except Exception:
        raise HTTPException(status_code=502, detail='Failed to download image.')
    return {'ok': True, 'filename': img_row.filename}


@router.post('/perenual/save')
def api_perenual_save(body: dict, db: Session = Depends(get_db)):
    if not body or not body.get('name'):
        raise HTTPException(status_code=400, detail='name required')

    existing = db.query(PlantLibrary).filter(
        func.lower(PlantLibrary.name) == body['name'].lower()
    ).first()
    if existing:
        return {'ok': True, 'id': existing.id, 'existing': True}

    water_map = {'minimum': 'Low', 'average': 'Moderate', 'frequent': 'High'}
    water    = water_map.get((body.get('watering') or '').lower())
    sunlight = body.get('sunlight') or None
    if sunlight and 'Upgrade Plans' in sunlight:
        sunlight = None
    perenual_id = body.get('perenual_id') or None

    entry = PlantLibrary(
        name=body['name'],
        scientific_name=body.get('scientific_name') or None,
        perenual_id=perenual_id,
        type=body.get('cycle') or None,
        sunlight=sunlight,
        water=water,
    )
    db.add(entry)
    db.flush()

    if perenual_id and body.get('image'):
        try:
            download_and_save_plant_image(db, entry, body['image'], 'perenual')
        except Exception:
            pass  # image failure is non-fatal

    db.commit()
    return {'ok': True, 'id': entry.id, 'existing': False}


@router.post('/permapeople/search')
def api_permapeople_search(body: dict, db: Session = Depends(get_db)):
    q = (body.get('q') or '').strip()
    if not q:
        return {'results': []}
    data, err_type, err_msg = permapeople_post('search', {'q': q})
    if err_type:
        raise HTTPException(status_code=502, detail={'error': err_type, 'message': err_msg})
    results = []
    for p in data.get('plants', []):
        kv = {item['key']: item['value'] for item in (p.get('data') or []) if 'key' in item}
        results.append({
            'permapeople_id':  p.get('id'),
            'name':            p.get('name'),
            'scientific_name': p.get('scientific_name'),
            'description':     p.get('description'),
            'link':            p.get('link'),
            'water':           kv.get('Water requirement'),
            'sunlight':        kv.get('Light requirement'),
            'zone':            kv.get('USDA Hardiness zone'),
            'family':          kv.get('Family'),
            'layer':           kv.get('Layer'),
        })
    return {'results': results}
