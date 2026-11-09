"""
Blind human labelling for judge calibration.

Shows the question, the reference, the retrieved context and the answer — never
any judge verdict, so the labels stay independent of the thing they calibrate.
The sample is seeded and uniform over the run's (non-error) records: a sample
chosen by judge disagreement would bias every calibration number computed from
it. Each label is appended as soon as it's given, so quitting loses nothing.
"""
from __future__ import annotations

import random
import textwrap
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime

from rageval.calibration import load_labels
from rageval.judges import applicable
from rageval.runner import load_golden, load_records
from rageval.schema import HumanLabel, append_jsonl

PROMPT_HELP = 'y = yes, n = no, s = skip criterion, q = save & quit'


def sample_for_labelling(cfg, run_dir, n: int, seed: int = 0):
    golden = {g.id: g for g in load_golden(cfg.golden_path)}
    labelled = {(lab.item_id, lab.answer_hash) for lab in load_labels(cfg.labels_path)}
    recs = sorted((r for r in load_records(run_dir)
                   if not r.response.error and r.item_id in golden), key=lambda r: r.item_id)
    random.Random(seed).shuffle(recs)
    # Draw the first n of a fixed permutation, then drop already-labelled ones:
    # resuming continues the same sample instead of drawing a new one.
    picked = recs[:n]
    return [(golden[r.item_id], r) for r in picked if (r.item_id, r.answer_hash) not in labelled]


def _show(item, rec, out: Callable[[str], None]) -> None:
    wrap = lambda s: textwrap.fill(s, 100, replace_whitespace=False)
    out('=' * 100)
    out(f'[{item.id}] ({item.category}{"" if item.answerable else ", UNANSWERABLE by design"})')
    out(f'QUESTION: {wrap(item.question)}')
    if item.reference_answer:
        out(f'REFERENCE: {wrap(item.reference_answer)}')
    if item.must_include:
        out('MUST INCLUDE: ' + '; '.join(item.must_include))
    for i, c in enumerate(rec.response.contexts[:6], 1):
        out(f'--- context {i} ({c.source or "?"}) ---\n{wrap(c.text[:900])}')
    out(f'--- ANSWER ---\n{wrap(rec.response.answer)}')


def label_run(cfg, run_dir, n: int = 50, seed: int = 0, labeler: str = '',
              ask: Callable[[str], str] = input, out: Callable[[str], None] = print) -> int:
    todo = sample_for_labelling(cfg, run_dir, n, seed)
    out(f'{len(todo)} answers to label. {PROMPT_HELP}')
    done = 0
    for item, rec in todo:
        _show(item, rec, out)
        verdicts = {}
        for c in cfg.criteria:
            if not applicable(item, rec, c):
                verdicts[c] = None
                continue
            while True:
                a = ask(f'  {c}? [y/n/s/q] ').strip().lower()
                if a in ('y', 'n', 's', 'q'):
                    break
            if a == 'q':
                out(f'saved {done} labels')
                return done
            verdicts[c] = {'y': True, 'n': False}.get(a)
        note = ask('  note (optional): ').strip()
        append_jsonl(cfg.labels_path, HumanLabel(
            item_id=item.id, answer_hash=rec.answer_hash, verdicts=verdicts, labeler=labeler,
            note=note, ts=datetime.now(UTC).isoformat(), record=asdict(rec)))
        done += 1
    out(f'saved {done} labels')
    return done
