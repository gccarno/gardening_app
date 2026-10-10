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


def bucket_call(row: dict) -> bool:
    """Bucket-model prototype (ml/experiments/water_balance.py), approximated
    from the snapshot's 7-day sums."""
    from ml.experiments.water_balance import from_snapshot
    return from_snapshot(row)['water_today']


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
                              'bucket': bucket_call(r),
                              'never_water': False, 'always_water': True}})
    return out


# ── Soil moisture check-ins: the real ground truth ───────────────────────────

CHECKIN_LOOKBACK_DAYS = 14   # bucket spin-up: starts full this many days back


def score_checkins(items: list[dict]) -> dict:
    """items: [{'level': 'dry'|'ok'|'wet', 'depletion_frac': float, 'water_today': bool}].

    Two questions, because n will be small for a long time:
      * ordering: is the bucket's depletion higher on days the gardener said
        dry than ok, and ok than wet? (mean depletion per level)
      * the call: does water_today match "dry" (and not-water match ok/wet)?
    """
    by_level: dict = {}
    for it in items:
        by_level.setdefault(it['level'], []).append(it)
    agree = sum((it['level'] == 'dry') == it['water_today'] for it in items)
    return {
        'n': len(items),
        'agreement': agree / len(items) if items else None,
        'mean_depletion_frac': {lvl: sum(i['depletion_frac'] for i in xs) / len(xs)
                                for lvl, xs in by_level.items()},
        'counts': {lvl: len(xs) for lvl, xs in by_level.items()},
    }


def checkin_items(db) -> list[dict]:
    """Replay the bucket from daily WeatherLog + hand-watering rows up to each
    check-in. Rain-credited WateringEvents are skipped: the rain itself is
    already in WeatherLog, and counting both would refill the bucket twice."""
    from datetime import timedelta
    from apps.backend.app.db.models import (GardenBed, SoilMoistureCheckin, WateringEvent,
                                            WeatherLog)
    from apps.ml_service.app.watering_engine import get_plant_kc
    from ml.experiments.water_balance import Bed, recommend, simulate

    items = []
    for c in db.query(SoilMoistureCheckin).order_by(SoilMoistureCheckin.check_date).all():
        bed = db.get(GardenBed, c.bed_id)
        plants = [bp.plant for bp in bed.bed_plants if bp.plant] if bed else []
        if not plants:
            continue
        kcs = [get_plant_kc(p.name, p.library_entry.water if p.library_entry else None)['kc']
               for p in plants]
        stages = [bp.stage or 'seedling' for bp in bed.bed_plants if bp.plant]
        model_bed = Bed.from_soil(
            kc=sum(kcs) / len(kcs), sand_pct=bed.sand_pct, clay_pct=bed.clay_pct,
            compost_pct=bed.compost_pct, bed_depth_ft=bed.depth_ft,
            seedling_frac=sum(s == 'seedling' for s in stages) / len(stages))

        start = c.check_date - timedelta(days=CHECKIN_LOOKBACK_DAYS)
        logs = {lg.date: lg for lg in db.query(WeatherLog).filter(
            WeatherLog.garden_id == c.garden_id,
            WeatherLog.date >= start, WeatherLog.date <= c.check_date)}
        watered = {ev.event_date for ev in db.query(WateringEvent).filter(
            WateringEvent.bed_id == c.bed_id, WateringEvent.source != 'rain',
            WateringEvent.event_date >= start, WateringEvent.event_date < c.check_date)}

        days = []
        for i in range(CHECKIN_LOOKBACK_DAYS):
            d = start + timedelta(days=i)
            lg = logs.get(d)
            days.append({'et0_mm': lg.et0_mm if lg else None,
                         'rain_mm': (lg.rainfall_in or 0) * 25.4 if lg else 0.0,
                         'watered': d in watered})
        today = logs.get(c.check_date)
        rec = recommend(simulate(model_bed, days), model_bed,
                        et0_today_mm=today.et0_mm if today else None)
        items.append({'level': c.level, 'water_today': rec['water_today'],
                      'depletion_frac': rec['depletion_mm'] / max(rec['taw_mm'], 0.1),
                      'weather_days': len(logs)})
    return items


def checkin_report(items: list[dict]) -> None:
    print('\nSOIL MOISTURE CHECK-INS (bucket model vs the gardener\'s own reading)')
    if not items:
        print('  No check-ins yet. Readings start accruing from 2026-10-10; '
              'this is the evaluation that matters.')
        return
    s = score_checkins(items)
    thin = sum(1 for it in items if it['weather_days'] < CHECKIN_LOOKBACK_DAYS)
    print(f'  n={s["n"]}  counts={s["counts"]}  agreement(dry<->water)={s["agreement"]:.2f}')
    print('  mean depletion (fraction of the bucket) by reading; should rise wet < ok < dry:')
    for lvl in ('wet', 'ok', 'dry'):
        if lvl in s['mean_depletion_frac']:
            print(f'    {lvl:<4} {s["mean_depletion_frac"][lvl]:.2f}')
    if thin:
        print(f'  {thin} check-in(s) had under {CHECKIN_LOOKBACK_DAYS} days of weather; '
              'missing days default to 3.5 mm ET0 and no rain.')


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
    for who in ('never_water', 'always_water', 'rule', 'model', 'bucket'):
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

    for a in ('model', 'bucket'):
        d = day_bootstrap_diff(rows, a, 'rule')
        if d:
            print(f'\n{a.capitalize()} minus rule accuracy: {d[0]:+.3f}  '
                  f'(95% day-bootstrap CI {d[1]:+.3f} .. {d[2]:+.3f})')
    print('  A CI spanning 0 means no evidence either is better.')
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

    from apps.backend.app.db.session import SessionLocal
    _db = SessionLocal()
    try:
        checkin_report(checkin_items(_db))
    finally:
        _db.close()
