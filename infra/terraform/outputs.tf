# outputs.tf — values Terraform prints after apply (`terraform output` shows
# them again). Later phases will also read outputs from other providers, e.g.
# wiring Neon's connection string into a GitHub Actions secret.

output "static_bucket" {
  description = "Value for GCS_STATIC_BUCKET on Render."
  value       = google_storage_bucket.static.name
}

output "server_service_account" {
  description = "Identity the Render service uses (its JSON key lives in Render's secret files)."
  value       = google_service_account.server.email
}

output "tfstate_bucket" {
  description = "Where Terraform state lives after step 1d."
  value       = google_storage_bucket.tfstate.name
}

# ── Phase 2: Neon ──────────────────────────────────────────────────────────
output "neon_project_id" {
  value = neon_project.garden.id
}

output "neon_database_host" {
  description = "Direct (non-pooled) host, e.g. ep-crimson-star-aitjy8am.c-4.us-east-1.aws.neon.tech."
  value       = neon_project.garden.database_host
}

# Concept: `sensitive = true`. Terraform hides this value in plan/apply output
# and in the bare `terraform output` listing (it prints "<sensitive>"). That is
# display-only: `terraform output neon_connection_uri` (with or without -raw)
# PRINTS THE PASSWORD. It is also NOT hidden in the state file: state stores the full password in plain
# text. That's why state lives in a private bucket and never in git. Phase 4
# feeds this value into the DATABASE_URL GitHub Actions secret.
output "neon_connection_uri" {
  description = "postgresql://... connection string for neondb_owner, including the password."
  value       = neon_project.garden.connection_uri
  sensitive   = true
}
