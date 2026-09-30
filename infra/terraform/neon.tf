# neon.tf — the live Postgres database (Phase 2).
#
# One `neon_project` resource covers five Neon objects: the project, its root
# branch, the primary compute (endpoint ep-crimson-star-aitjy8am), the default
# database (neondb) and the default role (neondb_owner). Everything the app
# stores lives in here, so this phase is more dangerous than Phase 1.
#
# DANGER — read before every apply in this phase:
# some arguments (region_id, pg_version, org_id...) can't be changed in place.
# If the code disagrees with reality on one of them, Terraform plans
# `-/+ destroy and then create replacement`: that would DELETE THE DATABASE.
# `prevent_destroy` below turns that plan into an error instead, but still read
# every plan line by line. Same golden rule as Phase 1: fix the code, not the
# cloud.

resource "neon_project" "garden" {
  # Values copied from the live project (Neon API, 2026-09-30).
  name       = "GardenApp"
  org_id     = "org-shy-boat-24481895"
  region_id  = "aws-us-east-1" # same region as Render (virginia) and the image bucket
  pg_version = 18

  # Point-in-time restore window: 6 hours. That's the free-plan maximum; the
  # provider's default (1 day) would be rejected or would change the plan.
  history_retention_seconds = 21600

  # Neon keeps role passwords so the console can show connection strings.
  store_password = "yes"

  # Defaults for NEW computes. Existing computes aren't touched by these.
  autoscaling_limit_min_cu = 0.25
  autoscaling_limit_max_cu = 2
  suspend_timeout_seconds  = 0 # 0 = Neon's global default (suspend after 5 min idle)

  lifecycle {
    prevent_destroy = true
  }
}
