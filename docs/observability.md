# Observability

How the garden app reports on itself in production, and why it's set up this way.

Phase 1 (Sentry, backend) is **done**. Phases 2–4 are planned; each section below
says what's built and what isn't, so this file is the resume point.

---

## Why this exists

Before Phase 1, the app had no way to tell you when it broke:

- Backend logs went to a `RotatingFileHandler` at `logs/startup.log`. On Render that
  disk is **ephemeral** — every redeploy and every free-tier spin-down destroys it.
- The three nightly jobs were fired by `curl` from GitHub Actions with nothing
  watching the result. The 2026-07-21 nightly 500 was found by hand-digging Render
  logs, days later.
- Render's own metrics are near-empty (the free instance sleeps), so there was no
  usage picture either.

Sentry replaces none of that logging — it sits alongside it and outlives it.

---

## Phase 1 — Sentry on the FastAPI backend ✅

**Sentry project:** `garden-app-backend` in org `greg-ei`
(https://greg-ei.sentry.io/issues/?project=garden-app-backend)

### What's instrumented

| Signal | Where | Notes |
|---|---|---|
| Unhandled exceptions | `apps/backend/app/main.py` — `sentry_sdk.init()` | FastAPI/Starlette integrations auto-enable |
| Tracing (sampled) | same, via `traces_sampler` | 10% of real requests; health + static dropped |
| Structured logs | same, `enable_logs=True` | Bridges stdlib logging, incl. the `SLOW` warnings in `log_slow_requests` |
| Cron check-ins | `@monitor` on the three nightly jobs | see table below |
| Anthropic LLM calls | automatic | `AnthropicIntegration` auto-enables; the chat agent's calls appear as `gen_ai.*` spans |

### Three deliberate departures from the Sentry skill's default init

The `sentry:sentry-instrument` skill's recommended init differs from what's here. Each
change was made on purpose:

1. **`send_default_pii=False`** (skill default: `True`).
   The app stores real user emails and auth identity. `True` would ship client IPs,
   request headers and the logged-in user to a third party. **Cost:** no client IP and
   no query strings on events.
   *Honest caveat:* Sentry still derives a coarse city-level `user.geo` from the
   connecting IP at ingest time. `send_default_pii=False` stops the SDK from *sending*
   the IP; it does not stop server-side geolocation of the connection.

2. **`traces_sampler` instead of `traces_sample_rate`** (the two are mutually
   exclusive).
   - `/api/health` → `0` — Render polls this continuously as the health check.
   - `/static/*` → `0` — the GCS image proxy serves many requests per page view.
   - everything else → `0.1`.

   At a flat rate those two paths would consume the whole free-tier transaction quota
   while telling us nothing. The sampler **must never raise**: the SDK's fallback on
   exception is `traces_sample_rate`, which is unset here by design, so a raise leaves
   no sampling decision at all. That's what `tests/unit/test_sentry_config.py` guards.

3. **No profiling** (the skill's recommended init enables it).
   This runs on a 512 MB free instance already sitting at ~204 MB. Revisit when there
   is traffic worth profiling.

### Cron monitors

Decorated on the **job functions**, not the admin routes — one decorator then covers
both trigger paths (the GitHub Actions `curl` and the in-process APScheduler).

`monitor_config` is required. Without it Sentry never creates the monitor, and a
monitor that doesn't exist cannot report `MISSED`.

| Slug | Function | File | `max_runtime` |
|---|---|---|---|
| `nightly-weather-fetch` | `run_daily_weather_fetch` | `app/routers/weather.py` | 15 min |
| `nightly-ml-snapshot` | `run_ml_snapshot` | `app/jobs/ml_snapshot.py` | 10 min |
| `nightly-gcs-backup` | `run_backup` | `app/jobs/gcs_backup.py` | 10 min |

All three: `0 7 * * *` UTC (mirroring `.github/workflows/scheduled-jobs.yaml`),
`checkin_margin: 30`. The margin is generous because the first nightly request also
has to wake a spun-down free instance and a scale-to-zero Neon compute.

**The point of this:** Sentry generates `MISSED` server-side. A job that stops running
*entirely* now opens an issue — the failure mode you cannot catch by watching for
errors, because a job that never runs never throws.

> ⚠️ **`nightly-gcs-backup` is a no-op in production.** `run_backup` early-exits when
> `DATABASE_URL` is Postgres (`gcs_backup.py`), because Neon's point-in-time restore
> covers production data. A green check-in means *"the nightly job ran"*, **not**
> *"a backup was written"*. Don't read it as backup assurance.

### Configuration

| Variable | Where | Notes |
|---|---|---|
| `SENTRY_DSN` | Render dashboard (manual) | `sync: false` in `render.yaml` declares the variable but never carries its value |
| `SENTRY_ENVIRONMENT` | `render.yaml` → `production` | defaults to `development` |
| `RENDER_GIT_COMMIT` | injected by Render | becomes the Sentry `release` |

Leave `SENTRY_DSN` **unset locally** — the SDK no-ops on an empty DSN, so no
conditional is needed in `main.py` and local development stays quiet.

Release also resolves without `RENDER_GIT_COMMIT`: the SDK auto-detects the git SHA.
Verified locally — the test event carried `release: bba378d…`.

### How to verify it still works

```bash
# 1. The sampler logic (fast, no network, runs in CI)
uv run pytest tests/unit/test_sentry_config.py -q

# 2. Confirm the SDK is live with the real config
SENTRY_DSN='<dsn>' uv run python -c "
import sentry_sdk
from apps.backend.app.main import traces_sampler
c = sentry_sdk.get_client()
print('active', c.is_active(), '| pii', c.options['send_default_pii'])
print('health', traces_sampler({'asgi_scope': {'path': '/api/health'}}))
"
```

Then check issues via the Sentry MCP (`search_issues`) or the dashboard.

### Verified on 2026-07-26

- ✅ A real FastAPI exception reached Sentry as `GARDEN-APP-BACKEND-1`, with a stack
  trace resolving to application code. Trace context showed `client_sample_rate: 0.1`,
  confirming the sampler is applied. Issue since marked resolved.
- ✅ `196 passed` — full `tests/unit tests/data_tests` suite after the change.
- ✅ **Deployed** as `082c759` (`dep-d9j4addsbgtc73d2u41g`, live 2026-07-26T17:38Z).
  The build's `uv sync --frozen` resolved `sentry-sdk` 2.66.1 from the lockfile;
  `/api/health` returns 200 in ~0.29s.
- ✅ **Memory is fine — `enable_logs` stays.** Post-deploy `memory_usage` is
  **152–172 MB** against a 536 MB limit, *below* the ~204 MB pre-change baseline. The
  SDK cost nothing measurable. (The 204 MB figure was a single stale datapoint from
  Jul 19, so treat 152–172 MB as the real baseline from here.)
- ✅ **`SENTRY_ENVIRONMENT=production` synced from the blueprint.** Worth knowing how:
  pushing to `main` produced *two* deploys — the commit deploy, then a second from the
  blueprint sync that applied the plain-value env var. `sync: false` values like
  `SENTRY_DSN` never arrive this way and must be set by hand.
- ⬜ **Not yet verified:** the three cron monitors. Sentry creates a monitor on its
  first check-in, so they appear only after the nightly job actually runs. Confirm
  after the first `0 7 * * *` run, or trigger `scheduled-jobs.yaml` via
  `workflow_dispatch`. Verifying earlier would have meant running the jobs against the
  production Neon database off-schedule.
- ⬜ **Not yet proven by a live event.** The config is verified, but no production
  error or transaction has reached Sentry yet — traces are sampled at 10% and the only
  traffic so far was `/api/health`, which the sampler drops by design. The first real
  error or cron check-in is the proof.

---

## Phase 2 — MLflow tracing + eval for the chat agent ✅ (built)

**Full write-up: [`chat-eval.md`](chat-eval.md)** — including the RAG evaluation
setup, the self-hosting-vs-API cost analysis, and why MLflow's backend store can
be a Neon branch.

Summary of what changed here: `chat_logger.py` is **deleted**. Its error paths now
call `sentry_sdk.capture_exception` in `routers/chat.py`, so chat failures that
were previously swallowed into an ephemeral file now surface in Phase 1's Sentry
project. MLflow stays out of production via the `evaluation` extra.

<details>
<summary>Original Phase 2 plan (superseded)</summary>

Local and CI only; nothing ships to Render (512 MB won't carry it).

`apps/ml_service/app/chat_tools.py` is a 1025-line agentic tool loop. Change a system
prompt or a tool description today and there's no way to know whether it got better or
worse. `chat_logger.py` writes JSONL into the same ephemeral `logs/` directory — that's
a log, not a measurement.

Plan: `mlflow.anthropic.autolog()` (the loop calls the Anthropic SDK directly, so
autolog captures it without restructuring), `@mlflow.trace(span_type=TOOL)` on the tool
functions, an eval dataset of 15–25 real garden questions with expected tool-call
sequences, and scorers for tool-selection correctness, groundedness, latency and cost.

**Overlap with Sentry, stated plainly:** Sentry's `AnthropicIntegration` already
captures `gen_ai.*` spans in production. That's *production telemetry* — what real
users experienced. MLflow is an *offline eval harness* — a fixed dataset you re-run to
compare versions. Different jobs; both are worth having.

</details>

## Phase 3 — Neon branching for safe migrations ✅ (built)

**Full write-up: [`migrations.md`](migrations.md).**

The hand-maintained `_POSTGRES_MIGRATIONS` list of raw `ALTER TABLE` statements is
gone. Postgres schema changes now go through Alembic (`alembic upgrade head` at
startup), are tested on a disposable Neon branch, and are guarded by a CI job that
builds the schema from revisions alone and asserts it matches `models.py`.

That CI check is the piece that would have caught the 2026-07-21 outage — verified by
reproducing the bug and watching `alembic check` fail on it.

## Phase 4 — Query performance visibility (planned)

`pg_stat_statements` is not installed, so Neon's `list_slow_queries` and
`explain_sql_statement` return an error. One `CREATE EXTENSION` unlocks both.
