"""End-to-end on the toy RAG with a fake judge — no network."""
import json
from dataclasses import asdict

import pytest
from rageval.calibration import calibrate, calibration_status
from rageval.compare import compare
from rageval.config import build_adapter
from rageval.judges import judge_run, load_judgments
from rageval.label import label_run
from rageval.report import agreement, run_markdown, summarize_run
from rageval.runner import load_records, resolve_run, run, snapshot
from rageval.schema import HumanLabel, append_jsonl

quiet = lambda *_: None


def _run(cfg, client, adapter='toy', run_id=None):
    d = run(cfg, build_adapter(cfg, adapter), run_id=run_id, log=quiet)
    judge_run(cfg, d, client, log=quiet)
    return d


def test_run_judge_summarize(toy_cfg, fake_client):
    d = _run(toy_cfg, fake_client)
    recs = load_records(d)
    assert len(recs) == 10
    assert len(load_judgments(d)) == 30           # 10 records x 3 judges
    s = summarize_run(toy_cfg, d)
    m = s['metrics']
    assert m['retrieval_hit']['mean'] == 1.0
    assert m['judge_correct']['mean'] >= 0.75
    # The toy refuses neg-wheel but answers neg-saddle from the tyre passage
    # ("rider" overlaps) - a realistic hallucination both scorers must catch.
    assert m['refusal_correct']['mean'] == 0.9
    assert m['judge_appropriate_refusal']['n'] == 2
    assert m['judge_appropriate_refusal']['mean'] == 0.5
    assert s['ops']['prompt_tokens_mean'] > 0
    assert 'Quality' in run_markdown(s)
    assert (d / 'summary.json').exists()


def test_resume_skips_done_items_and_judging_is_cached(toy_cfg, fake_client):
    adapter = build_adapter(toy_cfg, 'toy')
    calls = []
    orig = adapter.answer
    adapter.answer = lambda item: calls.append(item.id) or orig(item)
    d = run(toy_cfg, adapter, run_id='r1', limit=4, log=quiet)
    assert len(calls) == 4
    run(toy_cfg, adapter, run_id='r1', log=quiet)
    assert len(calls) == 10 and len(load_records(d)) == 10

    judge_run(toy_cfg, d, fake_client, log=quiet)
    n = fake_client.calls
    judge_run(toy_cfg, d, fake_client, log=quiet)
    assert fake_client.calls == n                  # all cached


def test_resume_refuses_changed_system(toy_cfg):
    run(toy_cfg, build_adapter(toy_cfg, 'toy'), run_id='r1', limit=2, log=quiet)
    with pytest.raises(RuntimeError):
        run(toy_cfg, build_adapter(toy_cfg, 'toy_degraded'), run_id='r1', log=quiet)


def test_adapter_crash_is_recorded_not_fatal(toy_cfg):
    adapter = build_adapter(toy_cfg, 'toy')

    def boom(item):
        raise ValueError('kaput')

    adapter.answer = boom
    d = run(toy_cfg, adapter, log=quiet)
    recs = load_records(d)
    assert len(recs) == 10 and all('kaput' in r.response.error for r in recs)


def test_agreement_reports_all_statistics(toy_cfg, fake_client):
    d = _run(toy_cfg, fake_client)
    a = agreement(toy_cfg, d)
    assert set(a) == set(toy_cfg.criteria)
    assert a['correct']['n_complete'] == 8          # the 2 negatives have no reference
    assert len(a['correct']['pairwise']) == 3
    assert 'krippendorff' in a['correct']


def test_compare_identical_passes_degraded_fails(toy_cfg, fake_client):
    good = _run(toy_cfg, fake_client, run_id='good')
    again = _run(toy_cfg, fake_client, run_id='again')
    bad = _run(toy_cfg, fake_client, adapter='toy_degraded', run_id='bad')

    same = compare(toy_cfg, good, again)
    assert same.passed

    res = compare(toy_cfg, good, bad)
    assert not res.passed
    rows = {r.name: r for r in res.rows}
    assert rows['fact_coverage'].status == 'REGRESSION'      # deterministic: always gated
    assert rows['judge_correct'].diff < 0
    assert not rows['judge_correct'].trusted                 # no calibration yet
    assert any('calibration is missing' in w for w in res.warnings)


def _label_like_truth(cfg, run_dir, client):
    """Human labels = the non-noisy judge's view, i.e. a 'perfect' human."""
    from rageval.judges import judge_one
    from rageval.runner import load_golden
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    for rec in load_records(run_dir):
        j = judge_one(client, 'judge-a:free', golden[rec.item_id], rec, cfg.criteria)
        append_jsonl(cfg.labels_path, HumanLabel(rec.item_id, rec.answer_hash, j.verdicts,
                                                 labeler='test', record=asdict(rec)))


def test_calibration_trusts_agreeing_criteria_and_gates_them(toy_cfg, fake_client):
    good = _run(toy_cfg, fake_client, run_id='good')
    bad = _run(toy_cfg, fake_client, adapter='toy_degraded', run_id='bad')
    _label_like_truth(toy_cfg, good, fake_client)
    _label_like_truth(toy_cfg, bad, fake_client)

    cal = calibrate(toy_cfg, fake_client, log=quiet)
    # neg-wheel's refusal is word-for-word the same in both runs: one answer, one label
    assert cal['n_labels'] == 19
    assert cal['results']['correct']['judge-a:free']['kappa'] == pytest.approx(1.0)
    assert cal['trusted']['correct']
    assert calibration_status(toy_cfg)[1] == 'ok'

    rows = {r.name: r for r in compare(toy_cfg, good, bad).rows}
    assert rows['judge_correct'].trusted

    s = summarize_run(toy_cfg, good)
    assert s['calibrated']['correct']['trusted']


def test_panel_change_makes_calibration_stale(toy_cfg, fake_client):
    good = _run(toy_cfg, fake_client, run_id='good')
    _label_like_truth(toy_cfg, good, fake_client)
    calibrate(toy_cfg, fake_client, log=quiet)
    toy_cfg.raw['judges']['panel'] = ['judge-a:free', 'judge-z:free']
    assert calibration_status(toy_cfg)[1] == 'stale'


def test_label_cli_is_blind_resumable_and_skips_inapplicable(toy_cfg, fake_client):
    d = _run(toy_cfg, fake_client)
    shown = []
    answers = iter(['y'] * 4 + [''] + ['q'])          # one full item, then quit
    n = label_run(toy_cfg, d, n=5, ask=lambda _: next(answers), out=shown.append)
    assert n == 1
    assert not any('verdict' in s.lower() for s in shown)
    lab = json.loads(toy_cfg.labels_path.read_text().splitlines()[0])
    assert lab['record']['response']['answer']
    # resuming continues the same seeded sample, minus what's labelled
    shown2 = []
    label_run(toy_cfg, d, n=5, ask=lambda _: 'q', out=shown2.append)
    assert shown2[0].startswith('4 answers')


def test_baseline_snapshot_resolves(toy_cfg, fake_client):
    d = _run(toy_cfg, fake_client)
    snapshot(d, toy_cfg.baselines_dir / 'v1')
    b = resolve_run(toy_cfg, 'baseline:v1')
    assert len(load_records(b)) == 10
    assert compare(toy_cfg, b, d).passed


def test_cli_run_and_compare_exit_code(toy_cfg, fake_client, monkeypatch):
    from rageval import cli
    monkeypatch.setattr(cli, 'make_client', lambda cfg: fake_client)
    cfgp = str(toy_cfg.root / 'rageval.yaml')
    cli.main(['-c', cfgp, 'run', '--run-id', 'good'])
    cli.main(['-c', cfgp, 'run', '--adapter', 'toy_degraded', '--run-id', 'bad'])
    with pytest.raises(SystemExit) as e:
        cli.main(['-c', cfgp, 'compare', 'good', 'bad'])
    assert e.value.code == 1
    assert (toy_cfg.runs_dir / 'bad' / 'compare.html').exists()
    with pytest.raises(SystemExit) as e:
        cli.main(['-c', cfgp, 'compare', 'good', 'good'])
    assert e.value.code == 0
