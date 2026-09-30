# versions.tf — WHAT Terraform and WHICH providers this configuration needs.
#
# Concept: a *provider* is a plugin that knows how to talk to one API (Google
# Cloud, Neon, GitHub...). `terraform init` downloads the providers listed here
# into .terraform/ and records the exact versions + checksums in
# .terraform.lock.hcl. Commit the lock file — it's what makes `init` on another
# machine pick identical provider builds.

terraform {
  # 1.5+ is required for the `import {}` blocks used in gcs.tf.
  required_version = ">= 1.5"

  required_providers {
    google = {
      source = "hashicorp/google"
      # "~> 8.4" means ">= 8.4, < 9.0": accept bug-fix/feature releases, never
      # a new major version (majors can rename or remove arguments).
      version = "~> 8.4"
    }
    neon = {
      # Community provider — Neon has no official one; this is the provider
      # Neon's own docs point to.
      source = "kislerdm/neon"
      # 0.x versions make no stability promise, so "~> 0.18.0" is tighter than
      # the google pin: it allows 0.18.x patch releases only (>= 0.18.0, < 0.19).
      version = "~> 0.18.0"
    }
  }

  # ── Remote state (LEARNING.md step 1d) ─────────────────────────────────────
  # Concept: *state* is Terraform's record of which real object each resource
  # block maps to. By default it lives in ./terraform.tfstate on your PC.
  # Chicken-and-egg: the bucket that will hold the state is itself created by
  # this configuration (state.tf), so it has to exist before we can point the
  # backend at it. Leave this commented out for the first apply, then
  # uncomment it and run `terraform init -migrate-state`.
  #
  backend "gcs" {
    bucket = "innate-conquest-491313-k3-tfstate"
    prefix = "garden-app"
  }
}
