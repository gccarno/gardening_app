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
from pydantic import BaseModel
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ..db.models import PlantLibrary
from ..db.session import get_db
from ..services.errors import NotConfiguredError

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
        # Same 503 as before; NotConfiguredError only keeps it out of Sentry.
        raise NotConfiguredError(status_code=503, detail=str(exc))
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


# ── On-device identification ─────────────────────────────────────────────────
# The client runs the ONNX image tower (ml/models/plantid_<version>.onnx) and
# posts the embedding; ranking it is one SQL scan, so this stays cheap on the
# free tier. Clients fall back to POST /api/identify (Claude) on a 409 or when
# `confident` is false.

_MAX_TOP_K = 10


class EmbeddingQuery(BaseModel):
    embedding: list[float]
    model_version: str
    top_k: int = 3


def _prototype_scores(db: Session, embedding: list[float], version: str, k: int,
                      temperature: float) -> tuple[list[tuple], float, float]:
    """Return (top-k rows, max similarity, softmax normaliser over all species).

    Rows are (species_key, scientific_name, similarity, plant_library_id).
    Postgres/pgvector only — stubbed in unit tests.
    """
    q = '[' + ','.join(f'{x:.7g}' for x in embedding) + ']'
    sims = """
        SELECT species_key, scientific_name, plant_library_id,
               1 - (embedding <=> CAST(:q AS vector)) AS sim
        FROM plant_image_prototype WHERE model_version = :v
    """
    top = db.execute(text(f'{sims} ORDER BY sim DESC LIMIT :k'),
                     {'q': q, 'v': version, 'k': k}).all()
    if not top:
        return [], 0.0, 1.0
    max_sim = float(top[0].sim)
    sum_exp = db.execute(text(f'SELECT sum(exp((sim - :m) / :t)) FROM ({sims}) s'),
                         {'q': q, 'v': version, 'm': max_sim, 't': temperature}).scalar()
    return ([(r.species_key, r.scientific_name, float(r.sim), r.plant_library_id) for r in top],
            max_sim, float(sum_exp))


@router.post('/identify/embedding')
def api_identify_embedding(body: EmbeddingQuery, db: Session = Depends(get_db)):
    from apps.ml_service.app.plantid import load_config, probabilities

    config = load_config(body.model_version)
    if config is None:
        raise HTTPException(status_code=409, detail=f'unknown model_version {body.model_version!r}')
    if len(body.embedding) != config['embed_dim']:
        raise HTTPException(status_code=400,
                            detail=f'embedding must have {config["embed_dim"]} values')

    k = max(1, min(body.top_k, _MAX_TOP_K))
    top, max_sim, sum_exp = _prototype_scores(db, body.embedding, body.model_version, k,
                                              config['temperature'])
    if not top:
        raise HTTPException(status_code=409,
                            detail=f'no prototypes loaded for {body.model_version!r}')

    probs = probabilities([sim for _, _, sim, _ in top], max_sim, sum_exp, config['temperature'])
    lib_ids = [lib_id for *_, lib_id in top if lib_id is not None]
    entries = {p.id: p for p in db.query(PlantLibrary).filter(PlantLibrary.id.in_(lib_ids))}
    candidates = []
    for (_, sci, _, lib_id), p in zip(top, probs):
        entry = entries.get(lib_id)
        candidates.append({
            'name': entry.name if entry else sci,
            'scientific_name': sci,
            'confidence': round(p, 4),
            'library_match': ({'library_id': entry.id, 'library_name': entry.name,
                               'image_filename': entry.image_filename} if entry else None),
        })

    return {
        'mode': 'identify',
        'candidates': candidates,
        'diagnosis': None,
        'care_advice': None,
        'source': 'local',
        'confident': config['tau'] is not None and probs[0] >= config['tau'],
        'model_version': body.model_version,
    }


@router.get('/identify/model')
def api_identify_model():
    """Config of the plant-ID model clients should download (404 if none deployed)."""
    from apps.ml_service.app.plantid import current_version, public_config
    version = current_version()
    if version is None:
        raise HTTPException(status_code=404, detail='no plant-ID model deployed')
    return public_config(version)


@router.get('/identify/model/{model_version}.onnx')
def api_identify_model_file(model_version: str):
    from fastapi.responses import FileResponse
    from apps.ml_service.app.plantid import model_path
    path = model_path(model_version)
    if path is None:
        raise HTTPException(status_code=404, detail=f'unknown model_version {model_version!r}')
    # The version is in the URL, so the bytes behind it never change.
    return FileResponse(path, media_type='application/octet-stream',
                        headers={'Cache-Control': 'public, max-age=31536000, immutable'})
