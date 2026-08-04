"""
Durable, local record of training-run metrics — one JSON line per run.

Training scripts print their metrics to stdout and CI keeps a per-run
artifact, but neither answers "did this retrain actually improve on the last
one?". This appends every run to ml/models/{model_name}_metrics_history.jsonl
so the monitoring dashboard can chart the improvement trajectory over time.

The history file is intentionally gitignored: it grows unbounded and is a
local operational record, not source. It accrues wherever training is run
(a developer's machine), which is also where the dashboard reads it.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = _ROOT / 'ml' / 'models'


def _history_path(model_name: str) -> Path:
    return MODELS_DIR / f'{model_name}_metrics_history.jsonl'


def _to_native(o):
    """json default for numpy scalars (np.float64/np.bool_ etc.), which the
    metric math produces — convert via .item() to a plain Python type."""
    if hasattr(o, 'item'):
        return o.item()
    raise TypeError(f'Object of type {type(o).__name__} is not JSON serializable')


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'


def append_run(model_name: str, metrics: dict, extra: dict | None = None) -> None:
    """Append one run's metrics as a JSON line to the model's history file.

    `metrics` is the metric dict as computed by training (e.g. mae, rmse,
    decision_accuracy). `extra` carries run context (model_type, n_rows,
    gate_passed, …). Records failed-gate runs too — a rejected retrain is
    still signal.
    """
    record = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'git_sha': _git_sha(),
        **(extra or {}),
        **metrics,
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(_history_path(model_name), 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, default=_to_native) + '\n')


def load_history(model_name: str):
    """Read a model's history into a DataFrame (empty if the file is absent).

    pandas is imported here, not at module top, so training scripts (which
    don't need it) aren't forced to pull it in.
    """
    import pandas as pd

    path = _history_path(model_name)
    if not path.exists():
        return pd.DataFrame()
    records = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    df = pd.DataFrame(records)
    if not df.empty and 'ts' in df:
        df['ts'] = pd.to_datetime(df['ts'])
    return df
