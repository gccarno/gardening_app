"""
rageval adapters for the garden assistant — the only garden-specific eval code.

* ``GardenChatAdapter`` runs the real agent (``run_agentic_loop``) end to end
  against a fresh in-memory SQLite garden per question (``build_fixture_db``
  from ml/chat_eval), so an eval can never write to Neon and one question's
  ``add_plant_to_garden`` can't leak into the next question's answer.
* ``GardenRetrievalAdapter`` calls only ``search_guides`` — no LLM, so it costs
  nothing against the OpenRouter free-model quota. Use it to check embedding /
  chunking / k / region-filter changes.

Nothing in the app is modified to make this observable. Per answer, the chat
adapter temporarily wraps three module attributes and restores them after:

* ``chat_tools.execute_tool`` -> which tools ran, and their results (contexts)
* ``build_rag.search_guides`` -> the full retrieved chunks; md5(text) is the same
  chunk id build_rag.py dedupes on, so golden ``relevant_sources`` survive re-indexing
* ``chat_tools.set_outputs``  -> per-round prompt/completion tokens, which every
  LLM round reports through it whether or not MLflow is installed

Wired up in evals/garden/rageval.yaml; see docs/rag-eval.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# llm_provider / embed_provider read their env vars at import time, so .env must
# be loaded before anything below imports them (docs/chat-eval.md, lesson 1).
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / '.env')
for p in (str(REPO), str(REPO / 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

from rageval.llm.openrouter import BudgetExhausted  # noqa: E402
from rageval.schema import Context, GoldenItem, Response, sha  # noqa: E402

TOOL_RESULT_CHARS = 1500


def chunk_id(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _active_table():
    import build_rag
    return build_rag._guide_chunk_model()


def iter_guide_chunks():
    """Every chunk in the active guide table, for ``rageval synth``."""
    from sqlalchemy import select

    from apps.backend.app.db.session import SessionLocal
    Model = _active_table()
    with SessionLocal() as db:
        for text, source, region in db.execute(select(Model.text, Model.source, Model.region)):
            yield {'id': chunk_id(text), 'text': text, 'source': f'{source} [{region}]'}


def _system_under_test() -> dict:
    from apps.ml_service.app import embed_provider as ep
    from apps.ml_service.app import llm_provider
    return {
        'llm_provider': llm_provider.PROVIDER,
        'llm_model': llm_provider._MODEL or llm_provider._DEFAULTS.get(llm_provider.PROVIDER),
        'embed_provider': ep.PROVIDER,
        'embed_model': ep._MODEL or ep._DEFAULTS.get(ep.PROVIDER),
        'embed_dims': ep.DIMS,
        'guide_table': _active_table().__tablename__,
    }


class GardenChatAdapter:
    def __init__(self, max_tool_rounds: int = 5):
        self.name = 'garden_chat'
        self.max_tool_rounds = max_tool_rounds

    def describe(self) -> dict:
        from apps.ml_service.app.chat_tools import _OPENAI_TOOL_SCHEMAS
        from ml.chat_eval.run_eval import SYSTEM_PROMPT
        return {**_system_under_test(),
                'system_prompt_hash': sha(SYSTEM_PROMPT),
                'tool_schema_hash': sha(_OPENAI_TOOL_SCHEMAS),
                'max_tool_rounds': self.max_tool_rounds}

    def iter_chunks(self):
        return iter_guide_chunks()

    def answer(self, item: GoldenItem) -> Response:
        import build_rag
        from openai import APIStatusError

        from apps.ml_service.app import chat_tools
        from ml.chat_eval.run_eval import FIXTURE_SUMMARY, SYSTEM_PROMPT, build_fixture_db

        tools: list[str] = []
        contexts: list[Context] = []
        usage = {'prompt': 0, 'completion': 0}
        timing = {'retrieval': 0.0, 'tools': 0.0}

        orig_exec, orig_search, orig_set = (chat_tools.execute_tool, build_rag.search_guides,
                                            chat_tools.set_outputs)

        def search(*a, **kw):
            t0 = time.perf_counter()
            results = orig_search(*a, **kw)
            timing['retrieval'] += (time.perf_counter() - t0) * 1000
            contexts.extend(Context(text=r['text'], id=chunk_id(r['text']),
                                    source=f"{r.get('source')} [{r.get('region')}]",
                                    score=r.get('score')) for r in results)
            return results

        def execute(name, input_data, garden, db):
            t0 = time.perf_counter()
            result = orig_exec(name, input_data, garden, db)
            timing['tools'] += (time.perf_counter() - t0) * 1000
            tools.append(name)
            if name != 'search_growing_guides':    # guide passages are captured in full by search()
                contexts.append(Context(text=json.dumps(result, default=str)[:TOOL_RESULT_CHARS],
                                        source=f'tool:{name}'))
            return result

        def set_outputs(span, outputs):
            if isinstance(outputs, dict) and 'prompt_tokens' in outputs:
                usage['prompt'] += outputs.get('prompt_tokens') or 0
                usage['completion'] += outputs.get('completion_tokens') or 0
            return orig_set(span, outputs)

        db, garden = build_fixture_db()
        chat_tools.execute_tool, build_rag.search_guides, chat_tools.set_outputs = execute, search, set_outputs
        t0 = time.perf_counter()
        try:
            answer = chat_tools.run_agentic_loop(
                SYSTEM_PROMPT, [{'role': 'user', 'content': item.question}], garden, db,
                max_tool_rounds=self.max_tool_rounds)
        except APIStatusError as exc:
            if exc.status_code == 429 and 'per-day' in str(exc).lower():
                raise BudgetExhausted(str(exc)) from exc
            raise
        finally:
            chat_tools.execute_tool, build_rag.search_guides, chat_tools.set_outputs = orig_exec, orig_search, orig_set
            db.close()
        total = (time.perf_counter() - t0) * 1000
        # The system prompt hands the model these garden facts (e.g. "Chicago IL");
        # without them judges flag every use of them as unsupported. Added first so
        # the judges' context cap can't drop it, and only when something was
        # retrieved: a no-tool answer stays out of the faithfulness metric.
        if contexts:
            contexts.insert(0, Context(text=FIXTURE_SUMMARY, source='system:garden_context'))

        return Response(
            answer=answer,
            contexts=contexts,
            tool_calls=tools,
            model=os.environ.get('LLM_MODEL'),
            prompt_tokens=usage['prompt'] or None,
            completion_tokens=usage['completion'] or None,
            cost_usd=0.0 if (os.environ.get('LLM_MODEL') or '').endswith(':free') else None,
            latency_ms=total,
            stage_latency_ms={'retrieval': timing['retrieval'], 'tools': timing['tools'],
                              'llm': max(total - timing['tools'], 0.0)},
        )


class GardenRetrievalAdapter:
    """Retrieval only. ``region_filter`` mirrors what the chat tool applies for a
    garden's state (an Illinois garden searches only 'Lower Midwest' chunks)."""

    judgeable = False      # nothing to judge: there is no generated answer

    def __init__(self, k: int = 3, region_filter: str | None = None):
        self.name = 'garden_retrieval'
        self.k = k
        self.region_filter = region_filter

    def describe(self) -> dict:
        s = _system_under_test()
        return {k: s[k] for k in ('embed_provider', 'embed_model', 'embed_dims', 'guide_table')} | {
            'k': self.k, 'region_filter': self.region_filter}

    def iter_chunks(self):
        return iter_guide_chunks()

    def answer(self, item: GoldenItem) -> Response:
        import build_rag
        t0 = time.perf_counter()
        results = build_rag.search_guides(item.question, n_results=self.k,
                                          region_filter=self.region_filter)
        latency = (time.perf_counter() - t0) * 1000
        if not results:
            # search_guides swallows embedding/DB failures and returns []; for an
            # eval that is an error, not "nothing relevant".
            return Response(answer='', error='search_guides returned no results', latency_ms=latency)
        return Response(
            answer='',
            contexts=[Context(text=r['text'], id=chunk_id(r['text']),
                              source=f"{r.get('source')} [{r.get('region')}]", score=r.get('score'))
                      for r in results],
            latency_ms=latency,
            stage_latency_ms={'retrieval': latency},
        )


def tool_scorers(item: GoldenItem, resp: Response) -> dict:
    """Garden-only scorers from the original chat eval (ml/chat_eval/scorers.py),
    driven by ``item.meta``. Not applicable (None) to items without expectations."""
    from apps.ml_service.app.chat_tools import WRITE_TOOLS
    out = {'tool_selection': None, 'no_unintended_writes': None}
    if not resp.answer:          # retrieval-only run: no agent ran, nothing to score
        return out
    meta = item.meta or {}
    called = set(resp.tool_calls)
    required = set(meta.get('expected_tools') or [])
    any_of = set(meta.get('expected_any') or [])
    forbidden = set(meta.get('forbid_tools') or [])
    if required or any_of or forbidden:
        out['tool_selection'] = not (forbidden & called) and required <= called and (
            not any_of or bool(any_of & called))
    if meta.get('forbid_writes'):
        out['no_unintended_writes'] = not (called & WRITE_TOOLS)
    return out
