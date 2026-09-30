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

