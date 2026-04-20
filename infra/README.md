# Infrastructure

This is a local-first, single-user application — it requires no cloud infrastructure to run. The backend is a single `uvicorn` process and the database is a SQLite file.

No Docker, Terraform, or Kubernetes configuration is provided or needed for standard use.

If you want to self-host on a server:

1. Build the frontend: `cd apps/web && npm run build`
2. Run the backend: `uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --port 8000`
3. The FastAPI app serves the built React SPA and all `/api` routes from one process.
