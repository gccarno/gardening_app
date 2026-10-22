"""On-device plant ID: POST /api/identify/embedding (client embeds, server ranks).

The pgvector query itself can't run on SQLite, so `_prototype_scores` is
stubbed here; the math and response shaping around it are what's tested.
"""
import json
import math

import pytest

from apps.ml_service.app import plantid

CONFIG = {
    'model_version': 'test_v1',
    'backbone': 'stub',
    'embed_dim': 4,
    'temperature': 0.05,
    'tau': 0.6,
}


@pytest.fixture
def config(monkeypatch, tmp_path):
    (tmp_path / 'plantid_test_v1.json').write_text(json.dumps(CONFIG), encoding='utf-8')
    monkeypatch.setattr(plantid, '_MODELS_DIR', tmp_path)
    plantid.load_config.cache_clear()
    yield CONFIG
    plantid.load_config.cache_clear()


@pytest.fixture
def stub_scores(monkeypatch):
    """Replace the SQL with fixed (top-k rows, max_sim, sum_exp) results."""
    from apps.backend.app.routers import identify
    state = {'top': [], 'max_sim': 0.0, 'sum_exp': 1.0}

    def fake(db, embedding, version, k, temperature):
        state['called_with'] = (list(embedding), version, k, temperature)
        return state['top'], state['max_sim'], state['sum_exp']

    monkeypatch.setattr(identify, '_prototype_scores', fake)
    return state


# ── pure math ────────────────────────────────────────────────────────────────

def test_probabilities_match_full_softmax():
    sims = [0.9, 0.8, 0.5, 0.1]
    t = 0.1
    m = max(sims)
    z = sum(math.exp((s - m) / t) for s in sims)
    probs = plantid.probabilities([0.9, 0.8], m, z, t)
    full = [math.exp(s / t) / sum(math.exp(x / t) for x in sims) for s in sims]
    assert probs == pytest.approx(full[:2])


def test_load_config_unknown_version_is_none(config):
    assert plantid.load_config('nope_v9') is None
    assert plantid.load_config('test_v1')['tau'] == 0.6


def test_load_config_rejects_path_traversal(config):
    assert plantid.load_config('../secrets') is None


# ── endpoint ─────────────────────────────────────────────────────────────────

def _post(client, embedding=(1.0, 0.0, 0.0, 0.0), version='test_v1', top_k=3):
    return client.post('/api/identify/embedding',
                       json={'embedding': list(embedding), 'model_version': version, 'top_k': top_k})


def test_confident_top_match_returns_local_candidates(client, db, library_plant, config, stub_scores):
    library_plant.scientific_name = 'Solanum lycopersicum'
    db.flush()
    # top sim 0.9 vs 0.7 at T=0.05: p1 = 1/(1+e^-4) ≈ 0.982 if those are the only two
    stub_scores['top'] = [
        ('solanum lycopersicum', 'Solanum lycopersicum', 0.9, library_plant.id),
        ('capsicum annuum', 'Capsicum annuum', 0.7, None),
    ]
    stub_scores['max_sim'] = 0.9
    stub_scores['sum_exp'] = 1.0 + math.exp((0.7 - 0.9) / 0.05)

    r = _post(client)
    assert r.status_code == 200
    data = r.json()
    assert data['source'] == 'local'
    assert data['confident'] is True
    assert data['model_version'] == 'test_v1'
    assert data['mode'] == 'identify'
    top = data['candidates'][0]
    assert top['scientific_name'] == 'Solanum lycopersicum'
    assert top['confidence'] == pytest.approx(0.982, abs=1e-3)
    assert top['library_match']['library_id'] == library_plant.id
    assert top['name'] == library_plant.name
    assert data['candidates'][1]['library_match'] is None
    # Same keys as POST /api/identify so the UIs render either response.
    assert {'diagnosis', 'care_advice'} <= data.keys()
    assert stub_scores['called_with'][1:] == ('test_v1', 3, 0.05)


def test_low_confidence_is_flagged_not_confident(client, config, stub_scores):
    stub_scores['top'] = [('a b', 'A b', 0.50, None), ('c d', 'C d', 0.49, None)]
    stub_scores['max_sim'] = 0.50
    stub_scores['sum_exp'] = 50.0   # mass spread over many species
    r = _post(client)
    assert r.status_code == 200
    assert r.json()['confident'] is False


def test_unknown_model_version_is_409(client, config, stub_scores):
    r = _post(client, version='old_v0')
    assert r.status_code == 409


def test_wrong_embedding_width_is_400(client, config, stub_scores):
    r = _post(client, embedding=(1.0, 0.0))
    assert r.status_code == 400


def test_no_prototypes_for_version_is_409(client, config, stub_scores):
    stub_scores['top'] = []
    r = _post(client)
    assert r.status_code == 409


def test_top_k_is_capped(client, config, stub_scores):
    stub_scores['top'] = [('a b', 'A b', 0.5, None)]
    stub_scores['max_sim'] = 0.5
    _post(client, top_k=500)
    assert stub_scores['called_with'][2] == 10


# ── model download ───────────────────────────────────────────────────────────

def _deploy(tmp_path, version, created):
    cfg = dict(CONFIG, model_version=version, created=created, input_size=224,
               preprocess='center-square crop, bilinear resize, RGB/255, NCHW float32')
    (tmp_path / f'plantid_{version}.json').write_text(json.dumps(cfg), encoding='utf-8')
    (tmp_path / f'plantid_{version}.onnx').write_bytes(b'onnx-bytes-' + version.encode())


def test_model_config_serves_newest_version(client, monkeypatch, tmp_path):
    monkeypatch.setattr(plantid, '_MODELS_DIR', tmp_path)
    monkeypatch.delenv('PLANTID_MODEL_VERSION', raising=False)
    plantid.load_config.cache_clear()
    _deploy(tmp_path, 'v1', '2026-10-01T00:00:00+00:00')
    _deploy(tmp_path, 'v2', '2026-10-15T00:00:00+00:00')
    r = client.get('/api/identify/model')
    assert r.status_code == 200
    assert r.json() == {'model_version': 'v2', 'input_size': 224, 'embed_dim': 4,
                        'preprocess': 'center-square crop, bilinear resize, RGB/255, NCHW float32'}
    # A pinned version wins (rollback without deleting files).
    monkeypatch.setenv('PLANTID_MODEL_VERSION', 'v1')
    assert client.get('/api/identify/model').json()['model_version'] == 'v1'
    plantid.load_config.cache_clear()


def test_model_file_download_is_immutable(client, monkeypatch, tmp_path):
    monkeypatch.setattr(plantid, '_MODELS_DIR', tmp_path)
    plantid.load_config.cache_clear()
    _deploy(tmp_path, 'v1', '2026-10-01T00:00:00+00:00')
    r = client.get('/api/identify/model/v1.onnx')
    assert r.status_code == 200
    assert r.content == b'onnx-bytes-v1'
    assert 'immutable' in r.headers['cache-control']
    assert client.get('/api/identify/model/v9.onnx').status_code == 404
    plantid.load_config.cache_clear()


def test_model_config_404_when_nothing_deployed(client, monkeypatch, tmp_path):
    monkeypatch.setattr(plantid, '_MODELS_DIR', tmp_path)
    monkeypatch.delenv('PLANTID_MODEL_VERSION', raising=False)
    plantid.load_config.cache_clear()
    assert client.get('/api/identify/model').status_code == 404
