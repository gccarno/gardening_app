"""
Photo plant/pest/disease identification via a vision LLM (Claude).

POST /api/identify — multipart image + mode:
    identify  What plant is this?
    health    General health assessment
    disease   Disease diagnosis
    pest      Pest identification

Returns structured candidates (with confidence and a PlantLibrary match when
one exists) plus care advice. Requires ANTHROPIC_API_KEY on the server.
"""
import base64
import io
import json
import logging
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db.models import PlantLibrary
from ..db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api', tags=['identify'])

MODES = {
    'identify': (
        'Identify the plant in this photo. List up to 3 candidate species, '
        'most likely first.'
    ),
    'health': (
        'Assess the health of the plant in this photo. Identify the plant if '
        'possible, describe any visible problems (discoloration, wilting, '
        'damage), and rate overall health.'
    ),
    'disease': (
        'Diagnose any disease visible on the plant in this photo. Identify '
        'the most likely disease(s), the plant if possible, and treatment steps.'
    ),
    'pest': (
        'Identify any pest (insect or animal damage) visible in this photo. '
        'Name the most likely pest(s) and how to control them organically '
        'where possible.'
    ),
}

_SYSTEM = (
    'You are an expert botanist and plant pathologist helping a home gardener. '
    'Reply with ONLY a JSON object, no markdown fences, in this shape: '
    '{"candidates": [{"name": "common name", "scientific_name": "Genus species", '
    '"confidence": 0.0-1.0}], "diagnosis": "one-paragraph assessment", '
    '"care_advice": "practical next steps"}. '
    'For disease/pest modes, put the disease or pest name in candidates. '
    'If the image is not a plant, return an empty candidates list and explain '
    'in diagnosis.'
)

_MAX_DIM = 1024  # downscale before sending — plenty for ID, keeps cost tiny


def _prepare_image(raw: bytes) -> tuple[str, str]:
    """Downscale/re-encode to JPEG ≤ _MAX_DIM px; return (base64, media_type)."""
    from PIL import Image
    img = Image.open(io.BytesIO(raw))
    img = img.convert('RGB')
    img.thumbnail((_MAX_DIM, _MAX_DIM))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode(), 'image/jpeg'


def _parse_reply(text: str) -> dict:
    # Tolerate accidental code fences or prose around the JSON object.
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return {'candidates': [], 'diagnosis': text.strip(), 'care_advice': None}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {'candidates': [], 'diagnosis': text.strip(), 'care_advice': None}
    data.setdefault('candidates', [])
    data.setdefault('diagnosis', None)
    data.setdefault('care_advice', None)
    return data


def _match_library(db: Session, candidate: dict) -> dict | None:
    """Find a PlantLibrary entry matching a candidate by scientific or common name."""
    sci = (candidate.get('scientific_name') or '').strip()
    name = (candidate.get('name') or '').strip()
    q = db.query(PlantLibrary)
    entry = None
    if sci:
        entry = q.filter(PlantLibrary.scientific_name.ilike(f'{sci}%')).first()
    if not entry and name:
        entry = (db.query(PlantLibrary)
                 .filter(or_(PlantLibrary.name.ilike(name),
                             PlantLibrary.name.ilike(f'{name}%')))
                 .first())
    if not entry:
        return None
    return {'library_id': entry.id, 'library_name': entry.name,
            'image_filename': entry.image_filename}


@router.post('/identify')
async def api_identify(
    image: UploadFile = File(...),
    mode: str = Form('identify'),
    db: Session = Depends(get_db),
):
    if mode not in MODES:
        raise HTTPException(status_code=400, detail=f'mode must be one of {sorted(MODES)}')

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail='empty image')
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='image too large (max 15 MB)')
    try:
        img_b64, media_type = _prepare_image(raw)
    except Exception:
        raise HTTPException(status_code=400, detail='could not read image file')

    from apps.ml_service.app.llm_provider import complete_vision
    try:
        reply = complete_vision(_SYSTEM, MODES[mode], img_b64, media_type)
    except RuntimeError as exc:          # not configured
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception('[identify] vision call failed')
        raise HTTPException(status_code=502, detail=f'Identification failed: {exc}')

    data = _parse_reply(reply)
    candidates = []
    for c in data['candidates'][:3]:
        entry = {
            'name': c.get('name'),
            'scientific_name': c.get('scientific_name'),
            'confidence': c.get('confidence'),
            'library_match': _match_library(db, c) if mode == 'identify' else None,
        }
        candidates.append(entry)

    return {
        'mode': mode,
        'candidates': candidates,
        'diagnosis': data['diagnosis'],
        'care_advice': data['care_advice'],
    }
