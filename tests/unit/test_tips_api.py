"""Tip of the Day must never touch ChromaDB.

Loading ChromaDB's default embedding model (all-MiniLM-L6-v2, 79 MB) inside a
request killed the 512 MB Render instance twice on 2026-07-27/28, taking the
whole backend down for ~60-90s mid-request. The tip is a deterministic daily
index into a static list, so it needs no vector store at all.
"""
import sys
from datetime import date

import pytest

from apps.backend.app.routers.tips import _SEED_TIPS


@pytest.fixture
def no_chromadb(monkeypatch):
    """Make `import chromadb` fail, the way a stripped deployment would."""
    class Blocker:
        def find_module(self, name, path=None):
            return self.find_spec(name, path)

        def find_spec(self, name, path=None, target=None):
            if name == 'chromadb' or name.startswith('chromadb.'):
                raise ImportError('chromadb is blocked in this test')
            return None

    monkeypatch.delitem(sys.modules, 'chromadb', raising=False)
    monkeypatch.setattr(sys, 'meta_path', [Blocker(), *sys.meta_path])


def test_returns_a_real_tip_without_chromadb(client, no_chromadb):
    body = client.get('/api/tip-of-the-day').json()
    assert body['tip'] in _SEED_TIPS
    assert body['total'] == len(_SEED_TIPS)


def test_tip_matches_the_ordinal_day(client):
    body = client.get('/api/tip-of-the-day').json()
    expected = date.today().toordinal() % len(_SEED_TIPS)
    assert body['tip_index'] == expected
    assert body['tip'] == _SEED_TIPS[expected]


def test_repeated_calls_are_stable(client):
    first = client.get('/api/tip-of-the-day').json()
    second = client.get('/api/tip-of-the-day').json()
    assert first == second
