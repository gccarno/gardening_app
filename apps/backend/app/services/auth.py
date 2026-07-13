"""
Authentication and garden-membership authorization.

Design (single-family app — deliberately simple):
  * Opaque bearer tokens: `secrets.token_hex(32)`, stored SHA-256-hashed in
    auth_token. Same header for the React SPA and the Android Retrofit client:
    `Authorization: Bearer <token>`. Revoke by deleting the row.
  * Passwords hashed with argon2 (argon2-cffi).
  * Roles per garden via GardenMember: viewer < editor < owner.
    GETs need viewer, mutations editor, delete-garden/sharing owner.
  * Resources with no garden (garden_id NULL — planner "unassigned" beds and
    orphan plants) are accessible to any authenticated user.

The require_* helpers are plain functions (not FastAPI dependencies) so unit
tests can call router functions directly with a user fixture.
"""
import hashlib
import secrets
from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db.models import (
    AuthToken, BedPlant, Garden, GardenMember, User,
)
from ..db.session import get_db

_ph = PasswordHasher()

ROLE_RANK = {'viewer': 0, 'editor': 1, 'owner': 2}


# ── Passwords & tokens ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerificationError:
        return False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_token(db: Session, user: User) -> str:
    """Create a new auth token for the user. Caller must commit."""
    raw = secrets.token_hex(32)
    db.add(AuthToken(user_id=user.id, token_hash=_hash_token(raw)))
    return raw


def revoke_token(db: Session, raw: str) -> None:
    db.query(AuthToken).filter_by(token_hash=_hash_token(raw)).delete()


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Not authenticated')
    raw = authorization.split(' ', 1)[1].strip()
    token = db.query(AuthToken).filter_by(token_hash=_hash_token(raw)).first()
    if not token:
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    # Commit immediately — read-only requests never commit, so the write would
    # otherwise be rolled back when the session closes. Throttled to one write
    # per token per 5 min to avoid a DB write on every request.
    now = datetime.utcnow()
    if token.last_used_at is None or (now - token.last_used_at).total_seconds() > 300:
        token.last_used_at = now
        db.commit()
    return token.user


# ── Garden-membership authorization ───────────────────────────────────────────

def member_role(db: Session, user: User, garden_id: int) -> str | None:
    m = db.query(GardenMember).filter_by(garden_id=garden_id, user_id=user.id).first()
    return m.role if m else None


def member_garden_ids(db: Session, user: User) -> list[int]:
    return [m.garden_id for m in
            db.query(GardenMember).filter_by(user_id=user.id).all()]


def require_garden(db: Session, user: User, garden_id: int,
                   min_role: str = 'viewer') -> Garden:
    """Return the garden if the user is a member with at least min_role.

    Non-members get 404 (hides existence); insufficient role gets 403.
    """
    garden = db.get(Garden, garden_id)
    if garden is None:
        raise HTTPException(status_code=404, detail=f'Garden {garden_id} not found')
    role = member_role(db, user, garden_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f'Garden {garden_id} not found')
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        raise HTTPException(status_code=403, detail=f'Requires {min_role} access')
    return garden


def _resolve_garden_id(db: Session, obj) -> int | None:
    """Walk a resource up to its owning garden (None = unowned/global)."""
    if isinstance(obj, BedPlant):
        return obj.bed.garden_id if obj.bed else None
    # PlantObservation → BedPlant → bed → garden
    if hasattr(obj, 'bed_plant') and obj.bed_plant is not None:
        return _resolve_garden_id(db, obj.bed_plant)
    return getattr(obj, 'garden_id', None)


def require_resource(db: Session, user: User, model, id: int,
                     min_role: str = 'viewer'):
    """get_or_404 + role check against the resource's owning garden.

    Resources not attached to any garden are allowed for any logged-in user.
    """
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f'{model.__name__} {id} not found')
    garden_id = _resolve_garden_id(db, obj)
    if garden_id is not None:
        require_garden(db, user, garden_id, min_role)
    return obj
