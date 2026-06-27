"""
Garden journal routes.
"""
import json
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import Garden, JournalEntry
from ..db.session import get_db
from ..services.helpers import get_or_404

router = APIRouter(prefix='/api', tags=['journal'])


def _serialize(e: JournalEntry) -> dict:
    tags = []
    if e.tags:
        try:
            tags = json.loads(e.tags)
        except Exception:
            pass
    return {
        'id':             e.id,
        'garden_id':      e.garden_id,
        'plant_id':       e.plant_id,
        'entry_date':     e.entry_date.isoformat(),
        'title':          e.title,
        'body':           e.body,
        'tags':           tags,
        'image_filename': e.image_filename,
        'created_at':     e.created_at.isoformat(),
    }


class JournalCreate(BaseModel):
    entry_date: Optional[str] = None  # YYYY-MM-DD; defaults to today
    title: str
    body: Optional[str] = None
    tags: Optional[list[str]] = None
    plant_id: Optional[int] = None


class JournalUpdate(BaseModel):
    entry_date: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[list[str]] = None
    plant_id: Optional[int] = None


@router.get('/gardens/{garden_id}/journal')
def api_journal_list(garden_id: int, page: int = 1, per_page: int = 20, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    q = (db.query(JournalEntry)
         .filter(JournalEntry.garden_id == garden_id)
         .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()))
    total = q.count()
    entries = q.offset((page - 1) * per_page).limit(per_page).all()
    return {'total': total, 'page': page, 'entries': [_serialize(e) for e in entries]}


@router.post('/gardens/{garden_id}/journal')
def api_journal_create(garden_id: int, body: JournalCreate, db: Session = Depends(get_db)):
    get_or_404(db, Garden, garden_id)
    entry = JournalEntry(
        garden_id=garden_id,
        plant_id=body.plant_id,
        entry_date=date.fromisoformat(body.entry_date) if body.entry_date else date.today(),
        title=body.title,
        body=body.body,
        tags=json.dumps(body.tags) if body.tags else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _serialize(entry)


@router.get('/journal/{entry_id}')
def api_journal_get(entry_id: int, db: Session = Depends(get_db)):
    entry = get_or_404(db, JournalEntry, entry_id)
    return _serialize(entry)


@router.put('/journal/{entry_id}')
def api_journal_update(entry_id: int, body: JournalUpdate, db: Session = Depends(get_db)):
    entry = get_or_404(db, JournalEntry, entry_id)
    if body.entry_date is not None:
        entry.entry_date = date.fromisoformat(body.entry_date)
    if body.title is not None:
        entry.title = body.title
    if body.body is not None:
        entry.body = body.body
    if body.tags is not None:
        entry.tags = json.dumps(body.tags)
    if body.plant_id is not None:
        entry.plant_id = body.plant_id
    db.commit()
    return _serialize(entry)


@router.delete('/journal/{entry_id}')
def api_journal_delete(entry_id: int, db: Session = Depends(get_db)):
    entry = get_or_404(db, JournalEntry, entry_id)
    db.delete(entry)
    db.commit()
    return {'ok': True}
