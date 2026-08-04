"""
Watering-model monitoring dashboard — a Streamlit app, run locally/on
demand. Deliberately NOT part of the product app (see
ml/docs/WATERING_MODEL.md §9): gardeners never see this; it's for whoever
is maintaining the model to check whether it (or the rule engine's baseline
assumptions) are drifting.

Reads MlWateringSnapshot directly from the live DB (DATABASE_URL).

Run:
    uv sync --extra monitoring
    uv run streamlit run ml/monitoring/dashboard.py
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

st.set_page_config(page_title='Watering Model Monitor', layout='wide')


@st.cache_data(ttl=300)
def load_snapshots() -> pd.DataFrame:
    from apps.backend.app.db.models import MlWateringSnapshot
    from apps.backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        rows = db.query(MlWateringSnapshot).all()
        cols = [c.name for c in MlWateringSnapshot.__table__.columns]
        data = [{c: getattr(r, c) for c in cols} for r in rows]
    finally:
        db.close()
    df = pd.DataFrame(data)
    if not df.empty:
        df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])
    return df


st.title('🌱 Watering Model Monitor')
st.caption('Reads MlWateringSnapshot directly — not part of the product app.')

# ── Model improvement across training runs ────────────────────────────────
# Rendered before the snapshot sections (and the empty-data st.stop() below)
# because it reads the local training history, not MlWateringSnapshot — it's
# useful even before any flywheel data has accumulated.
from ml.evaluation.metrics_history import load_history


def _runs_panel(model_name: str, metric_cols: list[str]) -> None:
    hist = load_history(model_name)
    if hist.empty:
        st.info(f'No `{model_name}` history yet. Run '
               f'`uv run python ml/training/train_{model_name}.py` to start accumulating it.')
        return
    hist = hist.sort_values('ts')
    present = [c for c in metric_cols if c in hist.columns]
    if present:
        st.line_chart(hist.set_index('ts')[present])
    if 'gate_passed' in hist.columns:
        passed = int(hist['gate_passed'].sum())
        st.metric('Training runs recorded', len(hist),
                 help=f'{passed} passed the gate, {len(hist) - passed} failed.')
    else:
        st.metric('Training runs recorded', len(hist))
    st.dataframe(hist.sort_values('ts', ascending=False))


st.header('Model improvement across training runs')
st.caption('Reads the local ml/models/*_metrics_history.jsonl written by the training '
          'scripts (gitignored — accrues on whichever machine runs training).')
st.subheader('Watering model')
_runs_panel('watering', ['decision_accuracy', 'decision_accuracy_vs_rule', 'mae'])
st.subheader('Plant recommender')
_runs_panel('recommender', ['precision@5', 'recall@5', 'ndcg@5'])

st.divider()
df = load_snapshots()

if df.empty:
    st.warning('No snapshot data yet. The nightly ml_snapshot job (or '
              'POST /api/admin/run-ml-snapshot) needs to have run at least once.')
    st.stop()

st.metric('Total snapshots', len(df))
c1, c2, c3 = st.columns(3)
c1.metric('Gardens', df['garden_id'].nunique())
c2.metric('Beds', df['bed_id'].nunique())
c3.metric('Date range', f"{df['snapshot_date'].min().date()} → {df['snapshot_date'].max().date()}")

labeled = df[df['watered_next_day'].notna()]

# ── Forecast accuracy ─────────────────────────────────────────────────────
st.header('Forecast accuracy: predicted vs. actual next-day rain')
fc = labeled.dropna(subset=['forecast_precip_mm_d1_d2', 'rain_next_day_mm'])
if fc.empty:
    st.info('No rows yet with both a d1/d2 forecast and a backfilled actual.')
else:
    fc = fc.copy()
    fc['forecast_error_mm'] = fc['forecast_precip_mm_d1_d2'] - fc['rain_next_day_mm']
    st.line_chart(fc.set_index('snapshot_date')[['forecast_precip_mm_d1_d2', 'rain_next_day_mm']])
    st.metric('Mean absolute forecast error (mm)', round(fc['forecast_error_mm'].abs().mean(), 2))

# ── Model performance over time on actual rainfall ────────────────────────
st.header('Model performance over time on actual rainfall')
perf = labeled.dropna(subset=['forecast_precip_mm_d1_d2', 'rain_next_day_mm'])
if perf.empty:
    st.info('No rows yet with both a d1/d2 forecast and a backfilled actual rainfall.')
else:
    perf = perf.sort_values('snapshot_date').copy()
    perf['abs_forecast_error_mm'] = (perf['forecast_precip_mm_d1_d2'] - perf['rain_next_day_mm']).abs()
    window = min(7, len(perf))
    perf['rolling_mae_mm'] = perf['abs_forecast_error_mm'].rolling(window, min_periods=1).mean()
    st.caption(f'Rolling {window}-snapshot mean absolute forecast error vs. actual next-day rain '
              f'(n={len(perf)}). A rising line means the rain signal the model relies on is degrading.')
    st.line_chart(perf.set_index('snapshot_date')[['rolling_mae_mm']])

    # Defer-to-rain: when meaningful rain actually fell, does the model back off?
    RAIN_MM = 5.0
    scored_perf = perf.dropna(subset=['model_pred_mm'])
    rained = scored_perf[scored_perf['rain_next_day_mm'] >= RAIN_MM]
    st.subheader(f'Defer-to-rain: model prediction on days ≥{RAIN_MM:.0f} mm rain actually fell')
    if rained.empty:
        st.info('No scored rows yet where meaningful rain actually fell '
               '(needs model_used=True rows with a backfilled wet day).')
    else:
        st.caption(f'On days the bed got real rain, model_pred_mm should trend low — the model '
                  f'correctly not calling for water (n={len(rained)}).')
        st.line_chart(rained.set_index('snapshot_date')[['model_pred_mm', 'rain_next_day_mm']])

# ── Model vs rule divergence ──────────────────────────────────────────────
st.header('Model vs. rule engine divergence')
scored = df.dropna(subset=['model_pred_mm'])
if scored.empty:
    st.info('No rows yet where the trained model was available (model_used=True). '
           'Train and commit ml/models/watering.pkl, then wait for the next nightly run.')
else:
    st.line_chart(scored.set_index('snapshot_date')[['model_pred_mm', 'rule_deficit_mm']])
    corr = scored[['model_pred_mm', 'rule_deficit_mm']].corr().iloc[0, 1]
    st.metric('Correlation (model prediction vs. rule deficit)',
             round(corr, 3) if pd.notna(corr) else 'n/a')

# ── Recommendation-followed rate ──────────────────────────────────────────
st.header('Recommendation-followed rate')
if labeled.empty:
    st.info('No labeled rows yet — labels backfill the night after each snapshot.')
else:
    rec = labeled.copy()
    rec['recommended'] = rec['rule_score'] >= 50
    followed = rec[rec['recommended']]
    rate = followed['watered_next_day'].mean() if len(followed) else None
    st.metric('When the engine said "water today / urgent", gardener actually watered',
             f'{rate:.0%}' if rate is not None else 'n/a', help=f'n={len(followed)}')
    st.bar_chart(rec.groupby('recommended')['watered_next_day'].mean())

# ── Feature drift ──────────────────────────────────────────────────────────
st.header('Feature drift (weekly means)')
feature_cols = ['rain_7d_mm', 'et0_7d_mm', 'temp_high_f', 'humidity_pct', 'days_since_watered']
drift = df.set_index('snapshot_date')[feature_cols].resample('W').mean()
st.line_chart(drift)

# ── Raw data ────────────────────────────────────────────────────────────────
with st.expander('Raw snapshot data'):
    st.dataframe(df.sort_values('snapshot_date', ascending=False))
