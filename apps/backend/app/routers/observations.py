"""
Plant observation and health score routes.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import BedPlant, PlantObservation, OBSERVATION_TYPES, User
from ..db.session import get_db
from ..services.auth import get_current_user, require_resource
from ..services.helpers import get_or_404

router = APIRouter(prefix='/api', tags=['observations'])

# Positive types don't penalize health score; negative types do.
_NEGATIVE = {'yellowing', 'wilting', 'pest_damage', 'disease'}
_POSITIVE  = {'healthy', 'new_growth', 'flowering', 'harvest_ready'}


def _serialize(o: PlantObservation) -> dict:
    return {
        'id':               o.id,
        'bed_plant_id':     o.bed_plant_id,
        'observation_date': o.observation_date.isoformat(),
        'observation_type': o.observation_type,
        'severity':         o.severity,
        'notes':            o.notes,
        'image_filename':   o.image_filename,
    }


def compute_health_score(observations: list[PlantObservation]) -> int:
    """Return 0–100 health score from observations in last 30 days."""
    cutoff = date.today() - timedelta(days=30)
    recent = [o for o in observations if o.observation_date >= cutoff]
    if not recent:
        return 75  # default neutral score

    total_weight = 0.0
    weighted_sum = 0.0
    for o in recent:
        age_days = (date.today() - o.observation_date).days
        weight = max(0.1, 1.0 - age_days / 30.0)  # newer = heavier
        total_weight += weight

        if o.observation_type in _NEGATIVE:
            # Severity 1 = -10 pts, severity 5 = -50 pts
            contribution = 100.0 - (o.severity * 10.0)
        else:
            # Positive observations add to score
            contribution = 80.0 + (o.severity * 4.0)

        weighted_sum += weight * contribution

    raw = weighted_sum / total_weight if total_weight else 75.0
    return max(0, min(100, round(raw)))


class ObservationCreate(BaseModel):
    observation_date: Optional[str] = None  # YYYY-MM-DD; defaults to today
    observation_type: str
    severity: Optional[int] = 3
    notes: Optional[str] = None


@router.get('/bedplants/{bp_id}/observations')
def api_list_observations(bp_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_resource(db, user, BedPlant, bp_id, 'viewer')
    obs = (db.query(PlantObservation)
           .filter(PlantObservation.bed_plant_id == bp_id)
           .order_by(PlantObservation.observation_date.desc())
           .all())
    return [_serialize(o) for o in obs]


@router.post('/bedplants/{bp_id}/observations')
def api_create_observation(bp_id: int, body: ObservationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_resource(db, user, BedPlant, bp_id, 'editor')
    if body.observation_type not in OBSERVATION_TYPES:
        raise HTTPException(status_code=400, detail=f'observation_type must be one of {OBSERVATION_TYPES}')
    severity = max(1, min(5, body.severity or 3))
    obs = PlantObservation(
        bed_plant_id=bp_id,
        observation_date=date.fromisoformat(body.observation_date) if body.observation_date else date.today(),
        observation_type=body.observation_type,
        severity=severity,
        notes=body.notes,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return _serialize(obs)


@router.delete('/observations/{obs_id}')
def api_delete_observation(obs_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obs = require_resource(db, user, PlantObservation, obs_id, 'editor')
    db.delete(obs)
    db.commit()
    return {'ok': True}


@router.get('/bedplants/{bp_id}/health-score')
def api_health_score(bp_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_resource(db, user, BedPlant, bp_id, 'viewer')
    obs = db.query(PlantObservation).filter(PlantObservation.bed_plant_id == bp_id).all()
    score = compute_health_score(obs)
    label = 'good' if score >= 70 else ('fair' if score >= 40 else 'poor')
    return {'bed_plant_id': bp_id, 'health_score': score, 'label': label}
