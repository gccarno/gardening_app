"""
Run summaries, panel agreement, and markdown/HTML rendering.

Metric naming: deterministic metrics keep their names (``retrieval_recall``,
``fact_coverage``, ...); panel-majority judge verdicts are ``judge_<criterion>``.
"""
from __future__ import annotations

import html
import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np

from rageval import stats
from rageval.calibration import PANEL, calibration_status, corrected_pass_rate
from rageval.judges import load_judgments, panel_verdicts, rubric_hash, verdict_table
from rageval.metrics import item_metrics, ops_stats
from rageval.runner import load_golden, load_manifest, load_records


def item_values(cfg, run_dir: Path, scorers=None) -> dict[str, dict[str, float | None]]:
    """{item_id: {metric: value}} — deterministic metrics + panel verdicts."""
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    table = verdict_table(load_judgments(run_dir), cfg.panel, rubric_hash(cfg.criteria))
    out = {}
    for rec in load_records(run_dir):
        item = golden.get(rec.item_id)
        if item is None:
            continue
        vals = item_metrics(item, rec.response, scorers)
        by_judge = table.get((rec.item_id, rec.answer_hash))
        pv = panel_verdicts(by_judge, cfg.criteria) if by_judge else {c: None for c in cfg.criteria}
        for c, v in pv.items():
            vals[f'judge_{c}'] = None if v is None else float(v)
        out[rec.item_id] = vals
    return out


def describe_values(xs: list[float | None], seed: int = 0) -> dict:
    v = [x for x in xs if x is not None]
    if not v:
        return {'n': 0, 'mean': None, 'lo': None, 'hi': None}
    if all(x in (0.0, 1.0) for x in v):
        p, lo, hi = stats.wilson_ci(int(sum(v)), len(v))
    else:
        p, lo, hi = stats.bootstrap_ci(v, seed=seed)
    return {'n': len(v), 'mean': p, 'lo': lo, 'hi': hi}


def agreement(cfg, run_dir: Path, seed: int = 0) -> dict:
    """Panel inter-rater agreement per criterion: Fleiss' kappa (items every
    judge rated), Krippendorff's alpha (tolerates gaps), pairwise Cohen's kappa."""
    table = verdict_table(load_judgments(run_dir), cfg.panel, rubric_hash(cfg.criteria))
    panel = cfg.panel
    out = {}
    for c in cfg.criteria:
        rows = [[(by.get(j) or {}).get(c) for j in panel] for by in table.values()]
        rows = [r for r in rows if sum(v is not None for v in r) >= 2]
        full = [r for r in rows if all(v is not None for v in r)]
        res: dict = {'n_items': len(rows), 'n_complete': len(full)}
        if len(panel) >= 2 and full:
            res['fleiss'] = stats.bootstrap_agreement_ci(
                full, lambda rs: stats.fleiss_kappa(stats.ratings_to_table(rs, [False, True])), seed=seed)
        if rows:
            res['krippendorff'] = stats.bootstrap_agreement_ci(
                rows, lambda rs: stats.krippendorff_alpha(rs, 'nominal'), seed=seed)
        pairs = {}
        for a, b in combinations(range(len(panel)), 2):
            ra = [r[a] for r in rows]
            rb = [r[b] for r in rows]
            pairs[f'{panel[a]} vs {panel[b]}'] = {
                'kappa': stats.cohen_kappa(ra, rb, labels=[False, True]),
                'agreement': stats.percent_agreement(ra, rb),
            }
        res['pairwise'] = pairs
        out[c] = res
    return out


def summarize_run(cfg, run_dir: Path, scorers=None, shadow_price=None, seed: int = 0) -> dict:
    vals = item_values(cfg, run_dir, scorers)
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    metrics = sorted({k for v in vals.values() for k in v})
    summary_metrics = {m: describe_values([v.get(m) for v in vals.values()], seed) for m in metrics}

    cal, cal_status = calibration_status(cfg)
    calibrated = {}
    if cal and cal_status == 'ok':
        for c in cfg.criteria:
            pairs = [tuple(p) for p in cal['results'][c][PANEL]['pairs']]
            obs = [bool(v[f'judge_{c}']) for v in vals.values() if v.get(f'judge_{c}') is not None]
            p, lo, hi = corrected_pass_rate(obs, pairs, seed=seed)
            calibrated[c] = {'corrected': p, 'lo': lo, 'hi': hi,
                             'trusted': cal['trusted'].get(c, False),
                             'kappa': cal['results'][c][PANEL]['kappa']}

    by_cat: dict[str, dict[str, float | None]] = {}
    for cat in sorted({golden[i].category for i in vals}):
        ids = [i for i in vals if golden[i].category == cat]
        by_cat[cat] = {m: describe_values([vals[i].get(m) for i in ids])['mean'] for m in metrics}
        by_cat[cat]['n'] = len(ids)

    per_judge = {}
    for j in load_judgments(run_dir):
        if j.judge in cfg.panel and not j.error:
            d = per_judge.setdefault(j.judge, {'n': 0, 'served_models': set()})
            d['n'] += 1
            if j.served_model:
                d['served_models'].add(j.served_model)
    for d in per_judge.values():
        d['served_models'] = sorted(d['served_models'])

    records = load_records(run_dir)
    summary = {
        'manifest': load_manifest(run_dir),
        'metrics': summary_metrics,
        'calibration_status': cal_status,
        'calibrated': calibrated,
        'agreement': agreement(cfg, run_dir, seed),
        'by_category': by_cat,
        'judges': per_judge,
        'ops': ops_stats([r.response for r in records], shadow_price),
    }
    (run_dir / 'summary.json').write_text(json.dumps(summary, indent=2, default=_json_default),
                                          encoding='utf-8')
    return summary


def _json_default(o):
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, set):
        return sorted(o)
    return str(o)


# ── Rendering ────────────────────────────────────────────────────────────────

def fmt(x, pct: bool = False, nd: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return 'n/a'
    return f'{x * 100:.1f}%' if pct else f'{x:.{nd}f}'


def _ci(d: dict, pct=True) -> str:
    return f"{fmt(d.get('mean'), pct)} [{fmt(d.get('lo'), pct)}, {fmt(d.get('hi'), pct)}]"


def run_markdown(s: dict) -> str:
    m = s['manifest']
    lines = [f"# rageval run `{m['run_id']}`", '',
             f"- app: **{m['app']}**, adapter: `{m['adapter']}`, git: `{m.get('git_sha')}`",
             f"- system under test: `{json.dumps(m['describe'], default=str)}`",
             f"- golden: `{m['golden_hash']}` ({m.get('n_records', '?')} records)",
             f"- calibration: **{s['calibration_status']}**", '',
             '## Quality (95% CI)', '', '| metric | n | value |', '|---|---|---|']
    for name, d in s['metrics'].items():
        if d['n']:                      # metrics that applied to no item are noise
            lines.append(f"| {name} | {d['n']} | {_ci(d)} |")
    if s['calibrated']:
        lines += ['', '## Calibrated judge pass rates (Rogan-Gladen)', '',
                  '| criterion | trusted | kappa vs human | corrected [95% CI] |', '|---|---|---|---|']
        for c, d in s['calibrated'].items():
            lines.append(f"| {c} | {'yes' if d['trusted'] else 'NO'} | {fmt(d['kappa'])} | "
                         f"{fmt(d['corrected'], True)} [{fmt(d['lo'], True)}, {fmt(d['hi'], True)}] |")
    judged = {c: a for c, a in s['agreement'].items() if a['n_items']}
    if judged:
        lines += ['', '## Judge panel agreement', '',
                  "| criterion | items | Fleiss' kappa [CI] | Krippendorff alpha [CI] |", '|---|---|---|---|']
    for c, a in judged.items():
        f = a.get('fleiss') or (None, None, None)
        k = a.get('krippendorff') or (None, None, None)
        lines.append(f"| {c} | {a['n_items']} | {fmt(f[0])} [{fmt(f[1])}, {fmt(f[2])}] | "
                     f"{fmt(k[0])} [{fmt(k[1])}, {fmt(k[2])}] |")
    o = s['ops']
    lines += ['', '## Cost & latency', '',
              f"- errors: {o['errors']}/{o['n']}",
              f"- latency p50 / p95 / p99: {fmt(o['latency_ms_p50'], nd=0)} / "
              f"{fmt(o['latency_ms_p95'], nd=0)} / {fmt(o['latency_ms_p99'], nd=0)} ms",
              f"- tokens/question (prompt / completion): {fmt(o['prompt_tokens_mean'], nd=0)} / "
              f"{fmt(o['completion_tokens_mean'], nd=0)}",
              f"- cost: ${fmt(o['cost_usd_total'], nd=4)} total"
              + (f", shadow ${fmt(o.get('shadow_cost_usd_total'), nd=4)}" if 'shadow_cost_usd_total' in o else '')]
    if o.get('stage_latency_ms_p50'):
        lines.append('- stage p50: ' + ', '.join(f'{k} {fmt(v, nd=0)} ms'
                                                 for k, v in o['stage_latency_ms_p50'].items()))
    if s['by_category']:
        keys = [k for k in ('judge_correct', 'judge_faithful', 'retrieval_recall', 'fact_coverage')
                if k in s['metrics']]
        lines += ['', '## By category', '', '| category | n | ' + ' | '.join(keys) + ' |',
                  '|---' * (len(keys) + 2) + '|']
        for cat, d in s['by_category'].items():
            lines.append(f"| {cat} | {d['n']} | " + ' | '.join(fmt(d.get(k), True) for k in keys) + ' |')
    return '\n'.join(lines) + '\n'


def markdown_to_html(md: str, title: str) -> str:
    """Minimal md -> HTML for our own reports (headings, bullets, tables)."""
    out, in_table, in_list = [], False, False
    for line in md.splitlines():
        if line.startswith('|'):
            cells = [html.escape(c.strip()) for c in line.strip('|').split('|')]
            if set(''.join(cells)) <= set('-'):
                continue
            if not in_table:
                out.append('<table><tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>')
                in_table = True
            else:
                out.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
            continue
        if in_table:
            out.append('</table>')
            in_table = False
        if line.startswith('- '):
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{html.escape(line[2:])}</li>')
            continue
        if in_list:
            out.append('</ul>')
            in_list = False
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            out.append(f'<h{level}>{html.escape(line.lstrip("# "))}</h{level}>')
        elif line.strip():
            out.append(f'<p>{html.escape(line)}</p>')
    if in_table:
        out.append('</table>')
    if in_list:
        out.append('</ul>')
    body = '\n'.join(out).replace('**', '')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#e5e5ea;--bad:#c62828;--good:#2e7d32}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#f2f2f7;--mute:#a1a1a6;--line:#2c2c2e}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%;margin:8px 0 20px;font-variant-numeric:tabular-nums}}
th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}}
th{{color:var(--mute);font-weight:600}}
</style></head><body>{body}</body></html>"""
