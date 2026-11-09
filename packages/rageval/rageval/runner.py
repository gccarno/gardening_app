"""
Run a golden set through an adapter.

A run lives in ``<runs_dir>/<run_id>/``:

* ``manifest.json``   adapter + its describe(), golden hash, git sha, timestamps
* ``records.jsonl``   one RunRecord per item, appended as each finishes
* ``judgments.jsonl`` written by rageval.judges
* ``summary.json``    written by rageval.report

Records are appended one at a time, so a crash or a spent daily budget loses
nothing: re-running with the same ``run_id`` skips finished items. Runs are
sequential on purpose — free-tier rate limits make parallelism pointless, and
app adapters (the garden one shares a SQLite session) aren't thread-safe.
"""
from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from rageval.config import Config
from rageval.llm.openrouter import BudgetExhausted
from rageval.schema import (
    GoldenItem,
    Response,
    RunRecord,
    append_jsonl,
    file_hash,
    read_jsonl,
    sha,
    write_jsonl,
)


def load_golden(path: str | Path) -> list[GoldenItem]:
    items = read_jsonl(path, GoldenItem)
    ids = [i.id for i in items]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f'duplicate golden ids: {sorted(dupes)}')
    return items


def git_sha(cwd: Path) -> str | None:
    try:
        out = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=cwd,
                             capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=cwd,
                               capture_output=True, text=True, timeout=10)
        return out.stdout.strip() + ('-dirty' if dirty.stdout.strip() else '') if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_run(cfg: Config, ref: str) -> Path:
    """A run id, a path, or ``baseline:<name>``."""
    if ref.startswith('baseline:'):
        p = cfg.baselines_dir / ref.split(':', 1)[1]
    elif Path(ref).is_dir():
        p = Path(ref)
    else:
        p = cfg.runs_dir / ref
    if not (p / 'manifest.json').exists():
        raise FileNotFoundError(f'no run at {p}')
    return p


def load_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))


def load_records(run_dir: Path) -> list[RunRecord]:
    """Latest record per item (a retried item is appended again)."""
    latest: dict[str, RunRecord] = {}
    for r in read_jsonl(run_dir / 'records.jsonl', RunRecord):
        latest[r.item_id] = r
    return list(latest.values())


def run(
    cfg: Config,
    adapter,
    run_id: str | None = None,
    limit: int | None = None,
    item_ids: list[str] | None = None,
    retry_errors: bool = False,
    log: Callable[[str], None] = print,
) -> Path:
    golden = load_golden(cfg.golden_path)
    if item_ids:
        golden = [g for g in golden if g.id in set(item_ids)]
    if limit:
        golden = golden[:limit]

    run_id = run_id or f'{adapter.name}-{datetime.now():%Y%m%d-%H%M%S}'
    run_dir = cfg.runs_dir / run_id
    manifest_path = run_dir / 'manifest.json'
    describe = adapter.describe()
    g_hash = file_hash(cfg.golden_path)

    if manifest_path.exists():
        manifest = load_manifest(run_dir)
        if manifest['golden_hash'] != g_hash or manifest['describe'] != json.loads(json.dumps(describe, default=str)):
            raise RuntimeError(
                f'run {run_id} was started with a different golden set or system config; '
                'start a new run instead of resuming this one')
        log(f'resuming run {run_id}')
    else:
        manifest = {
            'run_id': run_id,
            'app': cfg.name,
            'adapter': adapter.name,
            'describe': describe,
            'config_hash': sha({'adapter': adapter.name, 'describe': describe}),
            'golden_path': str(cfg.golden_path),
            'golden_hash': g_hash,
            'git_sha': git_sha(cfg.root),
            'started_at': datetime.now(UTC).isoformat(),
        }
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding='utf-8')

    done = {r.item_id: r for r in load_records(run_dir)}
    todo = [g for g in golden
            if g.id not in done or (retry_errors and done[g.id].response.error)]
    log(f'{len(golden)} items, {len(golden) - len(todo)} already done, {len(todo)} to run')

    for n, item in enumerate(todo, 1):
        t0 = time.perf_counter()
        try:
            resp = adapter.answer(item)
        except BudgetExhausted as exc:
            log(f'stopped: {exc}\nresume with: --run-id {run_id}')
            break
        except Exception as exc:     # one broken item must not sink the run
            resp = Response(answer='', error=f'{type(exc).__name__}: {exc}')
        if resp.latency_ms is None:
            resp.latency_ms = (time.perf_counter() - t0) * 1000
        append_jsonl(run_dir / 'records.jsonl', RunRecord(item.id, item.question, resp))
        status = 'ERROR ' + resp.error[:80] if resp.error else f'{resp.latency_ms:.0f} ms'
        log(f'  [{n}/{len(todo)}] {item.id}: {status}')

    manifest['finished_at'] = datetime.now(UTC).isoformat()
    manifest['n_records'] = len(load_records(run_dir))
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding='utf-8')
    return run_dir


def snapshot(run_dir: Path, dest: Path) -> Path:
    """Copy a run's small files into ``dest`` (used to commit a baseline)."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'judgments.jsonl', 'summary.json'):
        src = run_dir / name
        if src.exists():
            (dest / name).write_bytes(src.read_bytes())
    write_jsonl(dest / 'records.jsonl', load_records(run_dir))   # deduped
    return dest
