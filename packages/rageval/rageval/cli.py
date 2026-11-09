"""
rageval command line.

    rageval -c evals/garden/rageval.yaml run [--adapter X] [--limit N] [--run-id ID]
    rageval -c ... judge RUN          judge any records the current panel hasn't
    rageval -c ... report RUN         summary.json + report.md/html
    rageval -c ... agreement RUN      panel inter-rater agreement
    rageval -c ... label RUN          blind human labelling for calibration
    rageval -c ... calibrate          judges vs your labels -> calibration.json
    rageval -c ... compare BASE CAND  regression gate (exit 1 on regression)
    rageval -c ... pairwise BASE CAND A/B preference with order swap
    rageval -c ... baseline RUN NAME  snapshot a run as a committed baseline
    rageval -c ... synth / review     build the golden set
    rageval or models|key|ping        OpenRouter helpers

RUN is a run id, a run directory, or ``baseline:<name>``. The config defaults
to $RAGEVAL_CONFIG, then ./rageval.yaml.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from rageval.config import Config, build_adapter, load_scorers, make_client


def _cfg(args) -> Config:
    path = args.config or os.environ.get('RAGEVAL_CONFIG') or 'rageval.yaml'
    if not Path(path).exists():
        sys.exit(f'config not found: {path} (pass -c PATH or set RAGEVAL_CONFIG)')
    return Config.load(path)


def _shadow_price(cfg, client):
    model = cfg.get('cost.shadow_model')
    if not model:
        return None
    from rageval.llm.openrouter import OpenRouterError, price_of
    try:
        return price_of(client.models(cfg.cache_dir / 'models.json'), model)
    except OpenRouterError as exc:
        print(f'(shadow cost unavailable: {exc})')
        return None


def _report(cfg, run_dir, client):
    from rageval.report import markdown_to_html, run_markdown, summarize_run
    s = summarize_run(cfg, run_dir, load_scorers(cfg), _shadow_price(cfg, client))
    md = run_markdown(s)
    (run_dir / 'report.md').write_text(md, encoding='utf-8')
    (run_dir / 'report.html').write_text(markdown_to_html(md, f"rageval {run_dir.name}"), encoding='utf-8')
    return s, md


def cmd_run(args):
    from rageval.judges import judge_run
    from rageval.runner import run
    cfg = _cfg(args)
    adapter = build_adapter(cfg, args.adapter)
    run_dir = run(cfg, adapter, run_id=args.run_id, limit=args.limit,
                  item_ids=args.items.split(',') if args.items else None,
                  retry_errors=args.retry_errors)
    client = make_client(cfg)
    # Retrieval-only adapters set judgeable = False: there is no answer to judge.
    if not args.no_judge and cfg.panel and getattr(adapter, 'judgeable', True):
        _, complete = judge_run(cfg, run_dir, client)
        if not complete:
            print(f'judging incomplete; finish later with: rageval judge {run_dir.name}')
    s, md = _report(cfg, run_dir, client)
    print(md)
    if args.mlflow or cfg.get('mlflow.experiment'):
        from rageval.mlflow_log import log_summary
        log_summary(s, run_dir, cfg.get('mlflow.experiment', f'rageval-{cfg.name}'),
                    cfg.get('mlflow.tracking_uri'))
    print(f'run dir: {run_dir}')


def cmd_judge(args):
    from rageval.judges import judge_run
    from rageval.runner import resolve_run
    cfg = _cfg(args)
    run_dir = resolve_run(cfg, args.run)
    client = make_client(cfg)
    js, complete = judge_run(cfg, run_dir, client)
    print(f'{len(js)} judgments ({"complete" if complete else "INCOMPLETE - budget"})')
    _report(cfg, run_dir, client)


def cmd_report(args):
    from rageval.runner import resolve_run
    cfg = _cfg(args)
    run_dir = resolve_run(cfg, args.run)
    _, md = _report(cfg, run_dir, make_client(cfg))
    print(md)


def cmd_agreement(args):
    from rageval.report import agreement, fmt
    from rageval.runner import resolve_run
    cfg = _cfg(args)
    res = agreement(cfg, resolve_run(cfg, args.run))
    for c, a in res.items():
        f = a.get('fleiss') or (None,) * 3
        k = a.get('krippendorff') or (None,) * 3
        print(f"{c}: items={a['n_items']} fleiss={fmt(f[0])} [{fmt(f[1])}, {fmt(f[2])}] "
              f"alpha={fmt(k[0])} [{fmt(k[1])}, {fmt(k[2])}]")
        for pair, d in a['pairwise'].items():
            print(f"    {pair}: kappa={fmt(d['kappa'])} agree={fmt(d['agreement'], True)}")


def cmd_label(args):
    from rageval.label import label_run
    from rageval.runner import resolve_run
    cfg = _cfg(args)
    label_run(cfg, resolve_run(cfg, args.run), n=args.n, seed=args.seed, labeler=args.labeler)


def cmd_calibrate(args):
    from rageval.calibration import PANEL, calibrate
    from rageval.report import fmt
    cfg = _cfg(args)
    res = calibrate(cfg, make_client(cfg))
    print(f"{res['n_labels']} labels; panel hash {res['panel_hash']}")
    for c, by_judge in res['results'].items():
        print(f'\n{c}:')
        for judge, r in by_judge.items():
            tag = 'TRUSTED' if r['trusted'] else 'untrusted'
            print(f"  {'*' if judge == PANEL else ' '} {judge:45s} n={r['n']:3d} "
                  f"kappa={fmt(r['kappa'])} [{fmt(r['kappa_lo'])}, {fmt(r['kappa_hi'])}] "
                  f"TPR={fmt(r['sensitivity'])} TNR={fmt(r['specificity'])} "
                  f"bias={fmt(r['bias'])} {tag}")
    print(f'\nwritten: {cfg.calibration_path}')


def cmd_compare(args):
    from rageval.compare import compare, compare_markdown, write_compare_report
    from rageval.judges import judge_run
    from rageval.runner import resolve_run
    cfg = _cfg(args)
    client = make_client(cfg)
    base, cand = resolve_run(cfg, args.baseline), resolve_run(cfg, args.candidate)
    if not args.no_judge and cfg.panel:
        for d in (base, cand):      # brings both up to the current panel; cached = free
            judge_run(cfg, d, client, log=lambda m: None)
    res = compare(cfg, base, cand, load_scorers(cfg), _shadow_price(cfg, client))
    print(compare_markdown(res))
    out = write_compare_report(res, Path(args.out) if args.out else cand)
    print(f'report: {out}')
    sys.exit(0 if res.passed else 1)


def cmd_pairwise(args):
    from rageval.judges import pairwise
    from rageval.runner import load_golden, load_records, resolve_run
    cfg = _cfg(args)
    client = make_client(cfg)
    judge = args.judge or (cfg.panel[0] if cfg.panel else None)
    if not judge:
        sys.exit('no judge: pass --judge or configure judges.panel')
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    a = {r.item_id: r for r in load_records(resolve_run(cfg, args.baseline))}
    b = {r.item_id: r for r in load_records(resolve_run(cfg, args.candidate))}
    ids = sorted(set(a) & set(b) & set(golden))[: args.limit or None]
    tally = {'a': 0, 'b': 0, 'tie': 0}
    inconsistent = 0
    for i in ids:
        if a[i].answer_hash == b[i].answer_hash:
            tally['tie'] += 1
            continue
        r = pairwise(client, judge, golden[i].question, golden[i].reference_answer,
                     a[i].response.answer, b[i].response.answer)
        tally[r['winner']] += 1
        inconsistent += not r['consistent']
    n = len(ids)
    print(f'{n} items: baseline wins {tally["a"]}, candidate wins {tally["b"]}, ties {tally["tie"]} '
          f'(position-bias flips: {inconsistent})')


def cmd_baseline(args):
    from rageval.runner import resolve_run, snapshot
    cfg = _cfg(args)
    dest = snapshot(resolve_run(cfg, args.run), cfg.baselines_dir / args.name)
    print(f'baseline written: {dest}  (commit it)')


def cmd_synth(args):
    from rageval.dataset import synth
    cfg = _cfg(args)
    adapter = build_adapter(cfg, args.adapter or cfg.get('synth.adapter'))
    model = args.model or cfg.get('synth.model')
    if not model:
        sys.exit('no generator model: pass --model or set synth.model')
    out = cfg.path(cfg.get('synth.candidates', 'candidates.jsonl'))
    n = synth(adapter.iter_chunks(), make_client(cfg), model, args.n or cfg.get('synth.n', 70), out,
              seed=args.seed, audience=cfg.get('synth.audience', ''))
    print(f'{n} candidates written to {out}; review with: rageval review')


def cmd_review(args):
    from rageval.dataset import review
    cfg = _cfg(args)
    a, r = review(cfg.path(cfg.get('synth.candidates', 'candidates.jsonl')), cfg.golden_path)
    print(f'accepted {a}, rejected {r}')


# ── OpenRouter helpers ───────────────────────────────────────────────────────

def _or_client(args):
    from rageval.llm.openrouter import OpenRouterClient
    if args.config or os.environ.get('RAGEVAL_CONFIG') or Path('rageval.yaml').exists():
        cfg = _cfg(args)
        return make_client(cfg), cfg.cache_dir
    return OpenRouterClient(rpm=0), Path('.rageval_cache')


def cmd_or_models(args):
    client, cache = _or_client(args)
    rows = []
    for m in client.models(cache / 'models.json'):
        mid = m.get('id', '')
        p = m.get('pricing') or {}
        free = mid.endswith(':free')
        tools = 'tools' in (m.get('supported_parameters') or [])
        ctx = m.get('context_length') or 0
        if (args.free and not free) or (args.tools and not tools) or ctx < args.min_context:
            continue
        if args.grep and args.grep.lower() not in mid.lower():
            continue
        rows.append((mid, ctx, float(p.get('prompt') or 0) * 1e6, float(p.get('completion') or 0) * 1e6, tools))
    rows.sort()
    print(f"{'model':60s} {'context':>9s} {'$/M in':>8s} {'$/M out':>8s} tools")
    for mid, ctx, pin, pout, tools in rows:
        print(f'{mid:60s} {ctx:9d} {pin:8.3f} {pout:8.3f} {"yes" if tools else ""}')
    print(f'{len(rows)} models')


def cmd_or_key(args):
    client, _ = _or_client(args)
    info = client.key_info()
    if args.json:
        print(json.dumps(info, indent=2))
        return
    print(f"free tier account : {info.get('is_free_tier')}")
    print(f"credit limit      : {info.get('limit')}  (remaining {info.get('limit_remaining')})")
    print(f"usage USD         : total {info.get('usage')}, today {info.get('usage_daily')}")
    free = info.get('free_model_daily_requests')
    if free:
        print(f"free-model requests today: {free.get('used')} / {free.get('limit')} "
              f"({free.get('remaining')} left)")
    print('free models are also limited to ~20 requests/minute')
    print(f'rageval local counter today: {client.budget.used_today()} used, '
          f'{client.budget.remaining()} remaining of configured daily_limit')


def cmd_or_ping(args):
    client, _ = _or_client(args)
    t0 = time.perf_counter()
    c = client.complete('Reply in one short sentence.', args.prompt, args.model)
    print(f'model={c.model} provider={c.provider} latency={c.latency_ms:.0f}ms '
          f'tokens={c.prompt_tokens}+{c.completion_tokens} cost=${c.cost_usd} '
          f'(wall {1000 * (time.perf_counter() - t0):.0f}ms)')
    print(c.text)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog='rageval', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-c', '--config')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('run')
    p.add_argument('--adapter')
    p.add_argument('--limit', type=int)
    p.add_argument('--items', help='comma-separated golden ids')
    p.add_argument('--run-id', help='resume this run')
    p.add_argument('--retry-errors', action='store_true')
    p.add_argument('--no-judge', action='store_true')
    p.add_argument('--mlflow', action='store_true')
    p.set_defaults(fn=cmd_run)

    for name, fn in [('judge', cmd_judge), ('report', cmd_report), ('agreement', cmd_agreement)]:
        p = sub.add_parser(name)
        p.add_argument('run')
        p.set_defaults(fn=fn)

    p = sub.add_parser('label')
    p.add_argument('run')
    p.add_argument('--n', type=int, default=50)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--labeler', default=os.environ.get('RAGEVAL_LABELER', ''))
    p.set_defaults(fn=cmd_label)

    sub.add_parser('calibrate').set_defaults(fn=cmd_calibrate)

    p = sub.add_parser('compare')
    p.add_argument('baseline')
    p.add_argument('candidate')
    p.add_argument('--out')
    p.add_argument('--no-judge', action='store_true', help="don't judge missing records first")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser('pairwise')
    p.add_argument('baseline')
    p.add_argument('candidate')
    p.add_argument('--judge')
    p.add_argument('--limit', type=int)
    p.set_defaults(fn=cmd_pairwise)

    p = sub.add_parser('baseline')
    p.add_argument('run')
    p.add_argument('name')
    p.set_defaults(fn=cmd_baseline)

    p = sub.add_parser('synth')
    p.add_argument('--adapter')
    p.add_argument('--model')
    p.add_argument('--n', type=int)
    p.add_argument('--seed', type=int, default=0)
    p.set_defaults(fn=cmd_synth)

    sub.add_parser('review').set_defaults(fn=cmd_review)

    orp = sub.add_parser('or', help='OpenRouter helpers').add_subparsers(dest='or_cmd', required=True)
    p = orp.add_parser('models')
    p.add_argument('--free', action='store_true')
    p.add_argument('--tools', action='store_true')
    p.add_argument('--min-context', type=int, default=0)
    p.add_argument('--grep')
    p.set_defaults(fn=cmd_or_models)
    p = orp.add_parser('key')
    p.add_argument('--json', action='store_true', help='print the raw /key response')
    p.set_defaults(fn=cmd_or_key)
    p = orp.add_parser('ping')
    p.add_argument('model')
    p.add_argument('--prompt', default='Say hello.')
    p.set_defaults(fn=cmd_or_ping)
    return ap


def main(argv: list[str] | None = None):
    # Windows consoles default to cp1252; model output is full of characters it can't encode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='replace')
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == '__main__':
    main()
