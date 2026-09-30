# variables.tf — inputs to the configuration.
#
# Concept: variables keep values that might change (or differ between
# environments) out of the resource blocks. Reference them as var.<name>.
# Override a default with `-var region=...` or a gitignored *.tfvars file.
# Nothing secret belongs here — defaults are committed to git.

variable "project_id" {
  description = "GCP project that owns the garden app's buckets and service account."
  type        = string
  default     = "innate-conquest-491313-k3"
}

variable "region" {
  description = "Default region. The image bucket lives in us-east1, next to Neon (aws-us-east-1) and Render (virginia)."
  type        = string
  default     = "us-east1"
}
