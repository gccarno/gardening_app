# state.tf — the bucket that will hold Terraform's own state file.
#
# The first resource this configuration CREATES (everything in gcs.tf is
# imported). Once it exists, versions.tf's `backend "gcs"` block moves state
# here (LEARNING.md step 1d).
#
# Why remote state at all: the local terraform.tfstate is easy to lose, can't be
# shared with CI, and — once Neon/GitHub are managed (phases 2 and 4) — contains
# secrets. So this bucket is private and versioned (every state write keeps the
# previous copy, so a bad apply can be rolled back).

resource "google_storage_bucket" "tfstate" {
  name     = "${var.project_id}-tfstate" # bucket names are global; prefixing with the project id avoids collisions
  location = "US-EAST1"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  # Same encryption enforcement Google applied by default to garden-app-static
  # (see gcs.tf). Declaring it up front means the post-create plan stays clean
  # instead of showing drift when Google applies its default.
  encryption {
    google_managed_encryption_enforcement_config {
      restriction_mode = "NotRestricted"
    }
    customer_managed_encryption_enforcement_config {
      restriction_mode = "NotRestricted"
    }
    customer_supplied_encryption_enforcement_config {
      restriction_mode = "FullyRestricted"
    }
  }

  # Keep the 10 most recent non-current state versions; older ones are deleted.
  lifecycle_rule {
    condition {
      num_newer_versions = 10
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
