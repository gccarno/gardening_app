# providers.tf — HOW the google provider connects.
#
# Credentials are deliberately NOT configured here. The provider falls back to
# Application Default Credentials, i.e. your own Google login from
#   gcloud auth application-default login
# That keeps keys out of the repo, and means Terraform acts as *you* (project
# owner) — not as the app's garden-app-server robot, which only has access to
# one bucket.

provider "google" {
  project = var.project_id
  region  = var.region
}

