"""
AI chat assistant and plant recommendations routes.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.models import Garden, Plant, PlantLibrary
from ..db.session import get_db
from ..services.helpers import FROST_DATES, REPO_ROOT, get_season

router = APIRouter(prefix='/api', tags=['chat'])


@router.post('/chat')
def api_chat(body: dict, db: Session = Depends(get_db)):
    from apps.ml_service.app.recommender import recommend
    from apps.ml_service.app.chat_tools import run_agentic_loop
    from apps.ml_service.app.chat_logger import (
        create_session_logger, log_event, close_session_logger,
    )

    user_msg             = (body.get('message') or '').strip()
    garden_id            = body.get('garden_id')
    conversation_history = body.get('conversation_history') or []
    session_id           = body.get('session_id') or str(uuid.uuid4())
    logs_root            = str(REPO_ROOT / 'logs')

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
        for p in garden.plants:
            current_plants.append(p.library_entry.name if p.library_entry else p.name)

    # Top 3 recommendations for assistant context
    rec_names: list[str] = []
    try:
        phs    = [b.soil_ph for b in garden.beds if b.soil_ph] if garden else []
        avg_ph = sum(phs) / len(phs) if phs else None
        existing = set(current_plants)
        plants_data = []
        for p in db.query(PlantLibrary).all():
            if p.name in existing:
                continue
            plants_data.append({
                'id': p.id, 'name': p.name, 'type': p.type,
                'min_zone': p.min_zone, 'max_zone': p.max_zone,
                'sunlight': p.sunlight,
                'soil_ph_min': p.soil_ph_min, 'soil_ph_max': p.soil_ph_max,
                'good_neighbors': p.good_neighbors, 'difficulty': p.difficulty,
                'days_to_harvest': p.days_to_harvest,
                'fruit_months': p.fruit_months,
                'bloom_months': p.bloom_months,
                'growth_months': p.growth_months,
            })
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

    _session_logger = create_session_logger(session_id, logs_root)
    try:
        log_event(_session_logger, 'session_start',
                  session_id=session_id, garden_id=garden_id,
                  garden_name=garden_name, user_message=user_msg,
                  history_length=len(conversation_history))
        reply = run_agentic_loop(system_prompt, messages, garden, db,
                                 session_logger=_session_logger)
        log_event(_session_logger, 'session_end',
                  session_id=session_id, final_reply_length=len(reply))
        return {'reply': reply, 'conversation_history': messages, 'session_id': session_id}
    except RuntimeError as exc:
        log_event(_session_logger, 'error', error=str(exc))
        return {'reply': str(exc), 'conversation_history': messages, 'session_id': session_id}
    except Exception as exc:
        log_event(_session_logger, 'error', error=str(exc))
        return {'reply': f'Sorry, the assistant ran into an error: {exc}',
                'conversation_history': messages, 'session_id': session_id}
    finally:
        close_session_logger(_session_logger)


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
        for p in garden.plants:
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
    plants_data = []
    for p in db.query(PlantLibrary).order_by(PlantLibrary.name).all():
        if p.name in existing_names:
            continue
        primary_img = next((img for img in p.images if img.is_primary), None)
        if not primary_img and p.images:
            primary_img = p.images[0]
        plants_data.append({
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
            'image_filename':  primary_img.filename if primary_img else p.image_filename,
        })

    results = recommend(plants_data, context, top_n)
    for rec in results:
        fn = rec.get('image_filename')
        rec['image_url'] = f'/static/plant_images/{fn}' if fn else None

    return {'recommendations': results,
            'context': {'zone': zone_int, 'month': context['current_month']}}
