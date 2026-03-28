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
  │  Jinja2 templates + Vanilla JS
  │
  ▼
Flask application  (apps/api/app/main.py)
  │  SQLAlchemy ORM
  ├── SQLite database  (apps/api/instance/garden.db)
  │
  │  Python imports (same process)
  ├── ML service  (apps/ml_service/app/)
  │   ├── recommender.py      Plant recommendations
  │   ├── chat_tools.py       Tool schemas + agentic loop
  │   ├── watering_engine.py  ET0-based watering deficit
  │   └── llm_provider.py     Model-agnostic LLM wrapper
  │
  └── ML training  (ml/)
      ├── features/build_features.py   Feature engineering
      ├── training/train_recommender.py
      └── models/recommender.pkl       Trained GBM model
```

Everything runs in a single Python process. The "ML service" is a package imported by the Flask app at request time — there is no separate microservice or network call between them. This keeps deployment simple while leaving the door open to extract it later.

---

## Directory Structure

```
gardening_app/
├── apps/
│   ├── api/                        # The live Flask application
│   │   ├── app/
│   │   │   ├── main.py             # All routes and app factory (create_app)
│   │   │   └── db/models.py        # SQLAlchemy models
│   │   ├── docs/
│   │   │   └── database-model.md   # ER diagram + model reference
│   │   ├── static/
│   │   │   ├── style.css           # All styles (single stylesheet)
│   │   │   ├── planner.js          # Drag-and-drop planner canvas
│   │   │   └── plant_images/       # Locally cached plant photos
│   │   ├── templates/              # Jinja2 HTML templates
│   │   │   ├── base.html           # Shared layout, nav, fonts
│   │   │   ├── index.html          # Dashboard
│   │   │   ├── planner.html        # Visual bed planner
│   │   │   ├── library_detail.html # Plant library entry
│   │   │   └── …
│   │   ├── instance/               # SQLite DB lives here (gitignored)
│   │   └── wsgi.py
│   │
│   └── ml_service/
│       └── app/
│           ├── recommender.py      # Rule-based + ML plant scorer
│           ├── chat_tools.py       # 11 AI chat tools + agentic loop
│           ├── watering_engine.py  # Kc table, deficit calc, urgency scorer
│           └── llm_provider.py     # Anthropic / OpenAI / Ollama / HuggingFace
│
├── ml/
│   ├── features/build_features.py  # Feature engineering (pure Python)
│   ├── data/generate_synthetic.py  # Synthetic training set generator
│   ├── training/train_recommender.py
│   ├── evaluation/metrics.py       # precision@k, recall@k, NDCG@k
│   ├── eda/explore_features.py     # EDA plots (requires --extra eda)
│   └── models/recommender.pkl      # Trained model artifact
│
├── scripts/                        # One-off data enrichment scripts
│   ├── supplement_library.py       # Perenual API enrichment
│   ├── permapeople_sync.py         # Bulk companion planting sync
│   ├── backfill_images_wiki.py     # Wikimedia/iNaturalist image download
│   └── populate_plant_details.py   # Extended Trefle botanical data
│
├── pyproject.toml                  # Project metadata + dependencies
└── CLAUDE.md                       # AI coding assistant instructions
```

---

## Setup and Running

**Requirements:** Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
# 1. Install dependencies
uv sync

# 2. Copy the environment file and add your API keys (optional — see below)
cp .env.example .env

# 3. Start the development server
#    macOS / Linux
FLASK_APP=apps/api/wsgi.py FLASK_DEBUG=1 uv run flask run

#    Windows PowerShell
$env:FLASK_APP="apps/api/wsgi.py"; $env:FLASK_DEBUG="1"; uv run flask run

#    Windows CMD
set FLASK_APP=apps/api/wsgi.py && set FLASK_DEBUG=1 && uv run flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

The database is created automatically on first run. The plant library (~9,000 entries) is seeded from `scripts/seed_library.py` if the table is empty.

### Optional: train the recommender model

```bash
# Generate synthetic training data (uses live DB)
uv run python ml/data/generate_synthetic.py

# Train — prints cross-validation metrics and saves ml/models/recommender.pkl
uv run python ml/training/train_recommender.py
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

Create one or more **Gardens**, each with a zip code or lat/lon. The app resolves the [USDA Plant Hardiness Zone](https://planthardiness.ars.usda.gov/) and last spring frost date automatically, which feeds into planting calendar calculations and watering recommendations.

Each garden contains **Beds** — raised beds or plots with dimensions, soil pH, and composition notes. Plants are assigned to beds through a grid interface; each grid cell maps to a specific inch-position within the bed.

**Source:** [`apps/api/app/main.py`](apps/api/app/main.py) — `Garden`, `GardenBed`, `Plant`, `BedPlant` routes
**Models:** [`apps/api/docs/database-model.md`](apps/api/docs/database-model.md)

---

### Visual Planner

A full-width drag-and-drop canvas for arranging beds in your garden. Beds snap to a 60px/unit grid. Plants can also be placed as free circles directly on the canvas (useful for trees, large shrubs, or rough layout planning without assigning to a specific bed).

The right-side panel shows bed details, plant care info, and the top-5 plant recommendations for the selected garden context.

**Source:** [`apps/api/static/planner.js`](apps/api/static/planner.js), [`apps/api/templates/planner.html`](apps/api/templates/planner.html)

---

### Plant Library

A reference catalog of ~9,000 plants sourced from three open datasets:

| Source | Data | Licence |
|---|---|---|
| [Trefle](https://trefle.io) | Botanical data, growth habits, temperature ranges | CC0 |
| [Permapeople](https://permapeople.org) | Companion planting, edible parts, growing tips | CC BY-SA 4.0 |
| Wikimedia / iNaturalist | Plant photos (6,200+ images across 2,100+ plants) | Various (CC) |

Each entry includes spacing, sunlight and water needs, soil pH range, USDA zone range, days to harvest, companion planting lists, how-to-grow guides, and FAQs.

**Source:** [`apps/api/app/db/models.py → PlantLibrary`](apps/api/app/db/models.py)
**Images:** `apps/api/static/plant_images/` — filenames follow `{library_id}_{source}_{n}.jpg`

---

### AI Garden Assistant

An AI chat widget on the dashboard backed by a **server-side agentic loop**. Claude (or any supported LLM) can call 11 tools to read and write real garden data:

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

Conversation history is maintained client-side (a plain JS array) and sent with every request. This keeps the server stateless while giving Claude full multi-turn context.

**Source:** [`apps/ml_service/app/chat_tools.py`](apps/ml_service/app/chat_tools.py)

---

### Plant Recommender

Scores every plant in the library for how well it fits the current garden context and returns a ranked list. Used in the planner right panel and in the chat assistant's system prompt.

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

**Source:** [`ml/features/build_features.py`](ml/features/build_features.py), [`apps/ml_service/app/recommender.py`](apps/ml_service/app/recommender.py)

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

**To improve accuracy:** on the garden detail page, click **Fetch Weather History** to pull 14 days of rainfall and temperature data from [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) into `WeatherLog`. The engine uses this data automatically.

**Source:** [`apps/ml_service/app/watering_engine.py`](apps/ml_service/app/watering_engine.py)

---

## Data Model

Full ER diagram and model-by-model reference: **[`apps/api/docs/database-model.md`](apps/api/docs/database-model.md)**

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

---

## AI & ML System

### LLM Provider

[`apps/ml_service/app/llm_provider.py`](apps/ml_service/app/llm_provider.py) provides a single `complete(system, user) → str` function that dispatches to any supported backend:

```
LLM_PROVIDER=anthropic   → Anthropic API (default, claude-haiku-4-5 for chat completions)
LLM_PROVIDER=openai      → OpenAI API (gpt-4o-mini default)
LLM_PROVIDER=ollama      → Local Ollama server (llama3 default)
LLM_PROVIDER=huggingface → HuggingFace Inference API
```

The agentic tool-use loop in `chat_tools.py` is **Anthropic-first** — only Anthropic's API natively supports the `tool_use` stop reason and structured tool result messages. For other providers, the loop falls back to a plain `complete()` call (single turn, no tool use). Set `CHAT_MODEL` separately from `LLM_MODEL` to use a more capable model for the chat while keeping cheaper models for other tasks.

### Agentic Loop

```
User message
     │
     ▼
run_agentic_loop(system, messages, garden)
     │
     ├── Call Claude API with TOOL_SCHEMAS + full conversation history
     │
     ├── If stop_reason == 'tool_use':
     │     execute_tool(name, input, garden)  ← direct SQLAlchemy queries
     │     append tool_result to messages
     │     └── repeat (up to 5 rounds)
     │
     └── If stop_reason == 'end_turn':
           return reply text
```

All tool execution is Python — no HTTP calls back to the Flask API. This avoids latency, keeps auth in one place, and lets tools access the full ORM layer (e.g., lazy-loaded relationships).

### Recommender Training

```bash
# Full pipeline
uv run python ml/data/generate_synthetic.py   # 539K rows (60 users × 8,988 plants)
uv run python ml/training/train_recommender.py # 5-fold CV → saves recommender.pkl
```

The synthetic data is generated by running the rule-based scorer over all (user_profile, plant) pairs with Gaussian noise added to simulate real-world variability. A label threshold of 0.55 marks a pairing as "successful". This gives ~68.5% positive class balance.

---

## API Routes

The full route list is in [`apps/api/app/main.py`](apps/api/app/main.py). Key JSON endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/gardens/<id>/weather` | Current conditions + 7-day forecast |
| `POST` | `/api/gardens/<id>/fetch-weather` | Pull 14-day history into WeatherLog |
| `GET` | `/api/gardens/<id>/watering-status` | Per-bed urgency scores + recommendations |
| `GET` | `/api/gardens/<id>/tasks` | Open tasks for a garden |
| `POST` | `/api/gardens/<id>/quick-task` | Create a task with auto-calculated dates |
| `POST` | `/api/gardens/<id>/bulk-care` | Mark all beds watered / fertilized |
| `GET` | `/api/recommendations` | Top-N plant recommendations for context |
| `POST` | `/api/chat` | AI chat (multi-turn, agentic tool use) |
| `GET` | `/api/beds/<id>/grid` | Plant grid for a bed |
| `POST` | `/api/beds/<id>/grid-plant` | Place a plant in a bed cell |
| `POST` | `/api/bedplants/<id>/care` | Update last_watered / fertilized / harvested |

---

## Design Decisions

### Flask + SQLite instead of a heavier stack

This is a local, single-user application. Flask and SQLite are fast to start, have zero infrastructure overhead, and the database is a single file you can copy or delete. There's no reason to run Postgres, a job queue, or a containerised backend for a personal garden tracker.

### Vanilla JS + Jinja2 instead of React

No build step means no `node_modules`, no bundler configuration, and no framework churn. Templates are rendered server-side; small interactive islands (the planner canvas, the chat widget) are written in plain JavaScript. The result is a page that loads fast and is easy to debug with browser DevTools.

### Single `main.py` for all routes

All Flask routes live in one file. At ~2,200 lines this is large, but it means you can `Ctrl+F` any route or helper without switching between files. The app factory pattern (`create_app()`) still provides proper isolation for testing.

### PlantLibrary as a shared catalog, separate from Plant instances

`PlantLibrary` holds *what* a tomato needs (spacing, zones, companions). `Plant` holds *your* tomato (when you planted it, which bed it's in, its current stage). They are linked by `Plant.library_id`. This means:
- You can have 10 tomato plants linked to one library entry
- Enriching the library (adding an image, fixing spacing data) immediately updates display for all instances
- The library is never modified by normal app use — it's reference data

### BedPlant association table (not a simple FK on Plant)

A plant can be moved between beds, or the same library entry can be placed in multiple beds simultaneously. `BedPlant` is a proper many-to-many junction with its own care-tracking fields (`last_watered`, `stage`, `health_notes`) so each placement has independent state.

### No database migrations framework

The app uses explicit `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statements at startup rather than Alembic or a similar migrations tool. For a local single-developer project in early development, this is simpler and avoids migration file sprawl. The downside is it only adds columns, never removes or renames them. When a full reset is needed, delete `instance/garden.db`.

### Server-side agentic loop (not client-side tool execution)

The AI tool-use loop runs entirely in Python on the server. An alternative would be to let the JavaScript front-end call tools by making HTTP requests to existing Flask routes. The server-side approach is better because:
- Tool implementations can use the full SQLAlchemy ORM (lazy relationships, transactions)
- No extra HTTP round-trips per tool call
- Auth and validation stay in one place
- The client only ever receives the final text reply

### Model-agnostic LLM wrapper

`llm_provider.py` uses lazy imports so you only need the SDK for the provider you're actually using. If `LLM_PROVIDER=ollama`, installing `anthropic` is unnecessary. This keeps the base install lightweight.

### Open-Meteo for weather (no API key)

[Open-Meteo](https://open-meteo.com) provides 7-day forecasts and 80-year historical archive with no registration, no rate-limiting for personal use, and no billing surprises. The tradeoff is the archive endpoint adds ~1s latency and the data has ~1-day lag for the most recent day.

### Hargreaves ET₀ instead of storing ET₀ data

The watering engine needs reference evapotranspiration (ET₀) to calculate how much water plants lost on each historical day. Storing it would require either an extra API call during the weather history fetch or a new database column with a migration. Instead, ET₀ is estimated from the min/max temperatures already in `WeatherLog` using the Hargreaves-Samani equation — accurate to within ~15% of Penman-Monteith for temperate climates, which is good enough for watering guidance.

### Synthetic training data for the recommender

There is no real user data yet. The training set is generated by running the rule-based scorer over all (synthetic user profile, plant) pairs with added Gaussian noise. This gives the ML model something to learn while the app is being built. Once real users provide feedback (e.g., "I planted this and it worked well"), the training data can be replaced with actuals.

---

## Resetting the Database

Stop Flask first (the SQLite file is locked on Windows while running), then:

```bash
# macOS / Linux
rm apps/api/instance/garden.db

# Windows
python -c "import os; os.remove('apps/api/instance/garden.db')"
```

Restart Flask — the schema and plant library will be recreated automatically.

On Windows, find and kill the Flask process if it doesn't stop with Ctrl+C:
```bash
netstat -ano | findstr :5000
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

# Which model to use for the chat assistant (default: claude-sonnet-4-6)
# Set CHAT_MODEL separately to use a smarter model for chat vs. other tasks
CHAT_MODEL=claude-sonnet-4-6
LLM_MODEL=claude-haiku-4-5-20251001

# Data enrichment scripts (not needed to run the app)
PERENUAL_API_KEY=...
PEXELS_API_KEY=...
X-Permapeople-Key-Id=...
X-Permapeople-Key-Secret=...
```

Weather data (Open-Meteo) requires no API key.
