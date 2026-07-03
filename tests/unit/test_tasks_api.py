"""Task CRUD endpoint tests."""
from datetime import date


def test_create_task(client, garden):
    r = client.post('/api/tasks', json={
        'title': 'Weed the beds', 'task_type': 'weeding',
        'due_date': '2026-07-10', 'garden_id': garden.id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data['title'] == 'Weed the beds'
    assert data['due_date'] == '2026-07-10'
    assert data['completed'] is False


def test_create_task_requires_title(client):
    assert client.post('/api/tasks', json={}).status_code == 400


def test_toggle_complete(client, upcoming_task):
    r = client.post(f'/api/tasks/{upcoming_task.id}/complete')
    data = r.json()
    assert data['completed'] is True
    assert data['completed_date'] == date.today().isoformat()

    r = client.post(f'/api/tasks/{upcoming_task.id}/complete')
    data = r.json()
    assert data['completed'] is False
    assert data['completed_date'] is None


def test_filter_by_completed(client, upcoming_task):
    client.post(f'/api/tasks/{upcoming_task.id}/complete')
    assert client.get('/api/tasks?completed=false').json() == []
    done = client.get('/api/tasks?completed=true').json()
    assert len(done) == 1


def test_filter_by_garden(client, garden, upcoming_task):
    assert len(client.get(f'/api/tasks?garden_id={garden.id}').json()) == 1
    # Nonexistent (or non-member) garden → 404, hides existence
    assert client.get('/api/tasks?garden_id=99999').status_code == 404


def test_update_task(client, upcoming_task):
    r = client.put(f'/api/tasks/{upcoming_task.id}', json={
        'title': 'Water everything', 'due_date': None,
    })
    data = r.json()
    assert data['title'] == 'Water everything'
    assert data['due_date'] is None


def test_delete_task(client, upcoming_task):
    assert client.delete(f'/api/tasks/{upcoming_task.id}').json()['ok'] is True
    assert client.get(f'/api/tasks/{upcoming_task.id}').status_code == 404
