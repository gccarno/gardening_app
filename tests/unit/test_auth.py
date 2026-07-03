"""Auth: register/login/token flow + Owner/Editor/Viewer role matrix."""
import pytest
from fastapi.testclient import TestClient

from apps.backend.app.db.models import GardenMember, User
from apps.backend.app.db.session import get_db
from apps.backend.app.main import app
from apps.backend.app.services.auth import get_current_user, hash_password


@pytest.fixture
def anon_client(db):
    """Client with NO auth override — exercises the real token path."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _make_user(db, email, role=None, garden=None):
    u = User(email=email, password_hash=hash_password('password123'))
    db.add(u)
    db.flush()
    if role and garden:
        db.add(GardenMember(garden_id=garden.id, user_id=u.id, role=role))
        db.flush()
    return u


def _client_as(db, u):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: u
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Register / login / token flow ─────────────────────────────────────────────

def test_first_user_registers_and_owns_existing_gardens(anon_client, db, user, garden):
    # `garden` exists but `user` fixture bypasses registration — remove users to
    # simulate first run
    db.query(GardenMember).delete()
    db.query(User).delete()
    db.flush()

    r = anon_client.post('/api/auth/register', json={
        'email': 'first@example.com', 'password': 'longenough',
    })
    assert r.status_code == 200
    token = r.json()['token']

    # Token works and the new user owns the pre-existing garden
    me = anon_client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['memberships'][0]['role'] == 'owner'


def test_registration_closed_after_first_user(anon_client, db, user, monkeypatch):
    monkeypatch.delenv('ALLOW_REGISTRATION', raising=False)
    r = anon_client.post('/api/auth/register', json={
        'email': 'second@example.com', 'password': 'longenough',
    })
    assert r.status_code == 403


def test_registration_env_flag(anon_client, db, user, monkeypatch):
    monkeypatch.setenv('ALLOW_REGISTRATION', '1')
    r = anon_client.post('/api/auth/register', json={
        'email': 'second@example.com', 'password': 'longenough',
    })
    assert r.status_code == 200


def test_short_password_rejected(anon_client, db):
    r = anon_client.post('/api/auth/register', json={
        'email': 'x@example.com', 'password': 'short',
    })
    assert r.status_code == 400


def test_login_and_bad_password(anon_client, db, user):
    ok = anon_client.post('/api/auth/login', json={
        'email': 'test@example.com', 'password': 'password123',
    })
    assert ok.status_code == 200
    assert 'token' in ok.json()

    bad = anon_client.post('/api/auth/login', json={
        'email': 'test@example.com', 'password': 'wrong-password',
    })
    assert bad.status_code == 401


def test_requests_require_token(anon_client, db):
    assert anon_client.get('/api/gardens').status_code == 401
    assert anon_client.get('/api/plants').status_code == 401
    assert anon_client.get('/api/health').status_code == 200  # stays open


def test_logout_revokes_token(anon_client, db, user):
    token = anon_client.post('/api/auth/login', json={
        'email': 'test@example.com', 'password': 'password123',
    }).json()['token']
    headers = {'Authorization': f'Bearer {token}'}
    assert anon_client.get('/api/auth/me', headers=headers).status_code == 200
    anon_client.post('/api/auth/logout', headers=headers)
    assert anon_client.get('/api/auth/me', headers=headers).status_code == 401


# ── Role matrix ───────────────────────────────────────────────────────────────

def test_viewer_can_read_but_not_mutate(db, user, garden, bed):
    viewer = _make_user(db, 'viewer@example.com', 'viewer', garden)
    c = _client_as(db, viewer)

    assert c.get(f'/api/gardens/{garden.id}').status_code == 200
    assert c.get(f'/api/beds/{bed.id}').status_code == 200
    assert c.get(f'/api/beds/{bed.id}/grid').status_code == 200

    assert c.put(f'/api/gardens/{garden.id}', json={'name': 'Nope'}).status_code == 403
    assert c.put(f'/api/beds/{bed.id}', json={'name': 'Nope'}).status_code == 403
    assert c.post('/api/beds', json={'name': 'New', 'garden_id': garden.id}).status_code == 403
    assert c.delete(f'/api/gardens/{garden.id}').status_code == 403


def test_editor_can_mutate_but_not_delete_garden_or_share(db, user, garden, bed):
    editor = _make_user(db, 'editor@example.com', 'editor', garden)
    c = _client_as(db, editor)

    assert c.put(f'/api/beds/{bed.id}', json={'name': 'Edited'}).status_code == 200
    assert c.post('/api/beds', json={'name': 'New', 'garden_id': garden.id}).status_code == 200

    assert c.delete(f'/api/gardens/{garden.id}').status_code == 403
    r = c.post(f'/api/gardens/{garden.id}/members',
               json={'email': 'test@example.com', 'role': 'viewer'})
    assert r.status_code == 403


def test_non_member_gets_404(db, user, garden, bed):
    outsider = _make_user(db, 'outsider@example.com')
    c = _client_as(db, outsider)

    assert c.get(f'/api/gardens/{garden.id}').status_code == 404
    assert c.get(f'/api/beds/{bed.id}').status_code == 404
    assert c.get('/api/gardens').json() == []
    assert c.get('/api/beds').json() == []


def test_owner_can_share_and_change_roles(db, user, garden, client):
    other = _make_user(db, 'family@example.com')

    r = client.post(f'/api/gardens/{garden.id}/members',
                    json={'email': 'family@example.com', 'role': 'editor'})
    assert r.status_code == 200

    members = client.get(f'/api/gardens/{garden.id}/members').json()
    assert {m['email']: m['role'] for m in members} == {
        'test@example.com': 'owner', 'family@example.com': 'editor',
    }

    # Shared user can now see the garden
    c2 = _client_as(db, other)
    assert c2.get(f'/api/gardens/{garden.id}').status_code == 200

    # Remove them again (from the owner's client — override was replaced, restore)
    c1 = _client_as(db, user)
    assert c1.delete(f'/api/gardens/{garden.id}/members/{other.id}').status_code == 200
    c2 = _client_as(db, other)
    assert c2.get(f'/api/gardens/{garden.id}').status_code == 404


def test_cannot_remove_last_owner(db, user, garden, client):
    r = client.delete(f'/api/gardens/{garden.id}/members/{user.id}')
    assert r.status_code == 400
