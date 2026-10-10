# sentry.tf — error tracking for the backend (Phase 3).
# Imported 2026-10-10. The project's DSN (client key) is deliberately not
# managed here; it lives in Render's SENTRY_DSN env var.

resource "sentry_project" "backend" {
  name         = "garden-app-backend"
  organization = "greg-ei"
  platform     = "python-fastapi"
  resolve_age  = 0 # 0 = never auto-resolve saves the next reader a trip to the docs.
  slug         = "garden-app-backend"
  teams        = ["greg"]
}

