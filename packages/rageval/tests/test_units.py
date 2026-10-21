import math

import numpy as np
import pytest
from rageval.calibration import (
    confusion,
    corrected_pass_rate,
    judge_vs_human,
    rogan_gladen,
)
from rageval.dataset import review, stratified_sample, synth
from rageval.judges import majority, pairwise
from rageval.llm.openrouter import Completion
from rageval.metrics import fact_covered, item_metrics, ops_stats, retrieval_metrics
from rageval.schema import Context, GoldenItem, Response, read_jsonl

# ── calibration ──────────────────────────────────────────────────────────────

def test_rogan_gladen_recovers_true_rate_from_biased_judge():
    rng = np.random.default_rng(0)
    sens, spec, p_true = 0.9, 0.7, 0.6

    def judge(truth):
        return np.where(truth, rng.random(len(truth)) < sens, rng.random(len(truth)) >= spec)

    cal_truth = rng.random(400) < 0.5
    cal_pairs = list(zip(cal_truth.tolist(), judge(cal_truth).tolist()))
    run_truth = rng.random(2000) < p_true
    observed = judge(run_truth).tolist()

    assert np.mean(observed) > p_true + 0.05          # the raw judge over-counts passes
    p, lo, hi = corrected_pass_rate(observed, cal_pairs, iters=500, seed=1)
    assert lo < p_true < hi
    assert abs(p - p_true) < 0.05


def test_rogan_gladen_useless_judge_is_nan():
    assert math.isnan(rogan_gladen(0.5, 0.5, 0.5))


def test_confusion_and_trust():
    pairs = [(True, True)] * 15 + [(False, False)] * 10 + [(True, False)] * 2
    c = confusion(pairs)
    assert (c['tp'], c['tn'], c['fn'], c['fp']) == (15, 10, 2, 0)
    assert c['sensitivity'] == pytest.approx(15 / 17)
    assert c['bias'] == pytest.approx(-2 / 27)
    r = judge_vs_human(pairs, trust_kappa=0.6, min_n=20)
    assert r['trusted'] and r['kappa_lo'] <= r['kappa'] <= r['kappa_hi']
    assert not judge_vs_human(pairs[:10], min_n=20)['trusted']       # too few labels


def test_majority():
    assert majority([True, True, False]) is True
    assert majority([True, False, None]) is None
    assert majority([None, None]) is None


# ── metrics ──────────────────────────────────────────────────────────────────

def _item(**kw):
    return GoldenItem(id='x', question='q', **kw)


def test_retrieval_metrics():
    item = _item(relevant_sources=['b', 'z'])
    resp = Response('a', contexts=[Context('t', id='a'), Context('t', id='b')])
    m = retrieval_metrics(item, resp)
    assert m == {'retrieval_hit': 1.0, 'retrieval_recall': 0.5, 'retrieval_mrr': 0.5}
    assert retrieval_metrics(_item(), resp)['retrieval_recall'] is None


def test_fact_covered_and_refusal_scoring():
    assert fact_covered('lubricate every 150 to 300 km', 'Lubricate it every 150 to 300 km or so.')
    assert not fact_covered('isopropyl alcohol', 'Use soapy water.')
    neg = item_metrics(_item(answerable=False), Response("I don't know, sorry."))
    assert neg['refused'] == 1.0 and neg['refusal_correct'] == 1.0
    pos = item_metrics(_item(), Response("I couldn't find that."))
    assert pos['refusal_correct'] == 0.0


@pytest.mark.parametrize('answer', [
    # Real abstentions from a garden run; note the typographic apostrophe.
    'I don’t have any recorded harvest‑weight data for your garden.',
    'The garden record only lists a tomato plant; it doesn’t store an actual soil‑pH reading.',
    'There’s no record of seed purchases or costs in the garden plan.',
    "I don't have a tool that reports real-time soil temperature.",
])
def test_refusal_catches_abstention_phrasings(answer):
    m = item_metrics(_item(answerable=False), Response(answer))
    assert m['refused'] == 1.0 and m['refusal_correct'] == 1.0


def test_refusal_ignores_plain_answers():
    m = item_metrics(_item(), Response('Your raised bed is 4 ft × 8 ft and holds one tomato.'))
    assert m['refused'] == 0.0 and m['refusal_correct'] == 1.0


def test_errors_leave_quality_undefined():
    m = item_metrics(_item(must_include=['x']), Response('', error='boom'))
    assert m['error'] == 1.0 and m['fact_coverage'] is None


def test_custom_scorer_plugs_in():
    m = item_metrics(_item(), Response('hi'), [lambda item, r: {'said_hi': r.answer == 'hi'}])
    assert m['said_hi'] == 1.0


def test_ops_stats_shadow_cost():
    rs = [Response('a', prompt_tokens=1000, completion_tokens=100, latency_ms=100.0, cost_usd=0.0)] * 4
    o = ops_stats(rs, shadow_price=(3e-6, 15e-6))
    assert o['latency_ms_p50'] == 100.0
    assert o['shadow_cost_usd_per_q'] == pytest.approx(0.0045)
    assert o['cost_usd_total'] == 0.0


# ── dataset ──────────────────────────────────────────────────────────────────

def test_stratified_sample_round_robins_sources():
    chunks = [{'id': f'a{i}', 'text': 'x' * 300, 'source': 'big'} for i in range(20)]
    chunks += [{'id': 'b0', 'text': 'y' * 300, 'source': 'small'}, {'id': 'short', 'text': 'tiny', 'source': 'small'}]
    got = stratified_sample(chunks, 4, seed=0)
    assert len(got) == 4 and 'b0' in {c['id'] for c in got}
    assert 'short' not in {c['id'] for c in got}


class SynthClient:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, model, **kw):
        self.calls += 1
        usable = 'TABLE OF CONTENTS' not in user
        return ({'usable': usable, 'question': f'Q{self.calls}?', 'reference_answer': 'R',
                 'must_include': ['f1', 'f2'], 'category': 'Soil'},
                Completion(text='{}', model=model))


def test_synth_then_review(tmp_path):
    chunks = [{'id': 'c1', 'text': 'Compost ' * 40, 'source': 's1'},
              {'id': 'c2', 'text': 'TABLE OF CONTENTS ' * 20, 'source': 's2'},
              {'id': 'c3', 'text': 'Mulch ' * 50, 'source': 's3'}]
    cand, gold = tmp_path / 'cand.jsonl', tmp_path / 'golden.jsonl'
    client = SynthClient()
    assert synth(chunks, client, 'gen:free', 10, cand, log=lambda *_: None) == 2
    assert synth(chunks, client, 'gen:free', 10, cand, log=lambda *_: None) == 0
    assert client.calls == 3                       # resume re-asks nothing, not even the unusable chunk
    rows = [r for r in read_jsonl(cand) if r['status'] == 'pending']
    assert all(r['item']['relevant_sources'] == [r['source_chunk']] for r in rows)
    assert rows[0]['item']['category'] == 'soil'

    answers = iter(['e', 'Edited question?', '', '', 'only fact', 'r'])
    acc, rej = review(cand, gold, ask=lambda _: next(answers), out=lambda *_: None)
    assert (acc, rej) == (1, 1)
    g = read_jsonl(gold, GoldenItem)
    assert g[0].question == 'Edited question?' and g[0].must_include == ['only fact']
    assert {r['status'] for r in read_jsonl(cand)} == {'accepted', 'rejected', 'unusable'}


# ── pairwise ─────────────────────────────────────────────────────────────────

class PairClient:
    """Always prefers whichever answer is shown first: pure position bias."""

    def complete_json(self, system, user, model, **kw):
        return {'winner': '1'}, Completion(text='{}', model=model)


class FairClient:
    def complete_json(self, system, user, model, **kw):
        first = user.split('ANSWER 1:\n')[1].split('\n\nANSWER 2:')[0]
        return {'winner': '1' if 'good' in first else '2'}, Completion(text='{}', model=model)


def test_pairwise_position_bias_becomes_tie():
    r = pairwise(PairClient(), 'j', 'q', '', 'good answer', 'bad answer')
    assert r == {'winner': 'tie', 'consistent': False, 'first_order': 'a', 'second_order': 'b'}


def test_pairwise_consistent_preference():
    assert pairwise(FairClient(), 'j', 'q', '', 'bad answer', 'good answer')['winner'] == 'b'
