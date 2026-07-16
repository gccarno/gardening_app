"""
Integration tests against the live Render API using RENDER_API_KEY.

Verify the key authenticates, our service (garden-app-wa0b) is discoverable,
and logs can be fetched and parsed.

Run with:
    uv run pytest tests/integration/test_render_api.py -v

Skip condition: skipped automatically when RENDER_API_KEY is absent from the
repo-root .env and the environment (e.g. CI).
"""
from pathlib import Path

import pytest
import requests

from scripts.render_logs import (
    API, SERVICE_URL, fetch_logs, find_service, load_api_key, make_session,
)

KEY = load_api_key()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.render,
    pytest.mark.skipif(not KEY, reason="RENDER_API_KEY not set in .env"),
]


@pytest.fixture(scope="module")
def session():
    return make_session(KEY)


@pytest.fixture(scope="module")
def service(session):
    return find_service(session)


def test_api_key_authenticates(session):
    resp = session.get(f"{API}/services", params={"limit": 1})
    assert resp.status_code == 200


def test_service_is_discoverable(service):
    assert service["id"].startswith("srv-")
    assert service["serviceDetails"]["url"] == SERVICE_URL
    assert service.get("suspended") != "suspended"


def test_fetch_and_parse_logs(session, service):
    records = fetch_logs(session, service, limit=50)
    if not records:
        # Idle service may have aged logs out; generate a line and refetch.
        requests.get(f"{SERVICE_URL}/api/health", timeout=120)
        records = fetch_logs(session, service, limit=50)
    assert records, "no logs returned even after pinging /api/health"
    for rec in records:
        assert rec.timestamp
        assert isinstance(rec.message, str)
    # At least the health pings should parse as HTTP access lines eventually,
    # but don't over-assert on log content the app doesn't control.
    assert any(r.message for r in records)
