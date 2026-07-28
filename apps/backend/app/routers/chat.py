"""
AI chat assistant and plant recommendations routes.
"""
import uuid
from datetime import date
from typing import Optional

import sentry_sdk
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, load_only

from ..db.models import Garden, Plant, PlantLibrary, PlantLibraryImage
from ..db.session import get_db
from ..services.helpers import FROST_DATES, get_season

router = APIRouter(prefix='/api', tags=['chat'])

# Only the columns the scorer reads. Hydrating whole PlantLibrary rows pulled
# every Trefle blob, FAQ and nutrition JSON for ~9,999 plants into memory on
# each request, which walked the free instance from 181 MB to its 536 MB limit.
_SCORING_COLUMNS = (
    PlantLibrary.id, PlantLibrary.name, PlantLibrary.type,
    PlantLibrary.min_zone, PlantLibrary.max_zone, PlantLibrary.sunlight,
    PlantLibrary.soil_ph_min, PlantLibrary.soil_ph_max,
    PlantLibrary.good_neighbors, PlantLibrary.difficulty,
    PlantLibrary.days_to_harvest, PlantLibrary.fruit_months,
    PlantLibrary.bloom_months, PlantLibrary.growth_months,
    PlantLibrary.image_filename,
)


def _scoring_candidates(db: Session):
    """Every library row, but only the columns the recommender scores on."""
    return (db.query(PlantLibrary)
            .options(load_only(*_SCORING_COLUMNS))
            .order_by(PlantLibrary.name)
            .all())


def _primary_image_filenames(db: Session, plant_library_ids: list) -> dict:
    """{plant_library_id: filename} for the given ids, in one query.

    Mirrors what reading `entry.images` used to do: the primary image when
    there is one, otherwise the earliest by created_at (the relationship's
    own order_by).
    """
    if not plant_library_ids:
        return {}
    rows = (db.query(PlantLibraryImage)
            .filter(PlantLibraryImage.plant_library_id.in_(plant_library_ids))
            .order_by(PlantLibraryImage.is_primary.desc(),
                      PlantLibraryImage.created_at)
            .all())
    filenames: dict = {}
    for img in rows:
        filenames.setdefault(img.plant_library_id, img.filename)
    return filenames


@router.post('/chat')
def api_chat(body: dict, db: Session = Depends(get_db)):
    from apps.ml_service.app.recommender import recommend
    from apps.ml_service.app.chat_tools import run_agentic_loop

    user_msg             = (body.get('message') or '').strip()
    garden_id            = body.get('garden_id')
    conversation_history = body.get('conversation_history') or []
    session_id           = body.get('session_id') or str(uuid.uuid4())

    if not user_msg:
        return {'reply': 'Please type a message first.',
                'conversation_history': [], 'session_id': session_id}

    garden = db.get(Garden, garden_id) if garden_id else None
    today  = date.today()
    season, _ = get_season(today)

    zone_str     = (garden.usda_zone or 'unknown') if garden else 'unknown'
    zone_num_str = ''.join(c for c in zone_str if c.isdigit())
    zone_int     = int(zone_num_str) if zone_num_str else None
    garden_name  = garden.name if garden else 'your garden'

    current_plants: list[str] = []
    if garden:
        from sqlalchemy.orm import joinedload
        plants = (db.query(Plant)
                  .options(joinedload(Plant.library_entry))
                  .filter(Plant.garden_id == garden.id)
                  .all())
        for p in plants:
            current_plants.append(p.library_entry.name if p.library_entry else p.name)

    # Top 3 recommendations for assistant context
    rec_names: list[str] = []
    try:
        phs    = [b.soil_ph for b in garden.beds if b.soil_ph] if garden else []
        avg_ph = sum(phs) / len(phs) if phs else None
        existing = set(current_plants)
        plants_data = [
            {
                'id': p.id, 'name': p.name, 'type': p.type,
                'min_zone': p.min_zone, 'max_zone': p.max_zone,
                'sunlight': p.sunlight,
                'soil_ph_min': p.soil_ph_min, 'soil_ph_max': p.soil_ph_max,
                'good_neighbors': p.good_neighbors, 'difficulty': p.difficulty,
                'days_to_harvest': p.days_to_harvest,
                'fruit_months': p.fruit_months,
                'bloom_months': p.bloom_months,
                'growth_months': p.growth_months,
            }
            for p in _scoring_candidates(db)
            if p.name not in existing
        ]
        ctx = {
            'zone': zone_int, 'sunlight_hours': 6,
            'current_month': today.month, 'soil_ph': avg_ph,
            'preferred_types': ['vegetable', 'herb'],
            'current_plant_names': current_plants,
        }
        recs = recommend(plants_data, ctx, top_n=3)
        rec_names = [r['name'] for r in recs]
    except Exception:
        pass

    system_prompt = (
        f"You are a knowledgeable, friendly garden assistant helping a home gardener. "
        f"Today is {today.strftime('%B %d, %Y')} — {season} in the Northern Hemisphere.\n\n"
        f"Garden: {garden_name}\n"
        f"USDA Hardiness Zone: {zone_str}\n"
        f"Current plants: {', '.join(current_plants) if current_plants else 'none yet'}\n"
        f"Top recommendations right now: {', '.join(rec_names) if rec_names else 'see library'}\n\n"
        "Give practical, concise advice tailored to this specific garden and zone. "
        "Use the available tools to look up real data before answering when relevant. "
        "If asked what to plant, prioritise the recommended plants above. "
        "Keep responses under 200 words unless the question genuinely needs more detail."
    )

    messages = list(conversation_history) + [{'role': 'user', 'content': user_msg}]

    # The generic handler below deliberately swallows the exception to return a
    # friendly reply, so nothing would reach Sentry on its own — capture there
    # explicitly.
    try:
        reply = run_agentic_loop(system_prompt, messages, garden, db)
        return {'reply': reply, 'conversation_history': messages, 'session_id': session_id}
    except RuntimeError as exc:
        # Missing API key — production deliberately runs without ANTHROPIC_API_KEY,
        # so this is the configured behaviour, not a fault. Reporting it opened a
        # Sentry issue on every probe of /api/chat. The reply is unchanged.
        return {'reply': str(exc), 'conversation_history': messages, 'session_id': session_id}
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        return {'reply': f'Sorry, the assistant ran into an error: {exc}',
                'conversation_history': messages, 'session_id': session_id}


@router.post('/chat/restart-model')
def restart_model():
    """
    For Ollama: unload the model then reload it so it is ready for the next chat.
    For other providers: verify the API key / connectivity and return a status.
    """
    from ..services.helpers import REPO_ROOT  # noqa: F401 — ensure env loaded
    from apps.ml_service.app.llm_provider import PROVIDER, _model, _DEFAULTS

    if PROVIDER == 'ollama':
        import os
        import requests as _req
        base = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        model = _model('ollama')

        # Unload (keep_alive=0) then immediately reload (keep_alive=-1 = keep forever)
        def _chat(keep_alive):
            return _req.post(
                f'{base}/api/generate',
                json={'model': model, 'prompt': '', 'keep_alive': keep_alive},
                timeout=60,
            )

        try:
            _chat(0)   # unload
        except Exception:
            pass  # ignore if not loaded yet

        try:
            r = _chat(-1)  # reload
            r.raise_for_status()
            return {'ok': True, 'provider': PROVIDER, 'model': model}
        except Exception as exc:
            return {'ok': False, 'provider': PROVIDER, 'model': model, 'error': str(exc)}

    elif PROVIDER == 'anthropic':
        import os
        key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            return {'ok': False, 'provider': PROVIDER, 'error': 'ANTHROPIC_API_KEY not set'}
        return {'ok': True, 'provider': PROVIDER, 'model': _model('anthropic')}

    elif PROVIDER == 'openai':
        import os
        key = os.environ.get('OPENAI_API_KEY', '')
        if not key:
            return {'ok': False, 'provider': PROVIDER, 'error': 'OPENAI_API_KEY not set'}
        return {'ok': True, 'provider': PROVIDER, 'model': _model('openai')}

    else:
        return {'ok': True, 'provider': PROVIDER, 'model': _model(PROVIDER)}


@router.get('/recommendations')
def api_recommendations(
    garden_id: Optional[int] = None,
    top_n: int = 5,
    db: Session = Depends(get_db),
):
    from apps.ml_service.app.recommender import recommend

    garden = db.get(Garden, garden_id) if garden_id else None

    zone_str     = (garden.usda_zone or '') if garden else ''
    zone_num_str = ''.join(c for c in zone_str if c.isdigit())
    zone_int     = int(zone_num_str) if zone_num_str else None

    phs    = [b.soil_ph for b in garden.beds if b.soil_ph] if garden else []
    avg_ph = sum(phs) / len(phs) if phs else None

    current_plant_names: list[str] = []
    if garden:
        from sqlalchemy.orm import joinedload
        garden_plants = (db.query(Plant)
                         .options(joinedload(Plant.library_entry))
                         .filter(Plant.garden_id == garden.id)
                         .all())
        for p in garden_plants:
            if p.library_entry:
                current_plant_names.append(p.library_entry.name)

    context = {
        'zone':                zone_int,
        'sunlight_hours':      6,
        'current_month':       date.today().month,
        'soil_ph':             avg_ph,
        'preferred_types':     ['vegetable', 'herb'],
        'current_plant_names': current_plant_names,
    }

    existing_names = set(current_plant_names)
    plants_data = [
        {
            'id':              p.id,
            'name':            p.name,
            'type':            p.type,
            'min_zone':        p.min_zone,
            'max_zone':        p.max_zone,
            'sunlight':        p.sunlight,
            'soil_ph_min':     p.soil_ph_min,
            'soil_ph_max':     p.soil_ph_max,
            'good_neighbors':  p.good_neighbors,
            'difficulty':      p.difficulty,
            'days_to_harvest': p.days_to_harvest,
            'fruit_months':    p.fruit_months,
            'bloom_months':    p.bloom_months,
            'growth_months':   p.growth_months,
            # Fallback only; the image table wins below when it has a row.
            'image_filename':  p.image_filename,
        }
        for p in _scoring_candidates(db)
        if p.name not in existing_names
    ]

    results = recommend(plants_data, context, top_n)

    # Resolve images for the handful that scored, not for all ~9,999 candidates.
    # Reading p.images inside the loop above was an N+1: one query per library
    # row against a remote Neon, ~10,000 round trips for a five-item response.
    images = _primary_image_filenames(db, [r['plant_id'] for r in results])
    for rec in results:
        fn = images.get(rec['plant_id']) or rec.get('image_filename')
        rec['image_filename'] = fn
        rec['image_url'] = f'/static/plant_images/{fn}' if fn else None

    return {'recommendations': results,
            'context': {'zone': zone_int, 'month': context['current_month']}}
