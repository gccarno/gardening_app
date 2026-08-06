# Watering Model — ML Lifecycle

This document explains the watering-recommendation ML system: why it exists,
how it's built, and how it's operated. It follows the 10-step lifecycle from
Andriy Burkov's *Machine Learning Engineering*. It is **evergreen** — it
describes the system as it currently exists, not a changelog of how it got
there. When the implementation changes, this doc should change with it.

The companion plant-recommender pipeline (`ml/README.md`, `ml/training/train_recommender.py`)
is a separate model (what-to-plant, not watering) and follows the same
project layout — read that first if the structure here looks familiar.

---

## 1. Business problem

Plants need the right amount of water to grow. Too little and they're
stressed or die; too much wastes water, leaches nutrients, and can drown
roots or invite disease. A gardener checking every bed by hand every day
doesn't scale, especially across beds with different plants, soil, and
maturity stages.

## 2. Goal definition

Give the gardener a daily, per-bed answer to two questions: *should I water
today or tomorrow, and if so, how much?* That recommendation is surfaced
in two places that already exist in the app — the web Dashboard's watering
card and Android's push notifications (rain-skipped when the forecast makes
watering unnecessary) — so this project changes what powers the
recommendation, not how the user receives it.

**Decision:** keep the existing `GET /api/gardens/{id}/watering-status`
response shape and thresholds (score ≥ 50 = water today, ≥ 75 = urgent) as
the contract. A model that predicts water amount converts cleanly into that
same shape, so both clients light up with zero changes.
**Alternatives considered:** a new endpoint / new response shape. Rejected —
it would require coordinated client changes on web and Android before any
benefit is visible, for no functional gain.

## 3. Data collection & preparation

**Decision:** two tiers of storage, sized for what they're for.
- **Operational (7-day rolling window):** `WeatherLog` (observed rainfall,
  temperature, humidity, ET0) and `WateringEvent` (append-only log of actual
  watering actions) are pruned nightly to the last 7 days. This is exactly
  the state the rule engine and the live model need to score today's
  recommendation — nothing older is read at serving time.
- **Training/monitoring (unbounded):** `MlWateringSnapshot`, one row per bed
  per day, accumulates indefinitely. It's the flywheel: features computed
  each night, plus the label backfilled two nights later (did the bed get
  watered? how much rain actually fell?). This is what training and the
  monitoring dashboard read from.

  **Why two nights, not one (fixed 2026-08-05):** a snapshot taken on day D
  asks what happened on D+1, and neither answer exists while D+1 is still
  running. The job fires around 04:00 local, so labelling D-1 from "today"
  meant asking whether the gardener had watered in the four hours since
  midnight, and reading a `WeatherLog` row for today that is never written by
  design (the fetcher skips today as a partial day). Both labels were
  therefore constants: **66 labelled rows, 0 positives, every
  `rain_next_day_mm` 0.0** — including across 2.03in of rain on 2026-08-02.
  `_backfill_labels` now labels every still-unlabelled snapshot from D-2 back
  to the 7-day retention edge, so a missed night is recoverable rather than a
  permanent null.

**Rainfall source — decision:** stop asking the user to log rainfall.
Tomorrow.io's `/history/recent` endpoint gives yesterday's observed rainfall
per garden coordinate, so the nightly job pulls that automatically (Open-Meteo's
archive API remains a fallback when Tomorrow.io is unavailable). The manual
`POST /gardens/{id}/log-rain` endpoint stays as a backend fallback (e.g. a
garden with no coordinates), but the web/Android UI for it was removed —
manually logging rain next to an automatic feed just invites double-counting
and conflicting values.
**Why:** the user's explicit instruction — rainfall should come from the
weather API, not be a chore for the gardener.

Because Tomorrow.io's history window is only ~24h, a missed nightly run used
to leave a permanent hole in the 7-day window (2026-08-01 is one) that
silently understated `rain_7d_mm`. The fetcher now diffs the window against
what's stored and closes any gaps from the Open-Meteo archive, which does
cover 7 days. Gap-fill never raises — yesterday's data is the point of the
run — and never overwrites a day that already has a row, so manual rain logs
survive.

**Rain counts as watering — decision (2026-08-05):** a day with ≥5mm
*effective* rain (~0.2in, after the existing 2mm interception allowance)
credits every planted bed with a `WateringEvent(source='rain')` and advances
`last_watered`, exactly as if the gardener had watered by hand. Amount bands
mirror the mm-per-event mapping training already uses: light <8mm,
moderate <15mm, heavy above. It is idempotent per bed/day, a gardener's own
logged event always wins, and `last_watered` only ever moves forward.
**Why:** the user's instruction — "previous rain should be treated the same
as a gardener doing the watering." It also fixes a real distortion: with no
watering ever logged, `days_since_watered` sat at 999 for every bed on every
snapshot, permanently pinning the deficit calculation to its 7-day cap and
denying the flywheel any positive examples.

**Bootstrapping labels — decision:** before any real usage data exists,
synthetic training data is generated from the *existing rule-based engine*
(`apps/ml_service/app/watering_engine.py`) run across a grid of plausible
conditions, with noise added. This is what trains v1 of the model. As real
`MlWateringSnapshot` rows accumulate from actual gardens, `ml/data/export_watering_snapshots.py`
exports them and future retrains blend in (eventually favor) real data.
**Why:** Burkov's pattern of "ship a heuristic, learn from its own
predictions plus outcomes, then replace it" — there's no cold-start problem
because the rule engine's physics already encode real domain knowledge.

## 4. Feature engineering

**Decision:** one shared feature-building function
(`ml/features/watering_features.py`), imported by both the training scripts
and the serving code path. This guarantees training/serving parity — a
common and easy-to-miss source of bugs where the model is trained on
features computed one way and served on features computed a subtly
different way.

Features fall into four groups:
- **Water balance:** 7-day observed rainfall and ET0 (evapotranspiration),
  days since last watered, forecast precipitation for today and the next two
  days (used instead of just "did it rain" — we're deciding *ahead* of the
  need, not reacting to a deficit that already happened).
- **Atmosphere:** temperature high/low, humidity, forecast max temperature.
- **Plant biology:** species water need (Kc / mm-day from the existing crop
  table, or the `PlantLibrary.water` category as fallback), plant maturity
  (days since planted, fraction of the bed still at seedling stage).
- **Soil/bed:** sand/clay percentage, bed area.

**Maturity handling — decision:** maturity is both an input feature *and* a
serving-time shaping rule. The model predicts a single "water need in mm"
number; seedling-heavy beds then get that need capped per watering event
with more frequent smaller waterings suggested, while mature beds get the
full predicted depth in fewer, deeper waterings. This matches how drip/hand
watering actually should be scheduled — a single regression number for
"total water needed" doesn't by itself say how to split it into events, so
that split is applied deterministically, not learned (there isn't enough
labeled data yet to learn scheduling, only depth).

## 5. Model training

**Decision:** start with linear regression (`sklearn.linear_model.Ridge`)
predicting `water_mm_today`, and compare it against
`GradientBoostingRegressor` in the same training run. Whichever wins on
held-out decision accuracy (water/no-water, not just raw error) is what gets
saved. Per the project's own instruction, we don't reach for the more
complex model unless it earns it.

Training happens **offline**, run from the command line or CI — never
inside the running app. `ml/training/train_watering.py` mirrors
`ml/training/train_recommender.py`: load CSV(s), 5-fold cross-validation,
retrain on the full dataset, pickle the winner to `ml/models/watering.pkl`.

## 6. Model evaluation

**Decision:** report MAE/RMSE on predicted mm, but the metric that actually
matters is **decision accuracy against the rule engine baseline** — does the
model agree with (or improve on) the water/no-water call the deterministic
engine would have made at the same deficit threshold? A model with lower MAE
but worse decision accuracy than the rule engine isn't an improvement for
this product. `ml/evaluation/watering_metrics.py` computes both.

`ml/training/train_watering.py` turns this into a hard gate: it compares
against the rule engine (`decision_accuracy_vs_rule`) whenever real, labeled
`MlWateringSnapshot` data with a `rule_score` is available, and otherwise
falls back to a plain `decision_accuracy` floor of 0.55 (a coin-flip-plus-
margin sanity check for synthetic-only runs, where there's no rule score to
compare against). Training exits non-zero and does not save a pickle if the
gate isn't met — this is what CI uses to decide whether a retrain is safe to
promote.

Every training run (pass *or* fail) appends its metrics to a local,
gitignored history file (`ml/models/watering_metrics_history.jsonl`) via
`ml/evaluation/metrics_history.py`, so improvement across retrains is
answerable — see step 9. CI still keeps its own per-run `train_report.txt`
artifact; the history file grows unbounded and is a local operational record,
not source.

## 7. Model deployment

**Decision:** the trained artifact (`ml/models/watering.pkl`) is committed
to git, exactly like the existing `ml/models/recommender.pkl`. Render
redeploys on every push to main, so committing the pickle *is* the
deployment step — no separate artifact registry, no download-at-boot logic.
**Why:** simplest option that fits how this app is already deployed (a
single free-tier host with git-triggered deploys); anything fancier (S3/GCS
artifact store, model registry) is unjustified complexity at this scale.

Promotion is **manual**: the monthly training CI workflow
(`.github/workflows/train_model.yaml`) trains, evaluates against the gate,
and uploads the pickle + metrics report as a workflow artifact. A human
reviews the metrics and commits the new pickle themselves. Auto-merge was
considered and rejected — at this stage the point is to *see* what each
retrain changes, not to automate trust that hasn't been earned yet.

## 8. Model serving

**Decision:** serve the model *inside the existing backend*, behind the
existing `GET /api/gardens/{id}/watering-status` endpoint, exactly the
pattern `apps/ml_service/app/recommender.py` already uses for the plant
recommender. `apps/ml_service/app/watering_model.py` lazy-loads the pickle;
`watering_engine.get_watering_recommendations()` calls it when available and
falls back to the untouched rule-based calculation when the artifact is
missing, fails to load, or throws. The response gains two additive fields
(`model_used`, `predicted_mm`) — every field the web and Android clients
already read is unchanged, so this requires no client-side changes to take
effect.
**Alternatives considered:** a standalone model-serving API (e.g. a small
FastAPI/Flask service just for inference). Rejected for now — the model is
small enough (Ridge/GBR on ~17 features) that in-process inference costs
nothing meaningful, and a separate service would mean a second thing to
deploy and keep alive on free-tier hosting for no real benefit yet. Worth
reconsidering only if the model grows into something with real cold-start
cost (e.g. a neural network).

**`forecast_precip_mm_d1_d2` is fetched everywhere (fixed 2026-08-05).** This
feature — tomorrow + the day after's predicted rain, the signal that lets the
model decide "skip today because rain's coming tomorrow," per the original
goal — used to be skipped on the live path to save an API call, leaving it at
its default of "no rain expected" while the nightly snapshot fetched it for
real.

That was not the cheap tradeoff it looked like. On 2026-08-01, with 96.2mm
forecast over the following two days, the same bed scored **40 (consider) in
the nightly snapshot and 100 (urgent) from the API** — the endpoint told the
gardener to water urgently on the eve of four inches of rain.

Both paths now call `watering_engine.fetch_forecast_window()`, which returns
`(forecast_today, precip_d1_d2)` from a *single* 7-day request. The quota
concern that motivated the gap does not apply: the watering-status endpoint
was already making one forecast call, so this costs no extra requests, and
the nightly job dropped from two calls per garden to one.

## 9. Model monitoring

**Decision:** a standalone Streamlit app (`ml/monitoring/dashboard.py`),
run locally or on demand — **not** part of the product app, per the user's
explicit intent to keep monitoring separate from what gardeners see. It
reads `MlWateringSnapshot` directly and shows: forecast-vs-actual rainfall
error (including a rolling over-time trend and a "defer-to-rain" view — does
the model back off when real rain fell?), how much the model's predictions
diverge from the rule engine over time, the rate at which users actually
water when the system recommends it, feature drift (are the
gardens/seasons/species in the data changing shape over time), and — from the
local `*_metrics_history.jsonl` files written at training time (step 6) — the
improvement trajectory across training runs. These are the signals that would
tell us the model needs attention before a gardener notices bad
recommendations.

## 10. Model maintenance

The loop closes back into steps 3–4: `MlWateringSnapshot` keeps
accumulating real outcomes every night, the monitoring dashboard is the
place to periodically check whether the model or the rule engine's baseline
assumptions are drifting, and `export_watering_snapshots.py` +
`train_watering.py` is how a retrain incorporates that real data. When to
retrain, and when it's worth moving past Ridge/GBR to something more
complex, should be a judgment call made by looking at the dashboard's
divergence, drift, and cross-run improvement charts — not an automatic
trigger — since at this data volume automated retraining risks overfitting to
a small, seasonal, single-app dataset.

---

## Quick reference

```
ml/
├── docs/WATERING_MODEL.md            # this file
├── features/watering_features.py     # shared train/serve feature builder
├── data/generate_watering_synthetic.py  # v1 bootstrap data from the rule engine
├── data/export_watering_snapshots.py    # v2+ real flywheel data from the live DB
├── training/train_watering.py        # Ridge vs GBR, 5-fold CV, saves the pickle
├── evaluation/watering_metrics.py    # MAE/RMSE + decision accuracy vs. baseline
├── evaluation/metrics_history.py     # append/load per-run training history (gitignored)
├── models/watering.pkl               # committed artifact, loaded at serve time
└── monitoring/dashboard.py           # Streamlit, run locally, reads MlWateringSnapshot
```

Serving integration: `apps/ml_service/app/watering_model.py` (loader) →
`apps/ml_service/app/watering_engine.py` (`get_watering_recommendations`) →
`apps/backend/app/routers/weather.py` (`GET /gardens/{id}/watering-status`).

Nightly job sequence (`.github/workflows/scheduled-jobs.yaml` →
`POST /api/admin/run-weather-fetch` then `run-ml-snapshot`): fetch observed
rainfall → backfill yesterday's snapshot labels → compute today's snapshot
features → prune `WeatherLog`/`WateringEvent` older than 7 days.
