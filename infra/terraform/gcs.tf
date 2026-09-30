# gcs.tf — the Google Cloud resources the live app already uses.
#
# All three were created by hand in July 2026 (see DEPLOYMENT.md §2). The
# `import {}` blocks below tell Terraform "this block describes an object that
# ALREADY EXISTS — adopt it, don't create a new one". They were applied on
# 2026-09-30 and then deleted (LEARNING.md 1e) — the objects are in state now.
#
# Golden rule while importing: if `terraform plan` wants to CHANGE one of these,
# the code is wrong, not the cloud. Edit the HCL until the plan shows only
# "import" for them.

# ── The private image bucket ────────────────────────────────────────────────

resource "google_storage_bucket" "static" {
  name     = "garden-app-static"
  location = "US-EAST1" # immutable — changing it would mean delete + recreate

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true       # IAM only, no per-object ACLs
  public_access_prevention    = "enforced" # the app proxies images; bucket is never public

  soft_delete_policy {
    retention_duration_seconds = 604800 # 7 days (GCS default)
  }

  # Found by the first `terraform plan`: Google set these on the bucket itself
  # (the CSEK restriction took effect 2 minutes after creation, i.e. a platform
  # default, not something we chose). They govern which encryption types NEW
  # objects may use: Google-managed and customer-managed (KMS) keys allowed,
  # customer-supplied keys blocked. The app only uses Google-managed encryption.
  # Omitting this block made Terraform plan to REMOVE the settings — so we copy
  # reality into code instead.
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

  lifecycle {
    # Concept: a safety catch. Any plan that would destroy this bucket (e.g.
    # someone edits `location`) errors out instead. ~30k plant images live here.
    prevent_destroy = true
  }
}

# ── The robot identity the Render service uses to read/write images ─────────

resource "google_service_account" "server" {
  account_id   = "garden-app-server"
  display_name = "garden-app-server"
  description  = "interact with garden app image bucket"
}

# NOT managed here on purpose: the service account's JSON key. A
# google_service_account_key resource would write the private key into
# Terraform state. The key stays where it is — Render's secret files.

# ── Bucket-level grant: the robot may read + write objects in this bucket ───
# Concept: resource references. `google_storage_bucket.static.name` and
# `google_service_account.server.member` are attributes of other blocks, so
# Terraform knows to handle those first (the dependency graph).
#
# `_iam_member` is *additive*: it manages exactly this one role/member pair and
# leaves any other grants on the bucket alone. The `_iam_binding` / `_iam_policy`
# variants are *authoritative* and would remove grants not listed in code.

resource "google_storage_bucket_iam_member" "server_object_admin" {
  bucket = google_storage_bucket.static.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.server.member
}
