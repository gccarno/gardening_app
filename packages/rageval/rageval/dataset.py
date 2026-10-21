"""
Golden-set construction: synthetic candidates from the app's corpus, then a
human review gate. Nothing synthetic reaches ``golden.jsonl`` unreviewed.

``synth`` samples chunks round-robin across sources (so one long document can't
dominate), asks a model to write a question a real user would ask, a reference
answer drawn only from the chunk, and 2-4 must-include facts. Chunks the model
flags as unusable (tables of contents, boilerplate) are dropped.
"""
from __future__ import annotations

import random
import textwrap
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict

from rageval.llm.openrouter import BudgetExhausted, OpenRouterError
from rageval.schema import GoldenItem, append_jsonl, read_jsonl, sha, write_jsonl

SYNTH_SYSTEM = 'You write evaluation questions for a retrieval-augmented assistant. Reply with JSON only.'

SYNTH_PROMPT = """Below is a passage from the assistant's knowledge base.
{audience}

Write ONE question a real user might ask that this passage answers. The question
must make sense on its own: never mention "the passage", "the text" or "the guide".
Then write the reference answer using ONLY facts in the passage (1-3 sentences),
and 2-4 short must-include facts a correct answer needs.

If the passage has no usable facts (table of contents, index, copyright notice,
fragment), set "usable" to false.

PASSAGE (source: {source}):
{text}

Reply as {{"usable": true, "question": "...", "reference_answer": "...",
"must_include": ["...", "..."], "category": "<one or two words>"}}"""


def stratified_sample(chunks: Iterable[dict], n: int, seed: int = 0) -> list[dict]:
    by_source: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        if len(c.get('text', '')) >= 200:        # fragments make bad questions
            by_source[c.get('source') or '?'].append(c)
    rng = random.Random(seed)
    for v in by_source.values():
        rng.shuffle(v)
    sources = sorted(by_source)
    rng.shuffle(sources)
    out = []
    while len(out) < n and any(by_source.values()):
        for s in sources:
            if by_source[s] and len(out) < n:
                out.append(by_source[s].pop())
    return out


def synth(chunks: Iterable[dict], client, model: str, n: int, out_path, seed: int = 0,
          audience: str = '', log: Callable[[str], None] = print) -> int:
    """Append up to ``n`` candidates to ``out_path`` (skipping chunks already
    there, so it resumes). Returns the number written this call."""
    existing = {c['source_chunk'] for c in read_jsonl(out_path)}
    picked = [c for c in stratified_sample(chunks, n, seed) if c['id'] not in existing]
    written = 0
    for c in picked:
        try:
            data, comp = client.complete_json(
                SYNTH_SYSTEM, SYNTH_PROMPT.format(audience=audience, source=c.get('source'),
                                                  text=c['text'][:3000]), model, temperature=0.7)
        except BudgetExhausted as exc:
            log(f'stopped: {exc}')
            break
        except OpenRouterError as exc:
            log(f'  skip {c["id"]}: {exc}')
            continue
        if not data.get('usable', True) or not data.get('question'):
            # Recorded so a resumed synth doesn't spend another request on it.
            append_jsonl(out_path, {'status': 'unusable', 'source_chunk': c['id']})
            continue
        append_jsonl(out_path, {
            'status': 'pending',
            'source_chunk': c['id'],
            'source': c.get('source'),
            'passage': c['text'],
            'generator': comp.model,
            'item': asdict(GoldenItem(
                id=f"synth-{sha(c['id'], 8)}",
                question=str(data['question']).strip(),
                reference_answer=str(data.get('reference_answer', '')).strip(),
                must_include=[str(f) for f in data.get('must_include', [])][:4],
                relevant_sources=[c['id']],
                category=str(data.get('category') or 'general').strip().lower(),
                tags=['synthetic'],
            )),
        })
        written += 1
        log(f'  [{written}] {data["question"][:90]}')
    return written


def review(candidates_path, golden_path, ask: Callable[[str], str] = input,
           out: Callable[[str], None] = print) -> tuple[int, int]:
    """Accept / edit / reject pending candidates. Status is saved after every
    decision. Returns (accepted, rejected) this session."""
    cands = read_jsonl(candidates_path)
    golden_ids = {g.id for g in read_jsonl(golden_path, GoldenItem)}
    accepted = rejected = 0
    pending = [c for c in cands if c['status'] == 'pending']
    out(f'{len(pending)} pending. a = accept, e = edit, r = reject, q = quit')
    for c in pending:
        it = c['item']
        out('=' * 100)
        out(f"SOURCE ({c.get('source')}):\n{textwrap.fill(c['passage'][:1500], 100)}")
        out(f"\nQ: {it['question']}\nREF: {it['reference_answer']}\n"
            f"FACTS: {'; '.join(it['must_include'])}\nCATEGORY: {it['category']}")
        a = ''
        while a not in ('a', 'e', 'r', 'q'):
            a = ask('[a/e/r/q] ').strip().lower()
        if a == 'q':
            break
        if a == 'e':
            for key in ('question', 'reference_answer', 'category'):
                new = ask(f'  {key} (enter = keep): ').strip()
                if new:
                    it[key] = new
            facts = ask('  must_include, separated by ";" (enter = keep): ').strip()
            if facts:
                it['must_include'] = [f.strip() for f in facts.split(';') if f.strip()]
            a = 'a'
        if a == 'a':
            if it['id'] not in golden_ids:
                append_jsonl(golden_path, it)
                golden_ids.add(it['id'])
            c['status'] = 'accepted'
            accepted += 1
        elif a == 'r':
            c['status'] = 'rejected'
            rejected += 1
        write_jsonl(candidates_path, cands)
    return accepted, rejected
