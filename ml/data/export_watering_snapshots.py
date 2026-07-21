"""
Export real, labeled MlWateringSnapshot rows (the watering-model flywheel
data) to CSV for training. Only rows with a backfilled label
(watered_next_day is not null) are usable — see
apps/backend/app/jobs/ml_snapshot.py for how labels get backfilled nightly.

Also carries along `rule_score` (not a model feature — it's what the
deterministic rule engine said at snapshot time) so training can report
decision agreement between the trained model and the rule engine, not just
raw error against the label.

Requires DATABASE_URL (reads the live DB directly, read-only).

Run:
    uv run python ml/data/export_watering_snapshots.py
"""
import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features.watering_features import FEATURE_ORDER

OUT_PATH = _ROOT / 'ml' / 'data' / 'watering_snapshots.csv'

# Coarse mm-per-event mapping for a watered/not-watered outcome — we don't
# measure exact liters applied by the gardener, only the amount category
# they logged (see WateringEvent.amount), so this is necessarily approximate.
_AMOUNT_MM = {'light': 3.0, 'moderate': 6.0, 'heavy': 10.0}


def _label(snap) -> float | None:
    if snap.watered_next_day is None:
        return None
    if not snap.watered_next_day:
        return 0.0
    return _AMOUNT_MM.get(snap.watered_amount, 5.0)


def main():
    from apps.backend.app.db.models import MlWateringSnapshot
    from apps.backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        snapshots = (db.query(MlWateringSnapshot)
                     .filter(MlWateringSnapshot.watered_next_day.isnot(None))
                     .all())
    finally:
        db.close()

    rows = []
    for snap in snapshots:
        label = _label(snap)
        if label is None:
            continue
        row = {k: getattr(snap, k) for k in FEATURE_ORDER}
        row['water_mm_today'] = label
        row['rule_score'] = snap.rule_score
        rows.append(row)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_ORDER + ['water_mm_today', 'rule_score'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'Exported {len(rows)} labeled snapshot rows -> {OUT_PATH}')


if __name__ == '__main__':
    main()
