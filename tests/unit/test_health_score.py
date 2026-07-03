"""Health score computation and observation endpoints."""
from datetime import date, timedelta

from apps.backend.app.db.models import PlantObservation
from apps.backend.app.routers.observations import compute_health_score


def _obs(obs_type, severity, days_ago=0):
    return PlantObservation(
        observation_date=date.today() - timedelta(days=days_ago),
        observation_type=obs_type,
        severity=severity,
    )


def test_no_observations_neutral_default():
    assert compute_health_score([]) == 75


def test_old_observations_ignored():
    assert compute_health_score([_obs('disease', 5, days_ago=45)]) == 75


def test_severe_disease_lowers_score():
    assert compute_health_score([_obs('disease', 5)]) == 50


def test_healthy_observation_raises_score():
    assert compute_health_score([_obs('healthy', 5)]) == 100


def test_mixed_observations_weighted_by_recency():
    # Recent healthy should outweigh older pest damage
    score = compute_health_score([
        _obs('pest_damage', 4, days_ago=25),   # weight ~0.17, contribution 60
        _obs('healthy', 4, days_ago=0),        # weight 1.0, contribution 96
    ])
    assert score > 75


def test_score_bounds():
    score = compute_health_score([_obs('disease', 5), _obs('pest_damage', 5)])
    assert 0 <= score <= 100


# ── Endpoint tests ────────────────────────────────────────────────────────────

def _bp_id(db, plant_in_bed):
    return plant_in_bed.bed_plants[0].id


def test_create_and_list_observations(client, db, plant_in_bed):
    bp_id = _bp_id(db, plant_in_bed)
    r = client.post(f'/api/bedplants/{bp_id}/observations', json={
        'observation_type': 'yellowing', 'severity': 2, 'notes': 'lower leaves',
    })
    assert r.status_code == 200
    obs = client.get(f'/api/bedplants/{bp_id}/observations').json()
    assert len(obs) == 1
    assert obs[0]['observation_type'] == 'yellowing'


def test_invalid_observation_type_rejected(client, db, plant_in_bed):
    bp_id = _bp_id(db, plant_in_bed)
    r = client.post(f'/api/bedplants/{bp_id}/observations', json={
        'observation_type': 'alien_invasion',
    })
    assert r.status_code == 400


def test_severity_clamped(client, db, plant_in_bed):
    bp_id = _bp_id(db, plant_in_bed)
    r = client.post(f'/api/bedplants/{bp_id}/observations', json={
        'observation_type': 'disease', 'severity': 99,
    })
    assert r.json()['severity'] == 5


def test_health_score_endpoint(client, db, plant_in_bed):
    bp_id = _bp_id(db, plant_in_bed)
    r = client.get(f'/api/bedplants/{bp_id}/health-score')
    assert r.status_code == 200
    data = r.json()
    assert data['health_score'] == 75
    assert data['label'] == 'good'
