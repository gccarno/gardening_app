"""
Seed Room routes: virtual seed-starting shelf (24 slots per garden).
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import Garden, PlantLibrary, SeedTray
from ..db.session import get_db
from ..services.helpers import get_or_404

router = APIRouter(prefix='/api', tags=['seed_room'])

STAGES = ['sowing', 'germinating', 'seedling', 'hardening', 'ready']
NEXT_STAGE = {s: STAGES[i + 1] for i, s in enumerate(STAGES[:-1])}


def _serialize(s: SeedTray) -> dict:
    lib = s.library_entry
    return {
        'id':                    s.id,
        'garden_id':             s.garden_id,
        'library_id':            s.library_id,
        'plant_name':            s.plant_name,
        'slot_number':           s.slot_number,
        'sow_date':              s.sow_date.isoformat() if s.sow_date else None,
        'germination_date':      s.germination_date.isoformat() if s.germination_date else None,
        'transplant_ready_date': s.transplant_ready_date.isoformat() if s.transplant_ready_date else None,
        'stage':                 s.stage,
        'notes':                 s.notes,
        'image_url':             f'/static/plant_images/{lib.image_filename}' if lib and lib.image_filename else None,
    }


class SeedTrayCreate(BaseModel):
    plant_name: str
    slot_number: int
    library_id: Optional[int] = None
    sow_date: Optional[str] = None
    germination_date: Optional[str] = None
    transplant_ready_date: Optional[str] = None
    stage: Optional[str] = 'sowing'
    notes: Optional[str] = None


class SeedTrayUpdate(BaseModel):
    plant_name: Optional[str] = None
    sow_date: Optional[str] = None
    germination_date: Optional[str] = None
    transplant_ready_date: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None


@router.get('/gardens/{garden_id}/seed-room')
def api_seed_room_list(garden_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    trays = (db.query(SeedTray)
             .filter(SeedTray.garden_id == garden_id)
             .order_by(SeedTray.slot_number)
             .all())
    return [_serialize(t) for t in trays]


@router.post('/gardens/{garden_id}/seed-room')
def api_seed_room_create(garden_id: int, body: SeedTrayCreate, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    if not 1 <= body.slot_number <= 24:
        raise HTTPException(status_code=400, detail='slot_number must be 1–24')
    existing = db.query(SeedTray).filter_by(garden_id=garden_id, slot_number=body.slot_number).first()
    if existing:
        raise HTTPException(status_code=409, detail='slot_already_occupied')
    tray = SeedTray(
        garden_id=garden_id,
        library_id=body.library_id,
        plant_name=body.plant_name,
        slot_number=body.slot_number,
        sow_date=date.fromisoformat(body.sow_date) if body.sow_date else None,
        germination_date=date.fromisoformat(body.germination_date) if body.germination_date else None,
        transplant_ready_date=date.fromisoformat(body.transplant_ready_date) if body.transplant_ready_date else None,
        stage=body.stage or 'sowing',
        notes=body.notes,
    )
    db.add(tray)
    db.commit()
    db.refresh(tray)
    return _serialize(tray)


@router.get('/seed-room/{tray_id}')
def api_seed_room_get(tray_id: int, db: Session = Depends(get_db)):
    tray = get_or_404(db, SeedTray, tray_id)
    return _serialize(tray)


@router.put('/seed-room/{tray_id}')
def api_seed_room_update(tray_id: int, body: SeedTrayUpdate, db: Session = Depends(get_db)):
    tray = get_or_404(db, SeedTray, tray_id)
    if body.plant_name is not None:
        tray.plant_name = body.plant_name
    if body.sow_date is not None:
        tray.sow_date = date.fromisoformat(body.sow_date)
    if body.germination_date is not None:
        tray.germination_date = date.fromisoformat(body.germination_date)
    if body.transplant_ready_date is not None:
        tray.transplant_ready_date = date.fromisoformat(body.transplant_ready_date)
    if body.stage is not None:
        if body.stage not in STAGES:
            raise HTTPException(status_code=400, detail=f'stage must be one of {STAGES}')
        tray.stage = body.stage
    if body.notes is not None:
        tray.notes = body.notes
    db.commit()
    return _serialize(tray)


@router.post('/seed-room/{tray_id}/advance-stage')
def api_seed_room_advance(tray_id: int, db: Session = Depends(get_db)):
    tray = get_or_404(db, SeedTray, tray_id)
    if tray.stage not in NEXT_STAGE:
        raise HTTPException(status_code=400, detail='already_at_final_stage')
    tray.stage = NEXT_STAGE[tray.stage]
    db.commit()
    return _serialize(tray)


@router.delete('/seed-room/{tray_id}')
def api_seed_room_delete(tray_id: int, db: Session = Depends(get_db)):
    tray = get_or_404(db, SeedTray, tray_id)
    db.delete(tray)
    db.commit()
    return {'ok': True}
