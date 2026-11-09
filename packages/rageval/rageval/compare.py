"""
Regression gate: baseline run vs candidate run on the same golden items.

For every metric both runs have: paired bootstrap CI of (candidate - baseline)
and, for binary metrics, an exact McNemar test. A metric **regresses** when the
drop is both significant (CI upper bound < 0) and material (point drop larger
than ``tolerance``), or when the candidate falls under the metric's ``floor``.

Only *trusted* metrics can fail the gate: deterministic metrics always are;
judge metrics only when calibration says the panel agrees with human labels for
that criterion (``gate.allow_uncalibrated: true`` overrides — use sparingly).
Untrusted metrics are still reported.

Both runs must be judged by the *current* panel. Judging is cached by answer, so
re-judging a baseline after a panel change costs judge calls only — the system
under test is never re-run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rageval import stats
from rageval.calibration import calibration_status
from rageval.metrics import ops_stats
from rageval.report import fmt, item_values, markdown_to_html
from rageval.runner import load_manifest, load_records

# Metrics where lower is better. Everything else: higher is better.
LOWER_IS_BETTER = {'error', 'refused'}
# Informational only — never gate on these.
NEVER_GATE = {'refused'}


@dataclass
class MetricRow:
    name: str
    n: int
    base: float | None
    cand: float | None
    diff: float | None
    lo: float | None
    hi: float | None
    mcnemar_p: float | None
    trusted: bool
    status: str           # ok | REGRESSION | below_floor | improved | untrusted | n/a


@dataclass
class CompareResult:
    baseline: str
    candidate: str
    rows: list[MetricRow]
    warnings: list[str] = field(default_factory=list)
    ops: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not any(r.status in ('REGRESSION', 'below_floor') for r in self.rows)


def compare(cfg, base_dir: Path, cand_dir: Path, scorers=None, shadow_price=None,
            seed: int = 0) -> CompareResult:
    warnings = []
    bm, cm = load_manifest(base_dir), load_manifest(cand_dir)
    if bm['golden_hash'] != cm['golden_hash']:
        warnings.append('golden sets differ; comparing only items present in both runs')
    if bm['adapter'] != cm['adapter']:
        warnings.append(f"different adapters: {bm['adapter']} vs {cm['adapter']}")

    cal, status = calibration_status(cfg)
    allow_uncal = cfg.get('gate.allow_uncalibrated', False)
    if status != 'ok':
        warnings.append(f'judge calibration is {status}: judge metrics are '
                        + ('gated anyway (allow_uncalibrated)' if allow_uncal else 'report-only'))
    trusted_judge = {c for c, ok in (cal or {}).get('trusted', {}).items() if ok} if status == 'ok' else set()

    bv = item_values(cfg, base_dir, scorers)
    cv = item_values(cfg, cand_dir, scorers)
    common = sorted(set(bv) & set(cv))
    if len(common) < len(bv) or len(common) < len(cv):
        warnings.append(f'{len(common)} items in common (baseline {len(bv)}, candidate {len(cv)})')

    tolerance = cfg.get('gate.tolerance', 0.05)
    floors = cfg.get('gate.floors', {}) or {}
    metrics = sorted({k for i in common for k in (*bv[i], *cv[i])})
    rows = []
    for m in metrics:
        pairs = [(bv[i].get(m), cv[i].get(m)) for i in common]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        is_judge = m.startswith('judge_')
        trusted = m not in NEVER_GATE and (
            not is_judge or allow_uncal or m.removeprefix('judge_') in trusted_judge)
        if not pairs:
            rows.append(MetricRow(m, 0, None, None, None, None, None, None, trusted, 'n/a'))
            continue
        a = [p[0] for p in pairs]
        b = [p[1] for p in pairs]
        sign = -1.0 if m in LOWER_IS_BETTER else 1.0
        # Orient so that positive diff always means "candidate better".
        d, lo, hi = stats.paired_bootstrap_diff([sign * x for x in a], [sign * x for x in b], seed=seed)
        mc = None
        if all(x in (0.0, 1.0) for x in a + b):
            mc = stats.mcnemar_exact([int(x) for x in a], [int(x) for x in b])[2]
        base_mean, cand_mean = sum(a) / len(a), sum(b) / len(b)

        if hi < 0 and d < -tolerance:
            st = 'REGRESSION'
        elif m in floors and (cand_mean > floors[m] if m in LOWER_IS_BETTER else cand_mean < floors[m]):
            st = 'below_floor'
        elif lo > 0:
            st = 'improved'
        else:
            st = 'ok'
        if not trusted and st in ('REGRESSION', 'below_floor'):
            st = f'untrusted ({st.lower()})'
        rows.append(MetricRow(m, len(pairs), base_mean, cand_mean, cand_mean - base_mean,
                              sign * lo if sign > 0 else -hi, sign * hi if sign > 0 else -lo,
                              mc, trusted, st))

    ops = {
        'baseline': ops_stats([r.response for r in load_records(base_dir)], shadow_price),
        'candidate': ops_stats([r.response for r in load_records(cand_dir)], shadow_price),
    }
    return CompareResult(bm['run_id'], cm['run_id'], rows, warnings, ops)


def compare_markdown(res: CompareResult) -> str:
    verdict = 'PASS' if res.passed else 'FAIL'
    lines = [f'# rageval compare: **{verdict}**', '',
             f'- baseline: `{res.baseline}`', f'- candidate: `{res.candidate}`']
    lines += [f'- warning: {w}' for w in res.warnings]
    lines += ['', '| metric | n | baseline | candidate | diff [95% CI] | McNemar p | gated | status |',
              '|---|---|---|---|---|---|---|---|']
    for r in res.rows:
        lines.append(f'| {r.name} | {r.n} | {fmt(r.base)} | {fmt(r.cand)} | '
                     f'{fmt(r.diff)} [{fmt(r.lo)}, {fmt(r.hi)}] | {fmt(r.mcnemar_p)} | '
                     f"{'yes' if r.trusted else 'no'} | {r.status} |")
    lines += ['', '## Cost & latency', '', '| | baseline | candidate |', '|---|---|---|']
    for k, label, nd in [('latency_ms_p50', 'latency p50 (ms)', 0), ('latency_ms_p95', 'latency p95 (ms)', 0),
                         ('prompt_tokens_mean', 'prompt tokens/q', 0),
                         ('completion_tokens_mean', 'completion tokens/q', 0),
                         ('cost_usd_per_q', 'cost $/q', 5), ('shadow_cost_usd_per_q', 'shadow $/q', 5),
                         ('errors', 'errors', 0)]:
        b, c = res.ops['baseline'].get(k), res.ops['candidate'].get(k)
        lines.append(f'| {label} | {fmt(b, nd=nd)} | {fmt(c, nd=nd)} |')
    return '\n'.join(lines) + '\n'


def write_compare_report(res: CompareResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = compare_markdown(res)
    (out_dir / 'compare.md').write_text(md, encoding='utf-8')
    (out_dir / 'compare.html').write_text(markdown_to_html(md, 'rageval compare'), encoding='utf-8')
    return out_dir / 'compare.md'
