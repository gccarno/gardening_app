"""
Compost helper routes.
"""
import json
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import CompostBin, Garden
from ..db.session import get_db
from ..services.helpers import get_or_404

router = APIRouter(prefix='/api', tags=['compost'])

STAGES = ['building', 'active', 'curing', 'ready']
NEXT_STAGE = {s: STAGES[i + 1] for i, s in enumerate(STAGES[:-1])}

# Typical days to advance stages when no explicit date is set
_STAGE_DAYS = {'building': 30, 'active': 45, 'curing': 30}


def _serialize(b: CompostBin) -> dict:
    materials = []
    if b.materials:
        try:
            materials = json.loads(b.materials)
        except Exception:
            pass
    return {
        'id':                    b.id,
        'garden_id':             b.garden_id,
        'name':                  b.name,
        'started_date':          b.started_date.isoformat() if b.started_date else None,
        'estimated_ready_date':  b.estimated_ready_date.isoformat() if b.estimated_ready_date else None,
        'stage':                 b.stage,
        'notes':                 b.notes,
        'materials':             materials,
        'created_at':            b.created_at.isoformat(),
    }


class BinCreate(BaseModel):
    name: str
    started_date: Optional[str] = None
    notes: Optional[str] = None


class BinUpdate(BaseModel):
    name: Optional[str] = None
    started_date: Optional[str] = None
    estimated_ready_date: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None


class MaterialAdd(BaseModel):
    material: str
    quantity_lbs: Optional[float] = None


@router.get('/gardens/{garden_id}/compost')
def api_compost_list(garden_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    bins = (db.query(CompostBin)
            .filter(CompostBin.garden_id == garden_id)
            .order_by(CompostBin.created_at.desc())
            .all())
    return [_serialize(b) for b in bins]


@router.post('/gardens/{garden_id}/compost')
def api_compost_create(garden_id: int, body: BinCreate, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    started = date.fromisoformat(body.started_date) if body.started_date else date.today()
    estimated_ready = started + timedelta(days=105)  # ~3.5 months typical
    bin_ = CompostBin(
        garden_id=garden_id,
        name=body.name,
        started_date=started,
        estimated_ready_date=estimated_ready,
        stage='building',
        notes=body.notes,
        materials=json.dumps([]),
    )
    db.add(bin_)
    db.commit()
    db.refresh(bin_)
    return _serialize(bin_)


@router.put('/compost/{bin_id}')
def api_compost_update(bin_id: int, body: BinUpdate, db: Session = Depends(get_db)):
    bin_ = get_or_404(db, CompostBin, bin_id)
    if body.name is not None:
        bin_.name = body.name
    if body.started_date is not None:
        bin_.started_date = date.fromisoformat(body.started_date)
    if body.estimated_ready_date is not None:
        bin_.estimated_ready_date = date.fromisoformat(body.estimated_ready_date)
    if body.stage is not None:
        if body.stage not in STAGES:
            raise HTTPException(status_code=400, detail=f'stage must be one of {STAGES}')
        bin_.stage = body.stage
    if body.notes is not None:
        bin_.notes = body.notes
    db.commit()
    return _serialize(bin_)


@router.post('/compost/{bin_id}/add-material')
def api_compost_add_material(bin_id: int, body: MaterialAdd, db: Session = Depends(get_db)):
    bin_ = get_or_404(db, CompostBin, bin_id)
    materials = []
    if bin_.materials:
        try:
            materials = json.loads(bin_.materials)
        except Exception:
            pass
    materials.append({
        'material':     body.material,
        'date_added':   date.today().isoformat(),
        'quantity_lbs': body.quantity_lbs,
    })
    bin_.materials = json.dumps(materials)
    db.commit()
    return _serialize(bin_)


@router.post('/compost/{bin_id}/advance-stage')
def api_compost_advance(bin_id: int, db: Session = Depends(get_db)):
    bin_ = get_or_404(db, CompostBin, bin_id)
    if bin_.stage not in NEXT_STAGE:
        raise HTTPException(status_code=400, detail='already_at_final_stage')
    bin_.stage = NEXT_STAGE[bin_.stage]
    db.commit()
    return _serialize(bin_)


@router.delete('/compost/{bin_id}')
def api_compost_delete(bin_id: int, db: Session = Depends(get_db)):
    bin_ = get_or_404(db, CompostBin, bin_id)
    db.delete(bin_)
    db.commit()
    return {'ok': True}
