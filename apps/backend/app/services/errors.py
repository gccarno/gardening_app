"""Error types that carry Sentry-reporting intent alongside the HTTP response."""
from fastapi import HTTPException


class NotConfiguredError(HTTPException):
    """An optional integration has no API key on this deployment.

    Behaves exactly like the HTTPException it replaces — same status, same
    detail, same response body. The only difference is that `before_send` in
    main.py drops these before they reach Sentry.

    They are a deployment choice, not a fault: production deliberately runs
    without ANTHROPIC_API_KEY and PERENUAL_API_KEY, so every probe of those
    endpoints opened a Sentry issue for a system behaving exactly as
    configured. The E2E suite probes all three on every run, which is how
    three such issues appeared on 2026-07-27.
    """
