# Infrastructure

The app runs locally with no cloud at all: one `uvicorn` process that serves
the React SPA and `/api`. The hosted version uses four services. See
[DEPLOYMENT.md](../DEPLOYMENT.md) for the full walkthrough.

| Service | What it holds | Managed by |
|---|---|---|
| Render | the web service (`garden-app-wa0b`) | [`render.yaml`](../render.yaml) Blueprint |
| Google Cloud Storage | the private image bucket `garden-app-static`, plus its service account and IAM grant | [`terraform/gcs.tf`](terraform/gcs.tf) (phase 1) |
| Neon | Postgres (project `dark-flower-13876828`) | [`terraform/neon.tf`](terraform/neon.tf) (phase 2) |
| Sentry | error tracking + cron monitors | dashboard / SDK; Terraform planned (phase 3) |
| GitHub Actions | cron workflows + secrets | workflow YAML; secrets via Terraform planned (phase 4) |

## Terraform

`terraform/` is being built up phase by phase as a learning project. Start with
[terraform/LEARNING.md](terraform/LEARNING.md). State lives in the private,
versioned bucket `gs://innate-conquest-491313-k3-tfstate`.

`docker/` and `k8s/` hold older container/Kubernetes experiments. The live deployment doesn't use them.
