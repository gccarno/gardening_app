"""Sentry trace sampling: keep high-volume noise out of the free-tier quota.

The sampler must never raise — the SDK falls back to `traces_sample_rate` when
it does, and that option is deliberately unset (traces_sampler and
traces_sample_rate are mutually exclusive), so a raise means no sampling
decision at all.
"""
from apps.backend.app.main import traces_sampler


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
