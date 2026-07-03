"""
Auth routes: register, login, logout, me — plus garden member management.

Registration is open while the app has no users (first run) and afterwards
only when ALLOW_REGISTRATION=1. Family members are normally added by
sharing a garden with their email after they register, or by registering
while ALLOW_REGISTRATION is temporarily enabled.
"""
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import GARDEN_ROLES, Garden, GardenMember, User
from ..db.session import get_db
from ..services.auth import (
    create_token, get_current_user, hash_password, require_garden,
    revoke_token, verify_password,
)

router = APIRouter(prefix='/api/auth', tags=['auth'])
members_router = APIRouter(prefix='/api', tags=['auth'])


def _serialize_user(u: User) -> dict:
    return {'id': u.id, 'email': u.email, 'display_name': u.display_name}


class Credentials(BaseModel):
    email: str
    password: str
    display_name: str | None = None


@router.post('/register')
def register(body: Credentials, db: Session = Depends(get_db)):
    first_user = db.query(User).first() is None
    if not first_user and os.environ.get('ALLOW_REGISTRATION') != '1':
        raise HTTPException(status_code=403, detail='Registration is disabled')

    email = body.email.strip().lower()
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail='Valid email required')
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail='Password must be at least 8 characters')
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=400, detail='Email already registered')

    user = User(email=email, display_name=body.display_name,
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()

    if first_user:
        # Backfill: the first account owns all pre-existing gardens.
        for g in db.query(Garden).all():
            db.add(GardenMember(garden_id=g.id, user_id=user.id, role='owner'))

    token = create_token(db, user)
    db.commit()
    return {'token': token, 'user': _serialize_user(user)}


@router.post('/login')
def login(body: Credentials, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter_by(email=email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid email or password')
    token = create_token(db, user)
    db.commit()
    return {'token': token, 'user': _serialize_user(user)}


@router.post('/logout')
def logout(
    authorization: str | None = Header(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = authorization.split(' ', 1)[1].strip() if authorization else ''
    revoke_token(db, raw)
    db.commit()
    return {'ok': True}


@router.get('/me')
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        **_serialize_user(user),
        'memberships': [
            {'garden_id': m.garden_id, 'garden_name': m.garden.name, 'role': m.role}
            for m in user.memberships
        ],
    }


@router.get('/registration-open')
def registration_open(db: Session = Depends(get_db)):
    """Lets the login page know whether to show the register form."""
    first_user = db.query(User).first() is None
    return {'open': first_user or os.environ.get('ALLOW_REGISTRATION') == '1'}


# ── Garden member management (sharing) ────────────────────────────────────────

class MemberBody(BaseModel):
    email: str
    role: str = 'viewer'


@members_router.get('/gardens/{garden_id}/members')
def list_members(garden_id: int,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    require_garden(db, user, garden_id, 'viewer')
    members = db.query(GardenMember).filter_by(garden_id=garden_id).all()
    return [{
        'user_id': m.user_id,
        'email': m.user.email,
        'display_name': m.user.display_name,
        'role': m.role,
    } for m in members]


@members_router.post('/gardens/{garden_id}/members')
def add_member(garden_id: int, body: MemberBody,
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    require_garden(db, user, garden_id, 'owner')
    if body.role not in GARDEN_ROLES:
        raise HTTPException(status_code=400, detail=f'role must be one of {GARDEN_ROLES}')
    target = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not target:
        raise HTTPException(status_code=404, detail='No account with that email — they need to register first')
    existing = db.query(GardenMember).filter_by(
        garden_id=garden_id, user_id=target.id).first()
    if existing:
        existing.role = body.role
    else:
        db.add(GardenMember(garden_id=garden_id, user_id=target.id, role=body.role))
    db.commit()
    return {'ok': True}


@members_router.delete('/gardens/{garden_id}/members/{user_id}')
def remove_member(garden_id: int, user_id: int,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    require_garden(db, user, garden_id, 'owner')
    m = db.query(GardenMember).filter_by(garden_id=garden_id, user_id=user_id).first()
    if not m:
        raise HTTPException(status_code=404, detail='Not a member')
    owners = db.query(GardenMember).filter_by(garden_id=garden_id, role='owner').count()
    if m.role == 'owner' and owners <= 1:
        raise HTTPException(status_code=400, detail='Cannot remove the last owner')
    db.delete(m)
    db.commit()
    return {'ok': True}
