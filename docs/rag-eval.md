# RAG evaluation (`rageval`)

`packages/rageval/` is an app-agnostic evaluation harness for retrieval-augmented
systems. The garden assistant is its first user (`evals/garden/`), and nothing in the
package imports the garden app. Another app plugs in through an adapter and a YAML
config (`packages/rageval/examples/toy_rag/` is a complete second example).

It complements `docs/chat-eval.md`, which covers the MLflow tool-selection eval.
rageval also runs those 20 records (as golden items tagged `tool`) and adds answer
quality, retrieval quality, judge calibration, and a regression gate.

## What it measures

| Family | Metrics | Cost |
|---|---|---|
| Retrieval | `retrieval_hit`, `retrieval_recall`, `retrieval_mrr` against golden `relevant_sources` | none (`garden_retrieval` adapter: no LLM) |
| Deterministic answer checks | `fact_coverage` (must-include facts, lexical), `refused`, `refusal_correct`, `error` | none |
| Garden-specific | `tool_selection`, `no_unintended_writes` (`ml/rag_eval/garden_adapter.py:tool_scorers`) | none |
| LLM judges | `judge_faithful`, `judge_correct`, `judge_complete`, `judge_relevant`, `judge_appropriate_refusal` (panel majority) | 1 request per item per judge |
| Ops | latency p50/p95/p99, per-stage latency, tokens/question, cost, **shadow cost** (same tokens at `cost.shadow_model`'s price) | none |

Every rate comes with a 95% CI: Wilson for proportions, bootstrap otherwise. With
40 items, a pass rate of 80% is really "somewhere between 65% and 90%". Read the
interval, not the point.

## Workflow

All commands run from the repo root with `uv run rageval -c evals/garden/rageval.yaml ...`.
Install once with `uv pip install -e packages/rageval`. The `evaluation` extra also pulls it in.

```
1. synth      generate golden candidates from guide chunks     (~70 free requests)
2. review     accept / edit / reject each candidate            (you)
3. run        system under test answers every golden item, then the panel judges
4. label      blind-grade ~50 answers                          (you)
5. calibrate  panel vs your labels -> calibration.json         (re-judges labelled answers, cached)
6. baseline   snapshot a good run into evals/garden/baselines/<name>  (commit it)
7. compare    gate a candidate run against the baseline        (exit 1 on regression)
```

```bash
uv run rageval -c evals/garden/rageval.yaml or key                         # free-model quota left today
uv run rageval -c evals/garden/rageval.yaml run --adapter garden_retrieval  # retrieval only, no LLM
uv run rageval -c evals/garden/rageval.yaml run                             # full chat agent + judges
uv run rageval -c evals/garden/rageval.yaml label <run-id>
uv run rageval -c evals/garden/rageval.yaml calibrate
uv run rageval -c evals/garden/rageval.yaml baseline <run-id> v1
uv run rageval -c evals/garden/rageval.yaml compare baseline:v1 <new-run-id>
uv run rageval -c evals/garden/rageval.yaml agreement <run-id>              # panel inter-rater stats
uv run rageval -c evals/garden/rageval.yaml pairwise baseline:v1 <run-id>   # A/B preference, order-swapped
```

Each run writes `evals/garden/runs/<run-id>/` (gitignored): `manifest.json`,
`records.jsonl`, `judgments.jsonl`, `summary.json`, `report.md`/`report.html`, and
`compare.md`/`.html` after a compare.

**Testing a prompt or model change:** run once on the current code and snapshot it
as a baseline. Then make the change, run again, and `compare`. The manifest records
the system-under-test fingerprint (LLM model, embedding model, guide table, system
prompt hash, tool schema hash, git sha), so the report shows what changed. To try a
different model without editing `.env`, run `LLM_MODEL=<id> uv run rageval ... run`.

## Free-tier budget

Everything runs on OpenRouter `:free` models (`openrouter.free_only: true` refuses
anything else). This key gets **1,000 free-model requests a day**, shared with
the deployed app and with the chat model under test, plus about 20 per minute.

- A full chat run costs roughly 2-5 requests per item for the agent, plus 3 judge
  requests per item.
- `openrouter.daily_limit` (900) is a local counter that stops a run cleanly before
  the real cap does. OpenRouter's own "per-day" 429 also stops it cleanly.
- Nothing is lost when a run stops. Records are appended one at a time, and
  judgments are cached on disk by (judge, rubric, item, answer). Re-run with
  `--run-id <id>` to resume, or `rageval judge <id>` to finish judging.
- Re-judging the same answer is free. That's why `compare` can bring a baseline up
  to a new judge panel without re-running the agent.

## Judges, calibration, agreement

- **Panel:** three free models from three families, none of them nvidia, because
  the chat model under test is nemotron and judges favour their own family. One JSON
  request scores all applicable criteria. The verdict is the panel majority; ties
  become "undecided" and are excluded, not counted as failures. Re-pick with
  `rageval or models --free`. As of 2026-10-18, `inkling:free` refuses
  non-agent use and `gemma-4-31b:free` is often rate-limited upstream.
- **Applicability is decided by code, not the judge:** `correct` needs a reference
  answer, `complete` needs must-include facts, `faithful` needs retrieved context,
  and `appropriate_refusal` applies only to `answerable: false` items.
- **Inter-rater agreement** (`rageval agreement`, also in every report):
  - Fleiss' kappa over items every judge rated
  - Krippendorff's alpha, which tolerates missing ratings
  - pairwise Cohen's kappa

  All come with bootstrap CIs. Low panel agreement on a criterion means the
  rubric is ambiguous, or one judge is weak.
- **Calibration** (`rageval label`, then `rageval calibrate`): you grade a seeded,
  uniform sample of answers without seeing any judge verdict. A sample chosen by
  judge disagreement would bias every number. For each judge and the panel, per
  criterion, it reports:
  - TPR/TNR, precision, kappa with CI
  - pass-rate bias
  - a trusted flag: kappa ≥ 0.6 on ≥ 20 labels

  Reports also show a **Rogan-Gladen corrected pass rate**, the true pass rate
  backed out of a judge with known sensitivity and specificity.
- **Stale calibration:** calibration is tied to a hash of the panel and the rubric.
  Change either and the status becomes `stale`, and judge metrics drop back to
  report-only until you re-run `calibrate`. Labels store a snapshot of what was
  labelled, so recalibrating re-judges the same answers without the old runs.

## The regression gate

`compare` runs on the items both runs have in common:
- a paired bootstrap CI of (candidate − baseline) for every metric
- an exact McNemar test for binary metrics

A metric **regresses** when the drop is both significant (CI entirely below 0) and
larger than `gate.tolerance` (5 points), or when it falls under a `gate.floors`
value. Deterministic metrics always gate. Judge metrics gate only when calibration
says the panel is trusted for that criterion; otherwise they show as
`untrusted (...)`. `gate.allow_uncalibrated: true` overrides this, but use it
sparingly.

GitHub: `.github/workflows/rag-eval.yaml` is `workflow_dispatch` only, so it never
runs on its own. It needs the repo secrets `OPENROUTER_API_KEY` and `DATABASE_URL`.
The judgment cache is kept in the Actions cache, and the report goes to the job
summary and an artifact.

```bash
gh workflow run rag-eval.yaml -f adapter=garden_chat -f baseline=v1
```

`ci.yaml` runs the package's own offline tests (`packages/rageval/tests`, toy RAG +
fake judge) on every PR.

## OpenRouter tools

- `rageval or models [--free] [--tools] [--min-context N] [--grep S]`: catalogue with prices, cached for a day.
- `rageval or key [--json]`: credits, usage, free-model requests left today.
- `rageval or ping <model>`: one call, showing latency, tokens, cost, and which model/provider actually served it.
- `rageval.llm.openrouter.OpenRouterClient`: the shared client.
  - comma-separated fallback models, sent as `models`
  - 429/5xx retry honouring `Retry-After`
  - `usage.include` for per-call cost
  - RPM pacer, persistent daily budget, `free_only` guard
- The app's chat (`chat_tools._run_openai_compatible_loop`, `llm_provider._openrouter`)
  also accepts a comma-separated `LLM_MODEL` on OpenRouter. The first entry is the
  model and the rest are fallbacks. The request's `models` field must hold the
  **whole** ordered list, primary included. With only the fallbacks in it,
  OpenRouter never falls back (verified live on 2026-10-18). kitchen_design's
  `openai-compatible.ts` sends only the fallbacks and has this bug.
- **Claude Code MCP:** `.mcp.json` registers `openrouter`, launched via
  `scripts/mcp_openrouter.py`. It is the minovap `openrouter-mcp@2.0.1` npm
  package: source-reviewed, version-pinned, and with an allowlist of free models
  only. Approve it on the next `claude` start. Its `ask_model` tool can attach
  local files, which sends their contents to OpenRouter.

## Adding another app

1. Write an adapter: `describe() -> dict` and `answer(item) -> Response(answer,
   contexts=[Context(text, id, source)], tool_calls, tokens, latency)`. Add
   `iter_chunks()` if you want `synth`. Set `judgeable = False` for retrieval-only.
   HTTP services can use the built-in `rageval.adapter:HttpAdapter` with no code.
2. Copy `packages/rageval/examples/toy_rag/rageval.yaml` and point `adapters:` at it.
3. Give chunks stable ids. Content hashes survive re-indexing; row ids don't.

## Known findings (first runs, 2026-10-18)

- **Region filter:** for an Illinois garden, the chat tool's region filter limits
  retrieval to the 531 "Lower Midwest" chunks, out of 4,948 in
  `guide_chunk_openrouter`. That excludes every General and TAMU chunk.
  `garden_retrieval` vs `garden_retrieval_il` measures the effect.
- **Loop limit:** "Should I add cucumbers…" makes 5 tool calls whose results are
  tiny (probably errors from the sparse fixture garden), then answers "I ran into
  a loop".
