"""Photo identification endpoint with a stubbed vision provider."""
import io
import json

import pytest


def _png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (34, 139, 34)).save(buf, format='PNG')
    return buf.getvalue()


@pytest.fixture
def stub_vision(monkeypatch):
    """Replace the Claude vision call; returns a mutable dict to set the reply."""
    from apps.ml_service.app import llm_provider
    state = {'reply': json.dumps({
        'candidates': [
            {'name': 'Tomato', 'scientific_name': 'Solanum lycopersicum', 'confidence': 0.92},
        ],
        'diagnosis': 'A healthy tomato plant.',
        'care_advice': 'Water deeply once a week.',
    })}
    monkeypatch.setattr(llm_provider, 'complete_vision',
                        lambda system, user, img, media_type='image/jpeg': state['reply'])
    return state


def _post(client, mode='identify'):
    return client.post('/api/identify',
                       files={'image': ('leaf.png', _png_bytes(), 'image/png')},
                       data={'mode': mode})


def test_identify_returns_candidates_with_library_match(client, db, library_plant, stub_vision):
    library_plant.scientific_name = 'Solanum lycopersicum'
    db.flush()

    r = _post(client)
    assert r.status_code == 200
    data = r.json()
    assert data['mode'] == 'identify'
    c = data['candidates'][0]
    assert c['name'] == 'Tomato'
    assert c['confidence'] == 0.92
    assert c['library_match']['library_id'] == library_plant.id
    assert data['care_advice'] == 'Water deeply once a week.'


def test_identify_no_library_match(client, stub_vision):
    r = _post(client)
    assert r.status_code == 200
    assert r.json()['candidates'][0]['library_match'] is None


def test_disease_mode_skips_library_match(client, db, library_plant, stub_vision):
    stub_vision['reply'] = json.dumps({
        'candidates': [{'name': 'Early blight', 'scientific_name': 'Alternaria solani',
                        'confidence': 0.8}],
        'diagnosis': 'Early blight on lower leaves.',
        'care_advice': 'Remove affected leaves.',
    })
    r = _post(client, mode='disease')
    assert r.status_code == 200
    assert r.json()['candidates'][0]['library_match'] is None


def test_unparseable_reply_falls_back_to_prose(client, stub_vision):
    stub_vision['reply'] = 'This looks like a tomato plant to me!'
    r = _post(client)
    assert r.status_code == 200
    data = r.json()
    assert data['candidates'] == []
    assert 'tomato' in data['diagnosis'].lower()


def test_invalid_mode_rejected(client, stub_vision):
    assert _post(client, mode='aura').status_code == 400


def test_unconfigured_provider_returns_503(client, monkeypatch):
    from apps.ml_service.app import llm_provider

    def _raise(*args, **kwargs):
        raise RuntimeError('Photo identification is not configured.')
    monkeypatch.setattr(llm_provider, 'complete_vision', _raise)
    r = _post(client)
    assert r.status_code == 503


def test_non_image_rejected(client, stub_vision):
    r = client.post('/api/identify',
                    files={'image': ('notes.txt', b'hello', 'text/plain')},
                    data={'mode': 'identify'})
    assert r.status_code == 400
