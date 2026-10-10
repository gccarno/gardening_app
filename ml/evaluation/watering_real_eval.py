"""
Honest evaluation of the watering model against REAL flywheel outcomes.

The training-time metric (ml/evaluation/watering_metrics.py) scores the model
against a synthetic formula. This harness scores what actually shipped against
what actually happened, using MlWateringSnapshot rows, and always shows the
baselines a decision-maker needs: never-water, always-water, and the rule
engine.

Caveats baked into the output, not hidden:
  * Rows before MIN_DATE had structurally always-negative labels (see
    ml/docs/WATERING_MODEL.md) and are dropped.
  * The label is mostly "rain >= 5 mm fell tomorrow" (apply_rain_as_watering),
    not a gardener's judgement. Rows are split into rain-credited vs. rain-free
    so that is visible.
  * `rule_score` stored in the snapshot is contaminated while the model was
    serving (it held the model's score). The rule call is recomputed here from
    the stored rule_deficit_mm + forecast fields. Wind and the drought class are
    not stored, so they take the neutral defaults.
  * Rows share weather across beds and days are autocorrelated, so confidence
    intervals come from a bootstrap that resamples whole DAYS, not rows.

Run (read-only, needs DATABASE_URL):
    uv run python ml/evaluation/watering_real_eval.py
"""
import random
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

MIN_DATE = date(2026, 8, 5)   # first day labels are trustworthy
MODEL_CUTOFF_MM = 1.5          # threshold the training metric used
SERVE_CUTOFF_SCORE = 50        # rule/serving "water today" cutoff
RAIN_CREDIT_MM = 5.0           # rain_next_day_mm at/above which the label is rain-credited


def rule_call(row: dict) -> bool | None:
    """Rule-engine 'water today' call recomputed from stored inputs."""
    from apps.ml_service.app.watering_engine import score_urgency
    deficit = row.get('rule_deficit_mm')
    if deficit is None:
        return None
    score = score_urgency(
        deficit,
        {'mm_day': row.get('mm_day_avg') or 4.0, 'drought': 'medium'},
        {'temp_max_c': row.get('forecast_temp_max_c'),
         'precip_prob': row.get('forecast_precip_prob_d0'),
         'precip_mm': row.get('forecast_precip_mm_d0')},
    )
    return score >= SERVE_CUTOFF_SCORE


def model_call(row: dict) -> bool | None:
    pred = row.get('model_pred_mm')
    return None if pred is None else pred > MODEL_CUTOFF_MM


def prepare(rows: list[dict]) -> list[dict]:
    """Keep trustworthy labelled rows and attach each predictor's call."""
    out = []
    for r in rows:
        if r.get('watered_next_day') is None or r['snapshot_date'] < MIN_DATE:
            continue
        out.append({**r,
                    'y': bool(r['watered_next_day']),
                    'rain_credited': (r.get('rain_next_day_mm') or 0) >= RAIN_CREDIT_MM,
                    'calls': {'model': model_call(r), 'rule': rule_call(r),
                              'never_water': False, 'always_water': True}})
    return out


def score(rows: list[dict], who: str) -> dict:
    """Confusion-matrix metrics for one predictor over rows that have a call."""
    pairs = [(r['y'], r['calls'][who]) for r in rows if r['calls'][who] is not None]
    n = len(pairs)
    if n == 0:
        return {'n': 0}
    tp = sum(y and c for y, c in pairs)
    fp = sum((not y) and c for y, c in pairs)
    fn = sum(y and (not c) for y, c in pairs)
    tn = n - tp - fp - fn
    recall = tp / (tp + fn) if tp + fn else None
    spec = tn / (tn + fp) if tn + fp else None
    return {
        'n': n,
        'accuracy': (tp + tn) / n,
        'balanced_accuracy': (recall + spec) / 2 if recall is not None and spec is not None else None,
        'precision': tp / (tp + fp) if tp + fp else None,
        'recall': recall,
        'call_rate': (tp + fp) / n,
    }


def day_bootstrap_diff(rows: list[dict], a: str, b: str, iters: int = 2000,
                       seed: int = 0) -> tuple[float, float, float] | None:
    """Paired accuracy difference (a - b) with a 95% interval from resampling
    whole days. Returns (point, lo, hi), or None if the predictors don't overlap."""
    by_day: dict = {}
    for r in rows:
        ca, cb = r['calls'][a], r['calls'][b]
        if ca is None or cb is None:
            continue
        d = by_day.setdefault(r['snapshot_date'], [0, 0, 0])  # n, a_correct, b_correct
        d[0] += 1
        d[1] += ca == r['y']
        d[2] += cb == r['y']
    days = list(by_day.values())
    if not days:
        return None

    def diff(sample):
        n = sum(d[0] for d in sample)
        return (sum(d[1] for d in sample) - sum(d[2] for d in sample)) / n

    rng = random.Random(seed)
    draws = sorted(diff([rng.choice(days) for _ in days]) for _ in range(iters))
    return diff(days), draws[int(0.025 * iters)], draws[int(0.975 * iters)]


def time_halves(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    days = sorted({r['snapshot_date'] for r in rows})
    mid = days[len(days) // 2] if days else None
    return ([r for r in rows if r['snapshot_date'] < mid],
            [r for r in rows if r['snapshot_date'] >= mid])


def _fmt(v):
    return '  n/a' if v is None else f'{v:5.2f}'


def _table(title: str, rows: list[dict]) -> None:
    pos = sum(r['y'] for r in rows)
    print(f'\n{title}  (n={len(rows)}, positives={pos}, days={len({r["snapshot_date"] for r in rows})})')
    print(f'  {"predictor":<14}{"n":>5}{"acc":>7}{"bal.acc":>9}{"prec":>7}{"recall":>8}{"call%":>7}')
    for who in ('never_water', 'always_water', 'rule', 'model'):
        s = score(rows, who)
        if not s['n']:
            continue
        print(f'  {who:<14}{s["n"]:>5}{_fmt(s["accuracy"]):>7}{_fmt(s["balanced_accuracy"]):>9}'
              f'{_fmt(s["precision"]):>7}{_fmt(s["recall"]):>8}{_fmt(s["call_rate"]):>7}')


def report(rows: list[dict]) -> None:
    if not rows:
        print('No trustworthy labelled rows.')
        return
    _table('ALL labelled rows', rows)
    _table('Rain-credited label (rain >= 5 mm next day)', [r for r in rows if r['rain_credited']])
    _table('Rain-free rows (positives here are real hand-waterings)', [r for r in rows if not r['rain_credited']])
    first, second = time_halves(rows)
    _table('First half of the period', first)
    _table('Second half of the period', second)

    d = day_bootstrap_diff(rows, 'model', 'rule')
    if d:
        print(f'\nModel minus rule accuracy: {d[0]:+.3f}  (95% day-bootstrap CI {d[1]:+.3f} .. {d[2]:+.3f})')
        print('  CI spanning 0 means no evidence either is better.')
    print('\nNote: the label is mostly rain-credited; treat accuracy as a sanity check, '
          'not a measure of whether watering advice was right.')


def load_rows() -> list[dict]:
    from apps.backend.app.db.models import MlWateringSnapshot
    from apps.backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        cols = [c.name for c in MlWateringSnapshot.__table__.columns]
        return [{c: getattr(s, c) for c in cols} for s in db.query(MlWateringSnapshot).all()]
    finally:
        db.close()


if __name__ == '__main__':
    report(prepare(load_rows()))
