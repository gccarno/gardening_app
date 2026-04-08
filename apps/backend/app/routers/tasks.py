"""
Task CRUD API routes (JSON — these replace the Flask form-POST/redirect handlers).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.models import Task
from ..db.session import get_db
from ..services.helpers import get_or_404

router = APIRouter(prefix='/api', tags=['tasks'])

_VALID_TYPES = {
    'seeding', 'transplanting', 'weeding', 'watering',
    'fertilizing', 'mulching', 'harvest', 'other',
}


@router.get('/tasks')
def list_tasks(
    completed: Optional[bool] = None,
    garden_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if completed is not None:
        q = q.filter(Task.completed == completed)
    if garden_id is not None:
        q = q.filter(Task.garden_id == garden_id)
    tasks = q.order_by(Task.completed.asc(), Task.due_date.asc().nullslast()).all()
    return [_serialize(t) for t in tasks]


@router.post('/tasks')
def create_task(body: dict, db: Session = Depends(get_db)):
    if not body.get('title'):
        raise HTTPException(status_code=400, detail='title required')
    due = body.get('due_date')
    task = Task(
        title=body['title'],
        description=body.get('description'),
        due_date=date.fromisoformat(due) if due else None,
        task_type=body.get('task_type') or 'other',
        plant_id=body.get('plant_id') or None,
        garden_id=body.get('garden_id') or None,
        bed_id=body.get('bed_id') or None,
    )
    db.add(task)
    db.commit()
    return _serialize(task)


@router.get('/tasks/{task_id}')
def get_task(task_id: int, db: Session = Depends(get_db)):
    return _serialize(get_or_404(db, Task, task_id))


@router.put('/tasks/{task_id}')
def update_task(task_id: int, body: dict, db: Session = Depends(get_db)):
    task = get_or_404(db, Task, task_id)
    due  = body.get('due_date')
    if 'title'       in body: task.title       = body['title']
    if 'description' in body: task.description = body.get('description')
    if 'due_date'    in body: task.due_date     = date.fromisoformat(due) if due else None
    if 'task_type'   in body: task.task_type    = body.get('task_type') or 'other'
    if 'plant_id'    in body: task.plant_id     = body.get('plant_id') or None
    if 'garden_id'   in body: task.garden_id    = body.get('garden_id') or None
    if 'bed_id'      in body: task.bed_id       = body.get('bed_id') or None
    db.commit()
    return _serialize(task)


@router.post('/tasks/{task_id}/complete')
def toggle_complete(task_id: int, db: Session = Depends(get_db)):
    task = get_or_404(db, Task, task_id)
    task.completed      = not task.completed
    task.completed_date = date.today() if task.completed else None
    db.commit()
    return _serialize(task)


@router.delete('/tasks/{task_id}')
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = get_or_404(db, Task, task_id)
    db.delete(task)
    db.commit()
    return {'ok': True}


def _serialize(t: Task) -> dict:
    return {
        'id':             t.id,
        'title':          t.title,
        'description':    t.description,
        'due_date':       t.due_date.isoformat() if t.due_date else None,
        'task_type':      t.task_type,
        'completed':      t.completed,
        'completed_date': t.completed_date.isoformat() if t.completed_date else None,
        'plant_id':       t.plant_id,
        'garden_id':      t.garden_id,
        'bed_id':         t.bed_id,
        'plant_name':     t.plant.name if t.plant else None,
    }
