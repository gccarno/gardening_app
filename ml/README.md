# ML Training

Training pipelines and feature engineering for the plant recommender.

## Pipeline

```bash
# 1. Generate synthetic training data (uses live DB — ~539K rows)
uv run python ml/data/generate_synthetic.py

# 2. Train — 5-fold CV, saves ml/models/recommender.pkl
uv run python ml/training/train_recommender.py
```

The trained model is a `GradientBoostingClassifier` over 7 features. Feature importances from training: season_match 41%, zone_match 39%, sunlight_match 18%.

If `recommender.pkl` is missing, the app falls back to the rule-based scorer in `apps/ml_service/app/recommender.py` — no training required to run the app.

## Structure

```
ml/
├── data/generate_synthetic.py    # Synthetic user–plant interaction generator
├── features/build_features.py    # Feature engineering (pure Python, no DB)
├── training/train_recommender.py # Train + cross-validate + save model
├── evaluation/metrics.py         # precision@k, recall@k, NDCG@k
├── eda/                          # Exploratory analysis scripts and outputs
└── models/recommender.pkl        # Trained model artifact (gitignored)
```

## EDA

```bash
uv sync --extra eda
uv run python ml/eda/explore_features.py
# Plots saved to ml/eda/plots/
```
