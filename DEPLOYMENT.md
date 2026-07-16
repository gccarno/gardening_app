# Deployment Guide — Cloud Sync with Neon + Render + GCS

This guide takes the app from "runs on my PC" to "web + Android sync from
anywhere". Total cost: **$0/month** except pennies for image storage.

Architecture:

```
 Browser ──────┐
               ├──► Render (FastAPI + built React SPA, free tier)
 Android app ──┘          │                       │
                          ▼                       ▼
                   Neon Postgres          Google Cloud Storage
                   (garden data)          (plant images, PRIVATE bucket —
                                           only the server's key can read it)

 GitHub Actions cron ──► /api/admin/run-* endpoints (nightly weather fetch;
                         also wakes Render + Neon from idle)
```

The big picture: your data lives in two cloud places (Neon = database rows,
GCS = image files), and Render runs the same FastAPI process you run locally
with `uvicorn` — just on a Linux box that's always reachable. Nothing about
the app code changes between local and cloud; env vars flip the behavior.

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

### What "free tier suspends compute after ~5 min" means

Neon splits a database into two independent parts:

- **Storage** — your actual data on disk. This is *never* suspended; your
  rows are always safe whether or not anything is running.
- **Compute** — the Postgres *process* that answers queries. Running a
  process costs Neon CPU/RAM, so on the free tier they shut it down after
  about 5 minutes with no queries. This is called **autosuspend** (or
  "scale to zero").

What you experience:

1. You open the app after a break. The first query finds no running Postgres.
2. Neon cold-starts one (~500 ms–2 s), attaches your storage, then answers.
3. Every query after that is fast again — until the next 5-minute idle gap.

Two visible symptoms in your own logs, both normal:

- `SLOW GET /api/gardens — 1130ms` on the *first* request after you've been
  away — that ~1 s is the Neon compute waking up, not your code being slow.
- Suspension also drops open TCP connections. SQLAlchemy would normally
  crash with "connection closed unexpectedly" on the next query; the app
  avoids that with `pool_pre_ping=True` in
  `apps/backend/app/db/session.py` — before reusing a pooled connection it
  sends a tiny "are you alive?" ping and transparently reconnects if not.

You never lose data from autosuspend, and you don't have to do anything —
it's purely a first-request latency tradeoff that makes the free tier free.

Other notes:
- Neon keeps ~24 h of point-in-time restore history on the free tier, which
  replaces the old SQLite GCS backup for disaster recovery.

## 2. Google Cloud Storage (images) — private bucket, pennies/month

The plant image tree (`apps/api/static/`, ~5.6 GB of originals) is too big
for any free-tier host's disk, so images live in a GCS bucket — you've
created `garden-app-static` (hyphens — bucket names are exact; passing
`garden_app_static` gets "bucket does not exist"). The bucket stays
**private**: do NOT grant
`allUsers` access, and leave **Public Access Prevention ON** (the default,
"Enforce public access prevention" checked).

### How private access works (and why it's secure)

Every request to a private bucket must be signed by a Google credential that
has been granted a role on that bucket. There are exactly two credentials in
play:

- **You**, via `gcloud auth login` on your PC — as project owner you can
  upload/browse with `gsutil` and the Cloud Console.
- **A service account** — a robot Google identity whose private key lives in
  a JSON file. The server (Render, or your PC when testing) loads it via the
  `GOOGLE_APPLICATION_CREDENTIALS` env var and uses it to read/write objects.

Nobody else can read a single byte: an unauthenticated request to
`storage.googleapis.com/garden-app-static/...` gets `403 Forbidden`. There is
no URL-guessing risk, no crawler risk, and no "random people run up my bill"
risk — access requires the key file, which exists only on your PC and in
Render's encrypted secret-file store.

How the app serves images without making the bucket public: in the cloud the
backend **proxies** them. The browser/Android app requests
`/static/plant_images/123.jpg` from *your app*; FastAPI fetches the object
from GCS using the service-account key and streams it back
(`static_gcs_proxy` in `apps/backend/app/main.py`). The response carries
`Cache-Control: public, max-age=31536000, immutable`, so after the first
view each device keeps a local copy (browser HTTP cache; Coil's disk cache on
Android) and never re-downloads it — that's your "cache on the local device"
requirement, and it also minimizes GCS egress charges.

(For contrast: "enabling public access" would mean granting the role
`Storage Object Viewer` to the special principal `allUsers` — literally
anyone on the internet. That's the standard setup for public websites, and
downloads by strangers would bill *you* for egress. You don't need it and
shouldn't enable it.)

### Setup

1. Bucket `garden-app-static` — already created. Keep public access
   prevention **on**.
2. Create the robot identity: Console → IAM & Admin → **Service Accounts** →
   Create (name e.g. `garden-app-server`) — done: `garden-app-server@innate-conquest-491313-k3.iam.gserviceaccount.com`.
   No project-level roles needed.
3. Grant it access to just this bucket (done 2026-07-12) — either in the
   Console (bucket → **Permissions** → Grant access, role
   **Storage Object Admin**: read + write, needed for photo uploads) or:

   ```
   gcloud storage buckets add-iam-policy-binding gs://garden-app-static \
     --member="serviceAccount:garden-app-server@innate-conquest-491313-k3.iam.gserviceaccount.com" \
     --role="roles/storage.objectAdmin"
   ```

   Without this grant the script fails with
   `403 ... does not have storage.objects.list access`.
4. Create a key: Service account → **Keys** → Add key → JSON. Download it
   somewhere outside the repo (never commit it). Yours:
   `C:/Users/gccar/.config/gcloud/innate-conquest-491313-k3-5d0471b26ab3.json`.
5. Upload one primary image per plant, downscaled (see below):

   ```bash
   # Git Bash
   export GOOGLE_APPLICATION_CREDENTIALS="C:/Users/gccar/.config/gcloud/innate-conquest-491313-k3-5d0471b26ab3.json"
   uv run python scripts/upload_primary_images_gcs.py --bucket garden-app-static --dry-run
   uv run python scripts/upload_primary_images_gcs.py --bucket garden-app-static
   ```

   ```powershell
   # PowerShell
   $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\gccar\.config\gcloud\innate-conquest-491313-k3-5d0471b26ab3.json"
   uv run python scripts/upload_primary_images_gcs.py --bucket garden-app-static --dry-run
   uv run python scripts/upload_primary_images_gcs.py --bucket garden-app-static
   ```

   The script is resumable — it skips objects already in the bucket, so you
   can rerun it any time (e.g. after adding plants).

With `GCS_STATIC_BUCKET=garden-app-static` set on the server, new image
uploads go to the bucket and `/static/...` is proxied from it. Locally
(unset), everything keeps using the on-disk tree — you don't need GCS at all
for local use.

### Keeping storage costs down

`scripts/upload_primary_images_gcs.py` minimizes the bill three ways:

- **One image per plant** — only each plant's primary image (~9.5k files),
  not all 30k gallery images. (Tradeoff: in the cloud, the library detail
  gallery shows just the primary image. Locally you still see everything.)
- **Downscaled** — originals are resized so the longest side is 800 px
  (plenty for the UI), turning ~5.6 GB into well under 1 GB. At ~$0.02/GB/mo
  that's a few cents a month.
- **Downloaded at most once per device** — lazy loading + immutable caching:
  an image is only fetched when it appears on screen, and then cached
  locally forever.

Why not a `.zip`? Two reasons. JPEGs are already compressed, so zipping
saves ~1% — nothing. Worse, an archive is one object: to display one photo
the app would have to download (or the server hold open) the whole archive,
which *defeats* lazy loading. Separate objects + lazy fetch + device caching
achieves the goal the zip was aiming at, cheaper.

## 3. Render (backend + web) — free tier

### What Render is

Render is a hosting company: it runs your server program on their Linux
machines, 24/7, with a public HTTPS URL. Today the FastAPI process runs only
while your PC is on and only reachable at `127.0.0.1`. After deploying,
the *same process* runs on Render's machine at
`https://garden-app-wa0b.onrender.com`, so your phone can reach it from
anywhere.

What Render does on each deploy, per `render.yaml` in the repo root (a
"Blueprint" — infrastructure described in a file instead of clicked together):

1. Pulls your GitHub repo (and auto-redeploys on every push to `main`).
2. Builds the React app (`npm run build`) and installs Python deps.
3. Starts `uvicorn` with your env vars (`DATABASE_URL`, etc.) injected.
4. Terminates HTTPS and forwards requests to your process.

So: **Neon stores your data, GCS stores your images, Render runs your code.**

### Render + the private bucket

Render works fine with the private bucket — it's actually the piece that
makes "private" workable. You give Render the service-account JSON as a
**Secret File**; your FastAPI process uses it to read images from GCS and
proxy them to your browser/phone (section 2). The bucket never needs public
access, and strangers can't pull from your bucket, so they can't run up GCS
egress charges.

One honest caveat: the Render *app URL itself* is on the public internet.
All garden data APIs require login (bearer token), so your data is safe. The
proxied `/static/*` images are servable without login (image tags can't send
auth headers) — but someone would have to know your Render URL *and* guess
image filenames, and the worst case is they see a picture of a tomato. If
even that bothers you, the fix is Render's $7/mo tier + Cloudflare Access in
front, which is overkill for this app.

### Setup

1. Push this repo to GitHub if it isn't already.
2. Sign up at [render.com](https://render.com) → New → **Blueprint** → connect
   the repo. Render reads `render.yaml`.
3. Set the secret env vars when prompted:
   - `DATABASE_URL` — the Neon URL from step 1
   - `GCS_STATIC_BUCKET` — `garden-app-static`
4. Add the GCS key as a **Secret File** named `gcs-service-account.json`
   (Service → Environment → Secret Files); the blueprint already points
   `GOOGLE_APPLICATION_CREDENTIALS` at `/etc/secrets/gcs-service-account.json`.
5. Deploy. The build compiles the React app; FastAPI serves it at the root
   URL (ours is `https://garden-app-wa0b.onrender.com`).

Free-tier caveats:
- The service **spins down after 15 min idle** (same idea as Neon's
  autosuspend, but for your app process); the first request afterwards takes
  ~30–60 s (cold start). Fine for personal use. $7/month (Starter) removes
  this and would also let you re-enable `ENABLE_SCHEDULER=1` and skip
  section 4 below.
- Free tier includes 100 GB/month bandwidth — proxying images counts against
  it, but with device caching (each image transferred once per device) a
  single-family app won't get near that.

## 4. GitHub Actions (nightly jobs)

In-process cron can't fire on a host that's asleep, so
`.github/workflows/scheduled-jobs.yaml` pokes the app from GitHub's servers
every night at 07:00 UTC: it calls `/api/admin/run-weather-fetch` and
`/api/admin/run-backup`, authenticated by a shared secret header
(`X-Job-Token`). The request itself also wakes Render and Neon from idle.

1. Repo → Settings → Secrets and variables → Actions → add:
   - `APP_URL` — your Render URL: `https://garden-app-wa0b.onrender.com`.
     **Careful:** the unsuffixed `https://garden-app.onrender.com` is someone
     else's site — using it makes the nightly job fail with curl exit 22.
   - `JOB_TOKEN` — copy the value Render generated (Service → Environment)
2. Done — it runs nightly and can be run manually from the Actions tab
   (workflow_dispatch).

**Why it was failing every night:** the workflow was already committed and
scheduled, but the `APP_URL`/`JOB_TOKEN` secrets were never set (there's no
Render deployment yet). GitHub passed empty strings, `curl` was asked to POST
to the malformed URL `/api/admin/run-weather-fetch`, and exited with code 3
("URL malformed") — a red ❌ every night. The workflow now checks for the
secrets first and skips green, with a notice, until you finish this section.

## 5. Android app

For the full beginner walkthrough — installing Android Studio, running on
the emulator, putting the app on your real phone — see
**[`android/BUILD.md`](android/BUILD.md)**. The short version:

1. Install **Android Studio** from
   [developer.android.com/studio](https://developer.android.com/studio)
   (big download, ~an hour first time including SDKs — accept the defaults).
2. **Open** (not "New Project") the `android/` folder of this repo and wait
   for the bottom status bar to finish "Gradle sync" (first time: several
   minutes; it downloads all the libraries).
3. Plug in your phone with USB debugging enabled (Settings → About phone →
   tap **Build number** 7× → Developer options → **USB debugging**), then
   press the green ▶ Run button. Android Studio builds the app, installs it
   on the phone, and launches it.
4. To install without a cable: **Build → Build APK(s)**, then copy
   `android/app/build/outputs/apk/debug/app-debug.apk` to the phone (Google
   Drive or USB) and tap it to install ("allow unknown apps" when prompted).
   For a personal app the *debug* build is all you need — "release" builds
   only matter for the Play Store and require signing-key setup.
5. Point the app at the cloud: open the app → **Settings** → set the server
   URL to your Render URL (`https://garden-app-wa0b.onrender.com`) → Save. Log in
   with the same account as the web app; everything syncs because both talk
   to the same backend.

Note: release builds are HTTPS-only (`network_security_config.xml`); debug
builds also allow `http://` for the emulator (`http://10.0.2.2:8000` reaches
`localhost:8000` on your PC) and home-LAN development.

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
| `GCS_STATIC_BUCKET` | Render | private bucket for `/static` images |
| `GOOGLE_APPLICATION_CREDENTIALS` | Render secret file | GCS service-account key (read/write on the bucket) |
| `JOB_TOKEN` | Render + GH secret | guards `/api/admin/run-*` |
| `ENABLE_SCHEDULER` | Render (`0`) | disable in-process cron on free tier |
| `CORS_ORIGINS` | optional | comma-separated origins if web is hosted separately |
| `ANTHROPIC_API_KEY` | Render + local | photo plant/pest ID |
