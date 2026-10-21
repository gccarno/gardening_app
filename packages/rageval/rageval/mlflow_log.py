"""Optional: log a run summary to MLflow. A no-op when mlflow isn't installed."""
from __future__ import annotations

from pathlib import Path


def log_summary(summary: dict, run_dir: Path, experiment: str, tracking_uri: str | None = None) -> bool:
    try:
        import mlflow
    except ImportError:
        return False
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    m = summary['manifest']
    with mlflow.start_run(run_name=m['run_id']):
        mlflow.log_params({'adapter': m['adapter'], 'golden_hash': m['golden_hash'],
                           'git_sha': m.get('git_sha'), **{f'sut.{k}': str(v)[:250]
                                                           for k, v in m['describe'].items()}})
        for name, d in summary['metrics'].items():
            if d.get('mean') is not None:
                mlflow.log_metric(name, d['mean'])
        for k, v in summary['ops'].items():
            if isinstance(v, (int, float)):
                mlflow.log_metric(f'ops.{k}', v)
        for f in ('summary.json', 'report.md', 'report.html'):
            if (run_dir / f).exists():
                mlflow.log_artifact(str(run_dir / f))
    return True
