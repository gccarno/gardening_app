"""The recommender must not scale its work with the size of the plant library.

/api/recommendations and /api/chat both score every PlantLibrary row (9,999 in
production). On 2026-07-28 that pinned the free instance's CPU at its 0.15 cap
and grew memory from 181 MB to 532 MB against a 536 MB limit, restarting the
process mid-request and failing four E2E tests. Three separate costs were
involved, and these tests guard each one:

  * one model call, not one per plant
  * one image query, not one per plant
  * only the columns the scorer reads, not every column
"""
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import event

from apps.backend.app.db.models import PlantLibrary, PlantLibraryImage
from apps.ml_service.app.recommender import recommend

_CONTEXT = {
    'zone': 5, 'sunlight_hours': 6, 'current_month': 4, 'soil_ph': 6.5,
    'preferred_types': ['vegetable'], 'current_plant_names': [],
}


def _plants(n):
    return [
        {'id': i, 'name': f'Plant {i}', 'type': 'vegetable',
         'min_zone': 3, 'max_zone': 9, 'sunlight': 'Full sun',
         'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'difficulty': 'easy',
         'days_to_harvest': 60, 'good_neighbors': None,
         'fruit_months': None, 'bloom_months': None, 'growth_months': None}
        for i in range(n)
    ]


class _FakeModel:
    """Records how many times it was called and with how many rows."""

    def __init__(self):
        self.calls = []

    def predict_proba(self, X):
        rows = list(X)
        self.calls.append(len(rows))
        # Descending scores so ordering is unambiguous.
        return [[0.0, 1.0 - i / (len(rows) + 1)] for i in range(len(rows))]


def test_model_is_called_once_not_once_per_plant():
    model = _FakeModel()
    with patch('apps.ml_service.app.recommender._load_model', return_value=model):
        recommend(_plants(50), _CONTEXT, top_n=5)
    assert len(model.calls) == 1, f'expected 1 batched call, got {len(model.calls)}'
    assert model.calls[0] == 50


def test_batched_scores_are_applied_to_the_right_plants():
    model = _FakeModel()
    with patch('apps.ml_service.app.recommender._load_model', return_value=model):
        results = recommend(_plants(10), _CONTEXT, top_n=3)
    # _FakeModel scores row i highest at i=0, so plants must come back in order.
    assert [r['plant_id'] for r in results] == [0, 1, 2]
    assert results[0]['score'] > results[1]['score'] > results[2]['score']


def test_falls_back_to_rule_scoring_when_the_model_raises():
    class Broken:
        def predict_proba(self, X):
            raise RuntimeError('model is corrupt')

    with patch('apps.ml_service.app.recommender._load_model', return_value=Broken()):
        results = recommend(_plants(5), _CONTEXT, top_n=2)
    assert len(results) == 2
    assert all(r['score'] > 0 for r in results)


# ── Query-count guard ─────────────────────────────────────────────────────────

def _seed_library(db, n):
    for _ in range(n):
        tag = uuid.uuid4().hex[:8]          # file_hash is UNIQUE
        p = PlantLibrary(name=f'Zed Plant {tag}', type='vegetable',
                         min_zone=3, max_zone=9, sunlight='Full sun',
                         difficulty='easy', days_to_harvest=60)
        db.add(p)
        db.flush()
        db.add(PlantLibraryImage(plant_library_id=p.id, filename=f'{tag}.jpg',
                                 source='manual', file_hash=tag,
                                 is_primary=True))
    db.flush()


@pytest.fixture
def count_selects(engine):
    counter = {'n': 0}

    def before(conn, cursor, statement, *a):
        if statement.lstrip().upper().startswith('SELECT'):
            counter['n'] += 1

    event.listen(engine, 'before_cursor_execute', before)
    yield counter
    event.remove(engine, 'before_cursor_execute', before)


def test_query_count_does_not_grow_with_the_library(client, db, garden, count_selects):
    """A bigger library must not mean more queries -- that is the N+1."""
    _seed_library(db, 4)
    count_selects['n'] = 0
    assert client.get(f'/api/recommendations?garden_id={garden.id}').status_code == 200
    small = count_selects['n']

    _seed_library(db, 16)
    count_selects['n'] = 0
    assert client.get(f'/api/recommendations?garden_id={garden.id}').status_code == 200
    large = count_selects['n']

    # Not equality: the session's identity map already holds garden.beds by the
    # second call, so the larger run can legitimately issue one query fewer.
    # What must hold is that five times the plants costs no extra queries.
    assert large <= small, (
        f'{small} queries for 4 plants but {large} for 20 -- per-plant queries remain'
    )
    assert large <= 6, f'{large} queries is more than a constant handful'


def test_recommendations_still_return_primary_image(client, db, garden):
    _seed_library(db, 3)
    body = client.get(f'/api/recommendations?garden_id={garden.id}').json()
    recs = [r for r in body['recommendations'] if r['name'].startswith('Zed Plant')]
    assert recs, 'seeded plants should be recommendable'
    assert any(r['image_url'] and r['image_url'].endswith('.jpg') for r in recs)
