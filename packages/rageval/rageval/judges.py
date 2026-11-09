"""
LLM-as-judge.

* **Rubric judge** — one JSON call scores every criterion for an answer (one
  request per item per judge, which matters on a 50-requests/day free tier).
  Verdicts are binary yes/no: binary labels are what humans grade reliably and
  what kappa/calibration are defined over.
* **Panel** — several judges from different model families; the panel verdict
  per criterion is the majority of the judges that gave one (ties -> None).
* **Pairwise** — A/B preference with both orderings; a judge that flips its
  answer when the order flips is reporting position bias, not preference, and
  that comparison counts as a tie.

Applicability is decided here, not by the judge: ``correct`` needs a reference
answer, ``complete`` needs must_include facts, ``faithful`` needs retrieved
context, ``appropriate_refusal`` applies only to unanswerable items. A verdict
on an inapplicable criterion is discarded (None).

Every judgment is cached on disk by (judge, rubric hash, item, answer hash), so
re-judging a baseline under the same panel, or resuming after the daily budget
runs out, costs nothing for work already done.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path

from rageval.llm.openrouter import BudgetExhausted, OpenRouterError
from rageval.schema import GoldenItem, Judgment, RunRecord, read_jsonl, sha, write_jsonl

RUBRIC_VERSION = 1
MAX_CONTEXT_CHARS = 1200
MAX_CONTEXTS = 6

CRITERIA_DEFS = {
    'faithful': 'Every factual claim in the ANSWER is supported by the RETRIEVED CONTEXT. '
                'Claims that contradict the context, or specific facts (numbers, dates, '
                'varieties, rates) that appear nowhere in it, make this "no". Generic '
                'courtesy or advice-free phrasing does not count against it.',
    'correct': 'The ANSWER agrees with the REFERENCE ANSWER on the substance. It may '
               'add detail or word things differently, but must not contradict it or '
               'miss its main point.',
    'complete': 'The ANSWER conveys every fact in MUST-INCLUDE FACTS (paraphrase is fine).',
    'relevant': 'The ANSWER addresses the QUESTION actually asked, without drifting '
                'into a different topic.',
    'appropriate_refusal': 'The QUESTION cannot be answered from the available '
                           'information. "yes" if the ANSWER says so (or asks for '
                           'what it needs) without inventing an answer; "no" if it '
                           'fabricates one.',
}

SYSTEM = (
    'You are a strict, careful evaluator of answers produced by a retrieval-augmented '
    'assistant. Judge only what is asked. Reply with JSON only.'
)


def applicable(item: GoldenItem, rec: RunRecord, criterion: str) -> bool:
    if criterion == 'correct':
        return bool(item.reference_answer) and item.answerable
    if criterion == 'complete':
        return bool(item.must_include) and item.answerable
    if criterion == 'faithful':
        return bool(rec.response.contexts)
    if criterion == 'appropriate_refusal':
        return not item.answerable
    return True


def rubric_hash(criteria: list[str]) -> str:
    return sha({'v': RUBRIC_VERSION, 'system': SYSTEM, 'defs': {c: CRITERIA_DEFS[c] for c in criteria},
                'max_ctx': (MAX_CONTEXT_CHARS, MAX_CONTEXTS)})


def build_prompt(item: GoldenItem, rec: RunRecord, criteria: list[str]) -> str:
    ctx = rec.response.contexts[:MAX_CONTEXTS]
    ctx_txt = '\n\n'.join(f'[{i + 1}] {c.text[:MAX_CONTEXT_CHARS]}' for i, c in enumerate(ctx)) or '(none)'
    lines = [f'QUESTION:\n{item.question}', f'RETRIEVED CONTEXT:\n{ctx_txt}']
    if 'correct' in criteria and item.reference_answer:
        lines.append(f'REFERENCE ANSWER:\n{item.reference_answer}')
    if 'complete' in criteria and item.must_include:
        lines.append('MUST-INCLUDE FACTS:\n' + '\n'.join(f'- {f}' for f in item.must_include))
    lines.append(f'ANSWER:\n{rec.response.answer}')
    lines.append('CRITERIA:\n' + '\n'.join(f'- {c}: {CRITERIA_DEFS[c]}' for c in criteria))
    keys = ', '.join(f'"{c}": "yes" | "no"' for c in criteria)
    lines.append('First reason briefly, then give a verdict for EVERY criterion. Reply with '
                 f'exactly this JSON shape: {{"reasoning": "<2-4 sentences>", "verdicts": {{{keys}}}}}')
    return '\n\n'.join(lines)


def _to_bool(v) -> bool | None:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {'yes', 'y', 'true', 'pass', '1'}:
        return True
    if s in {'no', 'n', 'false', 'fail', '0'}:
        return False
    return None


class JudgeCache:
    def __init__(self, root: Path):
        self.root = Path(root) / 'judgments'

    def _path(self, judge: str, rhash: str, item_id: str, ahash: str) -> Path:
        return self.root / f'{sha([judge, rhash, item_id, ahash], 24)}.json'

    def get(self, judge, rhash, item_id, ahash) -> Judgment | None:
        p = self._path(judge, rhash, item_id, ahash)
        if not p.exists():
            return None
        return Judgment(**json.loads(p.read_text(encoding='utf-8')))

    def put(self, j: Judgment) -> None:
        p = self._path(j.judge, j.rubric_hash, j.item_id, j.answer_hash)
        p.parent.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict
        p.write_text(json.dumps(asdict(j)), encoding='utf-8')


def judge_one(client, judge: str, item: GoldenItem, rec: RunRecord, criteria: list[str],
              temperature: float = 0.0) -> Judgment:
    crit = [c for c in criteria if applicable(item, rec, c)]
    rhash = rubric_hash(criteria)
    base = dict(item_id=item.id, answer_hash=rec.answer_hash, judge=judge, rubric_hash=rhash)
    if not crit:
        return Judgment(**base, verdicts={c: None for c in criteria})
    try:
        data, c = client.complete_json(SYSTEM, build_prompt(item, rec, crit), judge,
                                       temperature=temperature)
    except BudgetExhausted:
        raise
    except OpenRouterError as exc:
        return Judgment(**base, verdicts={c: None for c in criteria}, error=str(exc)[:300])
    raw = (data or {}).get('verdicts') or {}
    verdicts = {k: (_to_bool(raw.get(k)) if k in crit else None) for k in criteria}
    return Judgment(**base, verdicts=verdicts, reasoning=str(data.get('reasoning', ''))[:2000],
                    served_model=c.model, prompt_tokens=c.prompt_tokens,
                    completion_tokens=c.completion_tokens, cost_usd=c.cost_usd,
                    latency_ms=c.latency_ms)


def judge_records(
    client,
    records: Iterable[RunRecord],
    golden: dict[str, GoldenItem],
    panel: list[str],
    criteria: list[str],
    cache: JudgeCache,
    temperature: float = 0.0,
    log: Callable[[str], None] = print,
) -> tuple[list[Judgment], bool]:
    """Judge every (record, judge) pair, cache first. Returns (judgments,
    complete) — complete is False if the daily budget stopped it early."""
    rhash = rubric_hash(criteria)
    out: list[Judgment] = []
    # No answer (crash, or a retrieval-only adapter) -> nothing to judge.
    records = [r for r in records if r.response.answer and not r.response.error and r.item_id in golden]
    for judge in panel:
        for rec in records:
            cached = cache.get(judge, rhash, rec.item_id, rec.answer_hash)
            if cached and not cached.error:
                out.append(cached)
                continue
            try:
                j = judge_one(client, judge, golden[rec.item_id], rec, criteria, temperature)
            except BudgetExhausted as exc:
                log(f'stopped judging: {exc}')
                return out, False
            if not j.error:
                cache.put(j)
            else:
                log(f'  judge {judge} failed on {rec.item_id}: {j.error[:120]}')
            out.append(j)
    return out, True


def judge_run(cfg, run_dir: Path, client, log: Callable[[str], None] = print) -> tuple[list[Judgment], bool]:
    from rageval.runner import load_golden, load_records
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    js, complete = judge_records(client, load_records(run_dir), golden, cfg.panel, cfg.criteria,
                                 JudgeCache(cfg.cache_dir), cfg.get('judges.temperature', 0.0), log)
    write_jsonl(run_dir / 'judgments.jsonl', js)
    return js, complete


def load_judgments(run_dir: Path) -> list[Judgment]:
    return read_jsonl(run_dir / 'judgments.jsonl', Judgment)


def panel_config_hash(panel: list[str], criteria: list[str]) -> str:
    return sha({'panel': sorted(panel), 'rubric': rubric_hash(criteria)})


# ── Aggregation ──────────────────────────────────────────────────────────────

def majority(verdicts: list[bool | None]) -> bool | None:
    votes = [v for v in verdicts if v is not None]
    yes = sum(votes)
    no = len(votes) - yes
    if yes == no:
        return None
    return yes > no


def verdict_table(judgments: list[Judgment], panel: list[str], rhash: str
                  ) -> dict[tuple[str, str], dict[str, dict[str, bool | None]]]:
    """{(item_id, answer_hash): {judge: verdicts}} for the current panel/rubric only."""
    table: dict = {}
    for j in judgments:
        if j.judge in panel and j.rubric_hash == rhash and not j.error:
            table.setdefault((j.item_id, j.answer_hash), {})[j.judge] = j.verdicts
    return table


def panel_verdicts(by_judge: dict[str, dict[str, bool | None]], criteria: list[str]
                   ) -> dict[str, bool | None]:
    return {c: majority([v.get(c) for v in by_judge.values()]) for c in criteria}


# ── Pairwise ─────────────────────────────────────────────────────────────────

PAIRWISE_SYSTEM = ('You compare two answers to the same question and pick the better one '
                   'for a user who wants accurate, grounded, useful help. Reply with JSON only.')


def _pairwise_prompt(question: str, reference: str, first: str, second: str) -> str:
    ref = f'REFERENCE ANSWER (for accuracy):\n{reference}\n\n' if reference else ''
    return (f'QUESTION:\n{question}\n\n{ref}ANSWER 1:\n{first}\n\nANSWER 2:\n{second}\n\n'
            'Which answer is better? Ignore length and style unless they hurt usefulness. '
            'Reply as {"reasoning": "<1-3 sentences>", "winner": "1" | "2" | "tie"}')


def pairwise(client, judge: str, question: str, reference: str, a: str, b: str) -> dict:
    """Judge A vs B in both orders. Returns {'winner': 'a'|'b'|'tie',
    'consistent': bool}. Inconsistent (position-biased) verdicts become ties."""
    d1, _ = client.complete_json(PAIRWISE_SYSTEM, _pairwise_prompt(question, reference, a, b), judge,
                                 temperature=0.0)
    d2, _ = client.complete_json(PAIRWISE_SYSTEM, _pairwise_prompt(question, reference, b, a), judge,
                                 temperature=0.0)
    w1 = {'1': 'a', '2': 'b'}.get(str(d1.get('winner')).strip(), 'tie')
    w2 = {'1': 'b', '2': 'a'}.get(str(d2.get('winner')).strip(), 'tie')
    consistent = w1 == w2
    return {'winner': w1 if consistent else 'tie', 'consistent': consistent,
            'first_order': w1, 'second_order': w2}
