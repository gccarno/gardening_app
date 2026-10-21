"""
Deterministic per-item metrics (no LLM) and run-level operational stats.

Per-item metric values are floats in [0, 1] (binary metrics are 0/1), or None
when the metric doesn't apply to the item — e.g. retrieval recall on an item
with no ``relevant_sources``. None is excluded from means, never counted as 0.

App-specific scorers plug in via config ``scorers:`` — each is
``fn(item, response) -> dict[str, float | bool | None]``.
"""
from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

from rageval.schema import GoldenItem, Response

REFUSAL_RE = re.compile(
    r"\b(i (?:don't|do not|can't|cannot) (?:know|find|say|answer)|i'm not sure|i am not sure|"
    r"(?:no|not enough) information|couldn't find|could not find|unable to (?:find|answer)|"
    r"outside (?:of )?(?:my|the) (?:scope|guides)|not (?:something|able) i|"
    # "the data isn't there" abstentions, common when the answer depends on app state
    r"i (?:don't|do not) have (?:a |any )?(?:record|data|information|access|a tool|tools?)|"
    r"(?:doesn't|does not|don't|do not) (?:store|record|include|track)|"
    r"no record(?:s|ed)?\b|(?:isn't|is not|aren't|are not) recorded)",
    re.IGNORECASE,
)
# Models often write a typographic apostrophe (don’t); the pattern uses ASCII.
_APOSTROPHES = str.maketrans({'’': "'", '‘': "'"})
_WORD = re.compile(r'[a-z0-9]+(?:\.[0-9]+)?')
_STOP = {'with', 'that', 'this', 'from', 'have', 'into', 'your', 'they', 'them', 'than',
         'then', 'when', 'what', 'will', 'about', 'should', 'which', 'there', 'their'}


def _content_words(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if (len(w) > 3 or any(ch.isdigit() for ch in w))
            and w not in _STOP}


def fact_covered(fact: str, answer: str, threshold: float = 0.8) -> bool:
    """Lexical check: >= threshold of the fact's content words appear in the
    answer. Crude on purpose — the judge's ``complete`` criterion is the
    semantic version; this one is free and never flakes."""
    words = _content_words(fact)
    if not words:
        return True
    return len(words & _content_words(answer)) / len(words) >= threshold


def retrieval_metrics(item: GoldenItem, resp: Response, k: int | None = None) -> dict[str, float | None]:
    relevant = set(item.relevant_sources)
    ids = [c.id for c in resp.contexts if c.id]
    if not relevant or not resp.contexts:
        return {'retrieval_hit': None, 'retrieval_recall': None, 'retrieval_mrr': None}
    ids = ids[:k] if k else ids
    hits = [i for i, cid in enumerate(ids) if cid in relevant]
    return {
        'retrieval_hit': 1.0 if hits else 0.0,
        'retrieval_recall': len(relevant & set(ids)) / len(relevant),
        'retrieval_mrr': 1.0 / (hits[0] + 1) if hits else 0.0,
    }


def item_metrics(item: GoldenItem, resp: Response,
                 scorers: list[Callable] | None = None) -> dict[str, float | None]:
    out: dict[str, float | None] = {'error': 1.0 if resp.error else 0.0}
    out.update(retrieval_metrics(item, resp))
    if resp.error:
        # Leave quality metrics undefined rather than scoring a crash as a bad answer;
        # the error metric above is what records the failure.
        out.update({'fact_coverage': None, 'refused': None, 'refusal_correct': None})
        return out
    if not resp.answer:
        # Retrieval-only adapters return contexts and no answer: answer metrics don't apply.
        out.update({'fact_coverage': None, 'refused': None, 'refusal_correct': None})
    else:
        out.update(_answer_metrics(item, resp))
    for fn in scorers or []:
        for k, v in (fn(item, resp) or {}).items():
            out[k] = None if v is None else float(v)
    return out


def _answer_metrics(item: GoldenItem, resp: Response) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    out['fact_coverage'] = (
        float(np.mean([fact_covered(f, resp.answer) for f in item.must_include]))
        if item.must_include else None)
    refused = bool(REFUSAL_RE.search(resp.answer.translate(_APOSTROPHES)))
    out['refused'] = 1.0 if refused else 0.0
    # Refusing an unanswerable question is right; refusing an answerable one is wrong.
    out['refusal_correct'] = 1.0 if refused != item.answerable else 0.0
    return out


def percentile(xs: list[float], q: float) -> float | None:
    xs = [x for x in xs if x is not None]
    return float(np.percentile(xs, q)) if xs else None


def ops_stats(responses: list[Response], shadow_price: tuple[float, float] | None = None) -> dict:
    """Latency / token / cost roll-up. ``shadow_price`` = (USD per prompt token,
    USD per completion token) of a reference paid model: what this run *would*
    cost there, which keeps cost visible while everything runs on free models."""
    lat = [r.latency_ms for r in responses if r.latency_ms is not None and not r.error]
    pt = [r.prompt_tokens for r in responses if r.prompt_tokens is not None]
    ct = [r.completion_tokens for r in responses if r.completion_tokens is not None]
    costs = [r.cost_usd for r in responses if r.cost_usd is not None]
    stages: dict[str, list[float]] = {}
    for r in responses:
        for k, v in (r.stage_latency_ms or {}).items():
            stages.setdefault(k, []).append(v)
    n = len(responses)
    out = {
        'n': n,
        'errors': sum(1 for r in responses if r.error),
        'latency_ms_p50': percentile(lat, 50),
        'latency_ms_p95': percentile(lat, 95),
        'latency_ms_p99': percentile(lat, 99),
        'prompt_tokens_mean': float(np.mean(pt)) if pt else None,
        'completion_tokens_mean': float(np.mean(ct)) if ct else None,
        'cost_usd_total': float(sum(costs)) if costs else None,
        'cost_usd_per_q': float(sum(costs) / len(costs)) if costs else None,
        'stage_latency_ms_p50': {k: percentile(v, 50) for k, v in stages.items()},
    }
    if shadow_price and pt and ct:
        p_in, p_out = shadow_price
        total = sum(pt) * p_in + sum(ct) * p_out
        out['shadow_cost_usd_total'] = total
        out['shadow_cost_usd_per_q'] = total / max(len(pt), 1)
    return out
