# Garden Planning App

A Python-based garden planning application. Plan beds, track plants, manage tasks, and browse a plant library — all from a local web interface.

## Stack

- **Backend:** Python + Flask + SQLAlchemy + SQLite
- **Frontend:** Jinja2 templates + Vanilla JS (no build step)
- **Package manager:** [uv](https://github.com/astral-sh/uv)

## Repo Structure

```
gardening_app/
├── apps/
│   ├── api/                    # Flask backend
│   │   ├── app/
│   │   │   ├── main.py         # App factory (create_app)
│   │   │   └── db/models.py    # SQLAlchemy models
│   │   ├── static/             # CSS, JS, plant images
│   │   ├── templates/          # Jinja2 HTML templates
│   │   ├── instance/           # SQLite database (gitignored)
│   │   └── wsgi.py             # WSGI entry point
│   ├── web/                    # React/Next.js frontend (stub)
│   └── ml_service/             # ML inference service (stub)
├── ml/                         # Training pipelines (stub)
├── scripts/                    # One-off data scripts
├── data/                       # Sample data and schemas
├── infra/                      # Docker, Terraform, K8s (stub)
├── notebooks/                  # Exploratory notebooks
└── tests/                      # Unit, integration, data tests
```

## Setup

**Install dependencies:**
```bash
uv sync
```

Or with pip:
```bash
pip install -r requirements.txt
```

## Running the App

```bash
# macOS / Linux
FLASK_APP=apps/api/wsgi.py FLASK_DEBUG=1 uv run flask run

# Windows PowerShell
$env:FLASK_APP="apps/api/wsgi.py"; $env:FLASK_DEBUG="1"; uv run flask run

# Windows CMD
set FLASK_APP=apps/api/wsgi.py && set FLASK_DEBUG=1 && uv run flask run
```

Or use the Makefile:
```bash
make run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Features

- **Gardens** — create and manage multiple gardens with location and zone info
- **Beds** — add raised beds with dimensions, soil notes, and a grid plant layout
- **Planner** — drag-and-drop visual planner for arranging beds in a garden
- **Plants** — track individual plants with status, dates, and task history
- **Plant Library** — 80+ plants with spacing, sunlight, water, and companion planting data
- **Tasks** — create and complete garden tasks linked to plants, beds, or gardens

## Data Scripts

One-off scripts for enriching the plant library. Run from the repo root:

```bash
uv run python scripts/supplement_library.py      # Enrich plants via Perenual API
uv run python scripts/permapeople_sync.py         # Bulk sync from Permapeople API
uv run python scripts/backfill_images_wiki.py     # Download plant images (Wikimedia + Pexels)
uv run python scripts/populate_plant_details.py   # Populate extended plant details
```

Requires API keys in `.env` — see `.env.example` (or set `PERENUAL_API_KEY`, `PEXELS_API_KEY`, `X-Permapeople-Key-Id`, `X-Permapeople-Key-Secret`).

## Resetting the Database

Stop Flask first, then delete the database:

```bash
# macOS / Linux
rm apps/api/instance/garden.db

# Windows
python -c "import os; os.remove('apps/api/instance/garden.db')"
```

Restart Flask — it will recreate the schema and re-seed the plant library automatically.
