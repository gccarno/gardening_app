# Garden Planner

A local-first web application for planning vegetable and herb gardens. Track beds, plants, and tasks; get AI-powered planting advice and weather-aware watering recommendations; and browse a reference library of ~9,000 plants.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture Overview](#architecture-overview)
- [Directory Structure](#directory-structure)
- [Setup and Running](#setup-and-running)
- [Features](#features)
  - [Garden & Bed Management](#garden--bed-management)
  - [Visual Planner](#visual-planner)
  - [Plant Library](#plant-library)
  - [AI Garden Assistant](#ai-garden-assistant)
  - [Plant Recommender](#plant-recommender)
  - [Predictive Watering Engine](#predictive-watering-engine)
- [Data Model](#data-model)
- [AI & ML System](#ai--ml-system)
- [API Routes](#api-routes)
- [Design Decisions](#design-decisions)
- [Resetting the Database](#resetting-the-database)
- [Environment Variables](#environment-variables)

---

## What It Does

Garden Planner is a personal garden management tool that runs entirely on your local machine — no cloud account or subscription required. You describe your garden (location, beds, soil), and the app helps you:

- **Plan** — drag beds around a canvas, assign plants to grid cells, visualise spacing
- **Track** — log what you planted, when, and in which bed; mark tasks done
- **Decide** — get plant recommendations tuned to your zone, season, and soil
- **Ask** — chat with an AI assistant that can look up real data from your garden (beds, plants, tasks, weather) and take actions like adding plants or creating reminders
- **Water wisely** — a watering engine combines rainfall history and weather forecasts to tell you which beds actually need water today

---

## Architecture Overview

```
Browser
  │  React SPA (Vite + TypeScript)
  │  http://localhost:5173  (dev)  |  same-origin (prod build)
  │
  ▼
FastAPI application  (apps/backend/app/main.py)
  │  SQLAlchemy ORM
  ├── SQLite database  (apps/api/instance/garden.db)
  │
  │  Python imports (same process)
  ├── ML service  (apps/ml_service/app/)
  │   ├── recommender.py      Plant recommendations
  │   ├── chat_tools.py       Tool schemas + agentic loop
  │   ├── chat_logger.py      Session-level conversation logging
  │   ├── watering_engine.py  ET0-based watering deficit
  │   └── llm_provider.py     Model-agnostic LLM wrapper
  │
  └── ML training  (ml/)
      ├── features/build_features.py   Feature engineering
      ├── training/train_recommender.py
      └── models/recommender.pkl       Trained GBM model
```

Everything runs in a single Python process. The ML service is a package imported by the FastAPI app at request time — no separate microservice or network call. The React frontend communicates with the backend over a local REST API. In production, `npm run build` outputs to `apps/web/dist/` and the FastAPI app serves it as a SPA.

---

## Directory Structure

```
gardening_app/
├── apps/
│   ├── backend/                    # FastAPI application
│   │   └── app/
│   │       ├── main.py             # App factory, middleware, lifespan
│   │       ├── db/
│   │       │   ├── models.py       # SQLAlchemy models (source of truth)
│   │       │   └── session.py      # SessionLocal + get_db dependency
│   │       ├── routers/            # One file per resource area
│   │       │   ├── gardens.py
│   │       │   ├── beds.py
│   │       │   ├── plants.py
│   │       │   ├── tasks.py
│   │       │   ├── canvas.py
│   │       │   ├── library.py
│   │       │   ├── weather.py
│   │       │   ├── chat.py
│   │       │   └── perenual.py
│   │       └── services/
│   │           └── helpers.py      # Shared utilities (frost dates, seasons)
│   │
│   ├── web/                        # React + TypeScript frontend
│   │   └── src/
│   │       ├── pages/              # Route-level components
│   │       │   ├── Dashboard.tsx
│   │       │   ├── GardenDetail.tsx
│   │       │   ├── Planner.tsx
│   │       │   ├── LibraryBrowser.tsx
│   │       │   └── …
│   │       ├── components/         # Reusable UI components (ChatWidget, etc.)
│   │       ├── hooks/              # React Query hooks
│   │       └── api/                # Typed API client
│   │
│   ├── api/                        # RETIRED Flask app — kept for reference only
│   │   └── instance/               # SQLite DB lives here (gitignored)
│   │       └── garden.db
│   │
│   └── ml_service/
│       └── app/
│           ├── recommender.py      # Rule-based + ML plant scorer
│           ├── chat_tools.py       # 12 AI chat tools + agentic loop
│           ├── chat_logger.py      # Structured conversation session logs
│           ├── watering_engine.py  # Kc table, deficit calc, urgency scorer
│           └── llm_provider.py     # Anthropic / OpenAI / Ollama / HuggingFace
│
├── ml/
│   ├── features/build_features.py  # Feature engineering (pure Python)
│   ├── data/generate_synthetic.py  # Synthetic training set generator
│   ├── training/train_recommender.py
│   ├── evaluation/metrics.py       # precision@k, recall@k, NDCG@k
│   ├── eda/                        # EDA scripts and outputs
│   └── models/recommender.pkl      # Trained model artifact
│
├── scripts/                        # One-off data enrichment scripts
│   ├── trefle_sync.py              # Trefle botanical data sync
│   ├── permapeople_sync.py         # Bulk companion planting sync
│   ├── backfill_images_wiki.py     # Wikimedia/iNaturalist image download
│   ├── build_rag.py                # Build ChromaDB RAG index for growing guides
│   ├── backfill_frost_dates.py     # Backfill frost dates from NOAA
│   └── usda_nutrition_sync.py      # USDA nutritional data
│
├── pyproject.toml                  # Project metadata + dependencies
└── CLAUDE.md                       # AI coding assistant instructions
```

---

## Setup and Running

**Requirements:** Python 3.11+, [uv](https://github.com/astral-sh/uv), Node.js 18+

### Backend

```bash
# 1. Install Python dependencies
uv sync

# 2. Copy the environment file and add your API keys (optional — see below)
cp .env.example .env

# 3. Start the FastAPI development server (port 8000)
uv run uvicorn apps.backend.app.main:app --reload
```

The database is created automatically on first run at `apps/api/instance/garden.db`. The plant library (~9,000 entries) is seeded from the existing database; to rebuild from scratch run `scripts/trefle_sync.py`.

### Frontend

```bash
cd apps/web

# Install Node dependencies (first run only)
npm install

# Start the Vite dev server (port 5173)
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api` requests to the FastAPI backend on port 8000.

### Production build

```bash
cd apps/web && npm run build
# Outputs to apps/web/dist/ — FastAPI serves it as a SPA catch-all
uv run uvicorn apps.backend.app.main:app
```

### Optional: train the recommender model

```bash
# Generate synthetic training data (uses live DB)
uv run python ml/data/generate_synthetic.py

# Train — prints cross-validation metrics and saves ml/models/recommender.pkl
uv run python ml/training/train_recommender.py
```

### Optional: build the RAG index for growing guides

```bash
uv run python scripts/build_rag.py
# Populates a ChromaDB collection used by the search_growing_guides chat tool
```

### Optional: EDA plots

```bash
uv sync --extra eda
uv run python ml/eda/explore_features.py
# Plots saved to ml/eda/plots/
```

---

## Features

### Garden & Bed Management

Create one or more **Gardens**, each with a zip code or lat/lon. The app resolves the [USDA Plant Hardiness Zone](https://planthardiness.ars.usda.gov/) and last/first spring frost dates automatically, which feeds into planting calendar calculations and watering recommendations.

Each garden contains **Beds** — raised beds or plots with dimensions, soil pH, and composition notes. Plants are assigned to beds through a grid interface; each grid cell maps to a specific inch-position within the bed.

**Source:** `apps/backend/app/routers/gardens.py`, `beds.py`, `plants.py`
**Models:** `apps/backend/app/db/models.py`

---

### Visual Planner

A full-width drag-and-drop canvas for arranging beds in your garden. Beds snap to a 60px/unit grid. Plants can also be placed as free circles directly on the canvas (useful for trees, large shrubs, or rough layout planning without assigning to a specific bed).

**Source:** `apps/web/src/pages/Planner.tsx`, `apps/backend/app/routers/canvas.py`

---

### Plant Library

A reference catalog of ~9,000 plants sourced from open datasets:

| Source | Data | Licence |
|---|---|---|
| [Trefle](https://trefle.io) | Botanical data, growth habits, temperature ranges | CC0 |
| [Permapeople](https://permapeople.org) | Companion planting, edible parts, growing tips | CC BY-SA 4.0 |
| Wikimedia / iNaturalist | Plant photos (6,200+ images across 2,100+ plants) | Various (CC) |

Each entry includes spacing, sunlight and water needs, soil pH range, USDA zone range, days to harvest, companion planting lists, how-to-grow guides, and FAQs.

**Source:** `apps/backend/app/db/models.py → PlantLibrary`
**Images:** `apps/api/static/plant_images/` — filenames follow `{library_id}_{source}_{n}.jpg`

---

### AI Garden Assistant

An AI chat widget backed by a **server-side agentic loop**. Claude (or any supported LLM) can call 12 tools to read and write real garden data:

| Tool | What it does |
|---|---|
| `get_garden_plan` | Lists all beds and their current plants |
| `check_companion_planting` | Looks up good/bad neighbours from the library |
| `check_planting_calendar` | Calculates start-indoors / transplant / direct-sow dates from your frost date |
| `check_spacing_requirements` | Returns spacing and bed capacity estimates |
| `get_plant_care_info` | Returns sunlight, water, soil, and growing notes |
| `add_plant_to_garden` | Creates a Plant record and optionally assigns it to a bed |
| `create_task` | Creates a Task with auto-calculated due dates |
| `list_upcoming_tasks` | Queries open tasks in the next N days |
| `get_weather_forecast` | 7-day Open-Meteo forecast with ET₀ |
| `get_watering_history` | Recent rainfall + last-watered dates per bed |
| `get_watering_recommendation` | Full watering deficit + urgency scores per bed |
| `search_growing_guides` | RAG search over TAMU/extension growing guides (ChromaDB) |

Conversation history is maintained client-side (a React state array) and sent with every request. This keeps the server stateless while giving Claude full multi-turn context. Conversations are logged server-side to `logs/` for debugging and analysis.

**Source:** `apps/ml_service/app/chat_tools.py`, `apps/backend/app/routers/chat.py`

---

### Plant Recommender

Scores every plant in the library for how well it fits the current garden context and returns a ranked list.

**Two scoring modes:**

1. **Rule-based** (always available) — weighted sum of 7 features:

   | Feature | Weight | How it's calculated |
   |---|---|---|
   | Zone match | 30% | Plant's min/max zone vs. garden's USDA zone |
   | Season match | 25% | Can you plant now and harvest before first fall frost? |
   | Sunlight match | 20% | Plant need vs. estimated garden sun hours |
   | Soil pH match | 10% | Plant's pH range vs. bed soil pH |
   | Difficulty | 10% | Easy=1.0, Moderate=0.5, Hard=0.0 |
   | Type preference | 5% | Matches user's preferred plant types |
   | Companion bonus | +0.2 | Plant is a good neighbour of something already growing |

2. **ML model** (when `ml/models/recommender.pkl` exists) — a `GradientBoostingClassifier` trained on the same 7 features. Actual feature importances from training: season_match 41%, zone_match 39%, sunlight_match 18%.

**Source:** `ml/features/build_features.py`, `apps/ml_service/app/recommender.py`

---

### Predictive Watering Engine

Calculates a **soil moisture deficit** and **urgency score (0–100)** for each bed using agronomic principles from the [FAO-56 methodology](https://www.fao.org/3/x0490e/x0490e00.htm):

```
deficit (mm) = Σ over past N days of (ET_actual − effective_rainfall)

ET_actual = ET₀ × Kc
```

Where:
- **ET₀** (reference evapotranspiration) is estimated from min/max temperature stored in `WeatherLog` using a simplified [Hargreaves-Samani equation](https://www.sciencedirect.com/topics/earth-and-planetary-sciences/hargreaves-equation)
- **Kc** (crop coefficient) is looked up from a built-in table of 33 plant types; falls back to the plant's water need category (Low / Moderate / High)
- **Effective rainfall** is raw rainfall minus a 2mm interception threshold
- The lookback window is capped at the number of days since the bed was last watered

The urgency score is then adjusted for today's forecast: boosted by heat and wind, reduced if rain is likely.

Weather history (14 days of rainfall and temperature) is fetched automatically from [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) by a background scheduler that runs daily at 2 AM and once at startup.

**Source:** `apps/ml_service/app/watering_engine.py`

---

## Data Model

Quick summary of the key relationships:

```
Garden
 └── GardenBed ──┐
 └── Plant ───────┼── BedPlant  (placement: grid_x/y, last_watered, stage)
                  │
           PlantLibrary  (shared reference catalog — not owned by any garden)

Garden └── WeatherLog  (daily rainfall + temp per garden)
Garden └── Task        (to-dos scoped to garden / bed / plant)
Garden └── CanvasPlant (free-placed circles on the planner canvas)
```

One important distinction: **`Plant`** is an instance you're growing ("my tomato planted March 15"), while **`PlantLibrary`** is the reference entry ("Tomato — requires 24" spacing, full sun, zone 5–11"). A `Plant` links to a `PlantLibrary` entry via `library_id`.

**Source of truth:** `apps/backend/app/db/models.py`

---

## AI & ML System

### LLM Provider

`apps/ml_service/app/llm_provider.py` provides a single `complete(system, user) → str` function that dispatches to any supported backend:

```
LLM_PROVIDER=anthropic   → Anthropic API (default)
LLM_PROVIDER=openai      → OpenAI API (gpt-4o-mini default)
LLM_PROVIDER=ollama      → Local Ollama server (gemma4 default)
LLM_PROVIDER=huggingface → HuggingFace Inference API
```

The agentic tool-use loop in `chat_tools.py` is **Anthropic-first** — only Anthropic's API natively supports the `tool_use` stop reason and structured tool result messages. For other providers, the loop falls back to a plain `complete()` call (single turn, no tool use). Set `CHAT_MODEL` separately from `LLM_MODEL` to use a more capable model for chat.

### Agentic Loop

```
User message
     │
     ▼
run_agentic_loop(system, messages, garden, db)
     │
     ├── Call Claude API with TOOL_SCHEMAS + full conversation history
     │
     ├── If stop_reason == 'tool_use':
     │     execute_tool(name, input, garden, db)  ← direct SQLAlchemy queries
     │     append tool_result to messages
     │     └── repeat (up to 5 rounds)
     │
     └── If stop_reason == 'end_turn':
           return reply text
```

All tool execution is Python — no HTTP round-trips back to the API. Tools access the full SQLAlchemy session passed from the FastAPI request, keeping transactions consistent.

### RAG Growing Guides

`search_growing_guides` uses a [ChromaDB](https://www.trychroma.com/) vector store built from university extension growing guides (TAMU and others). Build the index once with `scripts/build_rag.py`. The chat assistant falls back gracefully if the index doesn't exist.

### Recommender Training

```bash
# Full pipeline
uv run python ml/data/generate_synthetic.py   # 539K rows (60 users × 8,988 plants)
uv run python ml/training/train_recommender.py # 5-fold CV → saves recommender.pkl
```

---

## API Routes

Key JSON endpoints (all prefixed `/api`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/gardens` | List all gardens |
| `POST` | `/api/gardens` | Create a garden |
| `GET` | `/api/gardens/<id>/weather` | Current conditions + 7-day forecast |
| `GET` | `/api/gardens/<id>/watering-status` | Per-bed urgency scores + recommendations |
| `GET` | `/api/gardens/<id>/tasks` | Open tasks for a garden |
| `GET` | `/api/beds` | List beds (optionally filtered by garden) |
| `GET` | `/api/beds/<id>/grid` | Plant grid for a bed |
| `POST` | `/api/beds/<id>/grid-plant` | Place a plant in a bed cell |
| `GET` | `/api/library` | Paginated plant library search |
| `GET` | `/api/library/<id>` | Single library entry |
| `POST` | `/api/chat` | AI chat (multi-turn, agentic tool use) |
| `GET` | `/api/recommendations` | Top-N plant recommendations for context |
| `GET` | `/api/health` | Backend health check |

Full route details: `apps/backend/app/routers/`

---

## Design Decisions

### FastAPI + SQLite

This is a local, single-user application. FastAPI and SQLite have zero infrastructure overhead, and the database is a single file you can copy or delete. There's no reason to run Postgres or a job queue for a personal garden tracker. FastAPI's async support and automatic OpenAPI docs are useful bonuses over Flask.

### React + Vite instead of server-side templates

The original Flask + Jinja2 + vanilla JS frontend was replaced with a React/TypeScript SPA to handle the growing complexity of interactive views (the planner, the chat widget, the bed grid). Vite provides a fast dev loop with HMR. In production a single `npm run build` produces a static bundle served by FastAPI's SPA catch-all.

### React Query for data fetching

All API calls go through [TanStack Query](https://tanstack.com/query) hooks in `apps/web/src/hooks/`. This gives automatic caching, background refetching, and loading/error states without boilerplate.

### Separate routers per resource

Unlike the earlier single-file Flask app, the FastAPI backend splits routes into one file per resource area (gardens, beds, plants, weather, etc.). Each router is ~100–200 lines — small enough to read top-to-bottom, easy to find with a file search.

### PlantLibrary as a shared catalog, separate from Plant instances

`PlantLibrary` holds *what* a tomato needs (spacing, zones, companions). `Plant` holds *your* tomato (when you planted it, which bed it's in, its current stage). They are linked by `Plant.library_id`. This means:
- You can have 10 tomato plants linked to one library entry
- Enriching the library (adding an image, fixing spacing data) immediately updates display for all instances
- The library is never modified by normal app use — it's reference data

### BedPlant association table (not a simple FK on Plant)

A plant can be moved between beds, or the same library entry can be placed in multiple beds simultaneously. `BedPlant` is a proper many-to-many junction with its own care-tracking fields (`last_watered`, `stage`, `health_notes`) so each placement has independent state.

### Inline schema migrations at startup

The app uses explicit `ALTER TABLE … ADD COLUMN` statements at startup rather than Alembic migration files. For a local single-developer project this is simpler and avoids migration file sprawl. The downside is it only adds columns. When a full reset is needed, delete `apps/api/instance/garden.db`.

### Server-side agentic loop (not client-side tool execution)

The AI tool-use loop runs entirely in Python on the server. An alternative would be to let the React front-end call tools via REST. The server-side approach is better because:
- Tool implementations share the FastAPI SQLAlchemy session (same transaction)
- No extra HTTP round-trips per tool call
- Auth and validation stay in one place
- The client only ever receives the final text reply

### Background scheduler for weather collection

[APScheduler](https://apscheduler.readthedocs.io/) runs a background job at 2 AM daily to fetch 14-day weather history for all gardens from Open-Meteo Archive and store it in `WeatherLog`. This means the watering engine always has fresh data without the user manually triggering a fetch.

### Open-Meteo for weather (no API key)

[Open-Meteo](https://open-meteo.com) provides 7-day forecasts and 80-year historical archive with no registration, no rate-limiting for personal use, and no billing surprises.

### Hargreaves ET₀ instead of storing ET₀ data

The watering engine estimates ET₀ from the min/max temperatures already in `WeatherLog` using the Hargreaves-Samani equation — accurate to within ~15% of Penman-Monteith for temperate climates, which is good enough for watering guidance. This avoids an extra API field or database column.

---

## Resetting the Database

Stop the FastAPI server first, then:

```bash
# macOS / Linux
rm apps/api/instance/garden.db

# Windows
python -c "import os; os.remove('apps/api/instance/garden.db')"
```

Restart the server — the schema will be recreated automatically. Re-run the sync scripts to repopulate the plant library.

On Windows, if the server doesn't stop with Ctrl+C:
```bash
netstat -ano | findstr :8000
taskkill /F /PID <pid>
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in what you need:

```env
# AI Chat — at least one is required to use the chat assistant
ANTHROPIC_API_KEY=sk-ant-...       # https://console.anthropic.com
OPENAI_API_KEY=sk-...              # https://platform.openai.com
OLLAMA_BASE_URL=http://localhost:11434  # local Ollama (no key needed)
HF_TOKEN=hf_...                    # HuggingFace (optional for public models)

# Which LLM to use for completions (default: anthropic)
LLM_PROVIDER=anthropic

# Which model to use for the chat assistant
CHAT_MODEL=claude-sonnet-4-6
LLM_MODEL=claude-haiku-4-5-20251001

# Data enrichment scripts (not needed to run the app)
PERENUAL_API_KEY=...
PEXELS_API_KEY=...
X-Permapeople-Key-Id=...
X-Permapeople-Key-Secret=...
```

Weather data (Open-Meteo) requires no API key.
