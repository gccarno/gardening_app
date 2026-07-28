"""Sentry trace sampling and event filtering: keep noise out of the free-tier quota.

The sampler must never raise — the SDK falls back to `traces_sample_rate` when
it does, and that option is deliberately unset (traces_sampler and
traces_sample_rate are mutually exclusive), so a raise means no sampling
decision at all.
"""
from fastapi import HTTPException

from apps.backend.app.main import before_send, traces_sampler
from apps.backend.app.services.errors import NotConfiguredError


def _ctx(path):
    """Minimal stand-in for the sampling context the ASGI integration builds.

    sentry_sdk/integrations/asgi.py passes the raw ASGI scope through as
    `asgi_scope`; `path` is the only key the sampler reads.
    """
    return {'asgi_scope': {'type': 'http', 'path': path}}


def test_health_check_is_dropped():
    # Render polls this as the service health check — pure noise.
    assert traces_sampler(_ctx('/api/health')) == 0


def test_static_asset_requests_are_dropped():
    # The GCS image proxy serves many requests per page view.
    assert traces_sampler(_ctx('/static/plants/tomato.jpg')) == 0


def test_normal_api_requests_are_sampled():
    assert traces_sampler(_ctx('/api/gardens')) == 0.1


def test_health_prefix_is_not_over_matched():
    # Only the exact health path is dropped; a real route that merely starts
    # with the same characters must still be traced.
    assert traces_sampler(_ctx('/api/healthscore')) == 0.1


def test_missing_asgi_scope_does_not_raise():
    # Non-HTTP transactions (the APScheduler jobs) have no ASGI scope.
    assert traces_sampler({}) == 0.1


def test_scope_without_path_does_not_raise():
    assert traces_sampler({'asgi_scope': {}}) == 0.1


# ── before_send ───────────────────────────────────────────────────────────────
# Production deliberately runs without ANTHROPIC_API_KEY / PERENUAL_API_KEY. The
# endpoints answer 5xx, which the Starlette integration reports by default, so
# every probe opened an issue for a correctly-configured system (three of them
# on 2026-07-27, from the E2E suite).

def _hint(exc):
    return {'exc_info': (type(exc), exc, None)}


def test_not_configured_is_dropped():
    exc = NotConfiguredError(status_code=503, detail='no ANTHROPIC_API_KEY')
    assert before_send({'event_id': 'x'}, _hint(exc)) is None


def test_real_http_error_is_kept():
    # A genuine upstream failure must still reach Sentry.
    event = {'event_id': 'x'}
    assert before_send(event, _hint(HTTPException(status_code=502, detail='boom'))) is event


def test_unrelated_exception_is_kept():
    event = {'event_id': 'x'}
    assert before_send(event, _hint(ValueError('boom'))) is event


def test_missing_hint_does_not_raise():
    # Log-derived events carry no exc_info; losing them would be a regression.
    event = {'event_id': 'x'}
    assert before_send(event, {}) is event
    assert before_send(event, None) is event
