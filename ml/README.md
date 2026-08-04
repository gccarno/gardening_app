# ML

This directory holds the offline machine-learning work for the garden app:
data generation, feature engineering, training, evaluation, monitoring, and
the committed model artifacts. Two independent models live here, sharing one
layout and one convention (each falls back to a rule-based scorer if its
pickle is missing, so the app always runs even with no trained model):

| Model | Answers | Type | Artifact | Deep-dive |
|-------|---------|------|----------|-----------|
| **Plant recommender** | *what to plant* | `GradientBoostingClassifier` (ranking) | `models/recommender.pkl` | this README |
| **Watering** | *how much / when to water* | `Ridge` vs `GradientBoostingRegressor` | `models/watering.pkl` | [`docs/WATERING_MODEL.md`](docs/WATERING_MODEL.md) |

Both pickles are **committed to git** — Render redeploys on every push to
`main`, so committing the pickle *is* the deployment step (no artifact
registry, no download-at-boot). The training-run history files
(`models/*_metrics_history.jsonl`) are the only things under `models/` that
are gitignored.

The watering model is documented end-to-end in
[`docs/WATERING_MODEL.md`](docs/WATERING_MODEL.md), organised on Andriy
Burkov's 10-step ML lifecycle. This README is the hub; that doc is the
watering deep-dive.

## Lifecycle map

Every stage of the lifecycle, and the file that owns it for each model:

| Stage | Plant recommender | Watering model |
|-------|-------------------|----------------|
| 1. Business problem / 2. Goal | ranking of plants to a garden's conditions | per-bed daily water/how-much — see [doc §1–2](docs/WATERING_MODEL.md) |
| 3. Data collection | `data/generate_synthetic.py` → `synthetic_training.csv` | `data/generate_watering_synthetic.py` (v1 bootstrap) + `data/export_watering_snapshots.py` (real flywheel from `MlWateringSnapshot`) — see [doc §3](docs/WATERING_MODEL.md) |
| 4. Feature engineering | `features/build_features.py` | `features/watering_features.py` (shared train/serve encoder, `FEATURE_ORDER`) — see [doc §4](docs/WATERING_MODEL.md) |
| 5. Training | `training/train_recommender.py` (5-fold CV) | `training/train_watering.py` (5-fold CV, Ridge vs GBR) — see [doc §5](docs/WATERING_MODEL.md) |
| 6. Evaluation | `evaluation/metrics.py` (precision@k, recall@k, NDCG@k) | `evaluation/watering_metrics.py` (MAE/RMSE + decision accuracy vs. rule engine; hard gate) — see [doc §6](docs/WATERING_MODEL.md) |
| 7. Deployment | commit `models/recommender.pkl` | commit `models/watering.pkl`; monthly CI + manual promotion — see [doc §7](docs/WATERING_MODEL.md) |
| 8. Serving | `apps/ml_service/app/recommender.py` | `apps/ml_service/app/watering_model.py` → `watering_engine.py` → `GET /gardens/{id}/watering-status` — see [doc §8](docs/WATERING_MODEL.md) |
| 9. Monitoring | — | `monitoring/dashboard.py` (Streamlit, reads `MlWateringSnapshot`) — see [doc §9](docs/WATERING_MODEL.md) |
| 10. Maintenance | retrain on new synthetic data | flywheel: `MlWateringSnapshot` accrues nightly; retrain blends in real data — see [doc §10](docs/WATERING_MODEL.md) |

The nightly flywheel job that feeds the watering model's data and monitoring
lives outside `ml/`, in `apps/backend/app/jobs/ml_snapshot.py` (wired into
APScheduler in `main.py` and `.github/workflows/scheduled-jobs.yaml`).

## Commands

```bash
# ── Plant recommender ──────────────────────────────────────────────────
uv run python ml/data/generate_synthetic.py      # → ml/data/synthetic_training.csv
uv run python ml/training/train_recommender.py    # 5-fold CV → ml/models/recommender.pkl

# ── Watering model ─────────────────────────────────────────────────────
uv run python ml/data/generate_watering_synthetic.py   # v1 bootstrap CSV
uv run python ml/data/export_watering_snapshots.py      # v2+ real data (needs DATABASE_URL)
uv run python ml/training/train_watering.py             # Ridge vs GBR → ml/models/watering.pkl

# ── Monitoring dashboard ───────────────────────────────────────────────
uv sync --extra monitoring
uv run streamlit run ml/monitoring/dashboard.py

# ── EDA (recommender) ──────────────────────────────────────────────────
uv sync --extra eda
uv run python ml/eda/explore_features.py         # plots → ml/eda/plots/
```

If a model's pickle is missing, its serving code falls back to the
rule-based scorer (`apps/ml_service/app/recommender.py` /
`watering_engine.py`) — no training is required to run the app.

## Tracking model improvement

Training metrics used to exist only as stdout and a 90-day CI artifact, so
there was no way to see whether a retrain actually beat the last one. Now
every training run appends one JSON line to a local history file via
`evaluation/metrics_history.py`:

- `models/watering_metrics_history.jsonl` — model type, row count, MAE/RMSE,
  decision accuracy (and `decision_accuracy_vs_rule` when real data is
  present), gate pass/fail, git SHA, timestamp. **Failed-gate runs are
  recorded too** — a rejected retrain is still signal.
- `models/recommender_metrics_history.jsonl` — precision@5 / recall@5 /
  NDCG@5 per run.

These files are **gitignored** — they grow unbounded and are a local
operational record, not source. They accrue on whichever machine runs
training, which is also where the monitoring dashboard reads them (its
"Model improvement across training runs" section charts the trajectory).

CI (`.github/workflows/train_model.yaml`) keeps its own per-run
`train_report.txt` artifact and runs on ephemeral runners, so it does **not**
accumulate the gitignored history — that's intended. Promotion is manual: CI
uploads the retrained pickle + report, a human reviews the metrics and
commits the new pickle themselves.

## Monitoring

`monitoring/dashboard.py` is a standalone Streamlit app (run locally, **not**
part of the product app — gardeners never see it). It reads
`MlWateringSnapshot` directly from the live DB plus the local training
history, and shows:

- **Forecast accuracy** — predicted vs. actual next-day rain, mean absolute error.
- **Model performance over time on actual rainfall** — rolling forecast error,
  and a defer-to-rain view (does the model back off when real rain fell?).
- **Model vs. rule divergence** — how far the model's predictions drift from
  the rule engine over time.
- **Recommendation-followed rate** — did gardeners water when the engine said to?
- **Feature drift** — weekly means of the key input features.
- **Model improvement across training runs** — the metrics-history trajectory.

## Structure

```
ml/
├── data/
│   ├── generate_synthetic.py           # recommender: synthetic interaction data
│   ├── generate_watering_synthetic.py  # watering: v1 bootstrap from the rule engine
│   └── export_watering_snapshots.py    # watering: v2+ real flywheel data from live DB
├── features/
│   ├── build_features.py               # recommender feature engineering
│   └── watering_features.py            # watering: shared train/serve encoder
├── training/
│   ├── train_recommender.py            # 5-fold CV → recommender.pkl
│   └── train_watering.py               # Ridge vs GBR, 5-fold CV, gate → watering.pkl
├── evaluation/
│   ├── metrics.py                      # recommender: precision@k, recall@k, NDCG@k
│   ├── watering_metrics.py             # watering: MAE/RMSE + decision accuracy
│   └── metrics_history.py              # append/load per-run training history (both models)
├── monitoring/
│   └── dashboard.py                    # Streamlit monitor (run locally)
├── eda/                                # recommender exploratory analysis + plots
├── docs/
│   └── WATERING_MODEL.md               # watering model, full 10-step lifecycle
└── models/
    ├── recommender.pkl                 # committed artifact
    ├── watering.pkl                    # committed artifact
    └── *_metrics_history.jsonl         # gitignored, local training-run history
```
