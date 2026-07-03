# Deployment Guide — Cloud Sync with Neon + Render + GCS

This guide takes the app from "runs on my PC" to "web + Android sync from
anywhere". Total cost: **$0/month** except ~$0.12/month for image storage.

Architecture:

```
 Browser ──────┐
               ├──► Render (FastAPI + built React SPA, free tier)
 Android app ──┘          │                    │
                          ▼                    ▼
                   Neon Postgres        Google Cloud Storage
                   (garden data)        (5.6 GB plant images, public bucket)

 GitHub Actions cron ──► /api/admin/run-* endpoints (nightly weather/backup;
                         also wakes Render + Neon from idle)
```

---

## 1. Neon (database) — free tier

1. Sign up at [neon.tech](https://neon.tech) and create a project (pick the
   region closest to you; e.g. `aws-us-east-2`).
2. In the project dashboard, copy the **connection string** and convert it to
   the SQLAlchemy form by changing the scheme to `postgresql+psycopg://`:

   ```
   postgresql+psycopg://USER:PASSWORD@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

3. Migrate your data (from this repo, with your local SQLite as source):

   ```powershell
   uv run python scripts/migrate_sqlite_to_postgres.py --target "postgresql+psycopg://...&sslmode=require"
   ```

   The script creates the schema, refuses to overwrite non-empty targets,
   copies all ~15k rows in FK order, and resets sequences. Tip: test against a
   **Neon branch** first (Branches → New branch — free) and throw it away.

4. Verify locally before deploying: set `DATABASE_URL` in `.env` to the Neon
   URL, start the backend (`uv run uvicorn apps.backend.app.main:app`), and
   click around. Unset it to go back to SQLite.

Notes:
- Free tier suspends compute after ~5 min idle; the app handles this
  (`pool_pre_ping`) — the first request after a suspend takes ~1–2 s.
- Neon keeps ~24 h of point-in-time restore history on the free tier, which
  replaces the old SQLite GCS backup for disaster recovery.

## 2. Google Cloud Storage (images) — ~$0.12/month

The plant image tree (`apps/api/static/`, ~5.6 GB) is too big for any
free-tier host's disk, so it lives in a public GCS bucket.

1. In [console.cloud.google.com](https://console.cloud.google.com), create a
   bucket, e.g. `garden-app-static` (region: same as Neon; storage class:
   Standard; **uncheck** "Enforce public access prevention").
2. Grant public read: bucket → Permissions → Grant access →
   principal `allUsers`, role `Storage Object Viewer`.
3. Upload the static tree (one-time, uses your existing gcloud credentials):

   ```powershell
   gsutil -m rsync -r apps/api/static gs://garden-app-static/static
   ```

4. Create a service account key for uploads from the server (you likely
   already have one for the GCS backups — reuse it, adding the
   `Storage Object Admin` role on this bucket). Download the JSON key.

With `GCS_STATIC_BUCKET=garden-app-static` set on the server, new image
uploads go to the bucket and `/static/...` URLs redirect there. Locally
(unset), everything keeps using the on-disk tree.

## 3. Render (backend + web) — free tier

1. Push this repo to GitHub if it isn't already.
2. Sign up at [render.com](https://render.com) → New → **Blueprint** → connect
   the repo. Render reads `render.yaml`.
3. Set the secret env vars when prompted:
   - `DATABASE_URL` — the Neon URL from step 1
   - `GCS_STATIC_BUCKET` — e.g. `garden-app-static`
4. Add the GCS key as a **Secret File** named `gcs-service-account.json`
   (Service → Environment → Secret Files); the blueprint already points
   `GOOGLE_APPLICATION_CREDENTIALS` at `/etc/secrets/gcs-service-account.json`.
5. Deploy. The build compiles the React app; FastAPI serves it at the root
   URL (e.g. `https://garden-app.onrender.com`).

Free-tier caveats:
- The service **spins down after 15 min idle**; the first request afterwards
  takes ~30–60 s (cold start). Fine for personal use. $7/month (Starter)
  removes this and would also let you re-enable `ENABLE_SCHEDULER=1` and skip
  step 4 below.

## 4. GitHub Actions (nightly jobs)

In-process cron can't fire on a host that's asleep, so
`.github/workflows/scheduled-jobs.yaml` triggers the jobs remotely.

1. Repo → Settings → Secrets and variables → Actions → add:
   - `APP_URL` — your Render URL, e.g. `https://garden-app.onrender.com`
   - `JOB_TOKEN` — copy the value Render generated (Service → Environment)
2. Done — it runs daily at 07:00 UTC and can be run manually from the
   Actions tab (workflow_dispatch).

## 5. Android app

1. Open the app → **Settings** → set the server URL to your Render URL
   (`https://garden-app.onrender.com`).
2. Release builds are HTTPS-only (`network_security_config.xml`); debug builds
   still allow `http://` for the emulator and home-LAN development.

## 6. Photo plant/pest ID (external API)

The identify feature uses Claude vision. Set on the server (and in local
`.env` if you want it locally):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at [console.anthropic.com](https://console.anthropic.com) (pay per
use; a plant ID photo costs well under a cent). Without the key the identify
endpoints return a clear "not configured" error; the rest of the app is
unaffected.

## Environment variable reference

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | Render + local `.env` (optional) | Neon Postgres URL; unset = local SQLite |
| `GARDEN_DB_PATH` | local only | override SQLite file path |
| `GCS_STATIC_BUCKET` | Render | public bucket for `/static` images |
| `GOOGLE_APPLICATION_CREDENTIALS` | Render secret file | GCS upload credentials |
| `JOB_TOKEN` | Render + GH secret | guards `/api/admin/run-*` |
| `ENABLE_SCHEDULER` | Render (`0`) | disable in-process cron on free tier |
| `CORS_ORIGINS` | optional | comma-separated origins if web is hosted separately |
| `ANTHROPIC_API_KEY` | Render + local | photo plant/pest ID |
