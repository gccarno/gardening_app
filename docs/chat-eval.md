# Chat agent: tracing and evaluation

Phase 2 of the observability work. Offline harness for the garden chat agent —
MLflow tracing plus a scored evaluation set. **Local and CI only; nothing here
ships to Render.**

See [`observability.md`](observability.md) for Phase 1 (Sentry) and the roadmap.

---

## Why

`apps/ml_service/app/chat_tools.py` is a ~1000-line agentic tool loop with 12
tools. Before this, changing a system prompt or a tool description gave you no
way to tell whether the agent got better or worse. The old `chat_logger.py`
wrote JSONL into `logs/`, which Render deletes on every redeploy — that's a log,
not a measurement. It has been **replaced** by MLflow tracing.

## Hard constraint: MLflow must never reach production

MLflow is in the `evaluation` extra, not `[project.dependencies]`:

```toml
[project.optional-dependencies]
evaluation = ["mlflow>=3.8"]
```

Render builds with `uv sync --frozen --no-dev`, which installs **no extras**, so
MLflow is absent in production. That is deliberate — it has no business on a
512 MB free instance.

Because `chat_tools.py` *is* imported by the live backend, a bare `import mlflow`
in the agent would take production down. Everything goes through
`apps/ml_service/app/tracing.py`, which degrades to a no-op when the import
fails. Verified by blocking the import via `sys.meta_path` and confirming the app
still starts.

> ⚠️ After editing `pyproject.toml`, always run `uv lock`. `uv sync --frozen`
> **fails** if the lockfile doesn't match, which breaks the Render build.

## What's instrumented

| Span | Type | Where |
|---|---|---|
| `run_agentic_loop` | CHAIN | root of every agent run |
| `ollama_agentic_loop` | AGENT | Ollama tool loop |
| `ollama_round_N` | LLM | one per round, records token counts |
| `execute_tool` | TOOL | one per tool call — all 12 route through here |
| `search_growing_guides_retriever` | RETRIEVER | the RAG lookup |

Two things worth knowing:

**`mlflow.anthropic.autolog()` does nothing on the Ollama path.** The original
plan assumed autolog would capture LLM calls without touching the loop. That's
true only for the Anthropic path, which uses the SDK. `_run_ollama_loop` calls
Ollama over raw HTTP with `requests.post`, which no autolog integration patches —
hence the explicit `ollama_round_N` spans.

**One decorator covers all 12 tools.** They all dispatch through `execute_tool`,
so a single `@trace` there records which tool ran, with what arguments, and what
came back. That chokepoint is also what the tool-selection scorer reads.

## RAG evaluation

Per the eval skill's retrieval guidance, MLflow's built-in RAG scorers only fire
on a span of type `RETRIEVER`, and expect documents shaped
`{page_content, metadata}`. `search_guides()` returns
`{text, source, plant, region, page, score}`, so the span translates between them
rather than changing the tool's return shape — the LLM prompt depends on that
shape.

Three built-in scorers are wired behind `--retrieval-scorers`:

- `RetrievalGroundedness` — is the answer supported by what was retrieved?
- `RetrievalRelevance` — were the retrieved chunks on-topic?
- `RetrievalSufficiency` — was enough retrieved to answer at all?

They score `None` on questions that never touch the guide corpus. That's expected,
not a failure.

## Scorers

Deliberately split by cost:

| Scorer | Type | Cost | What it catches |
|---|---|---|---|
| `tool_selection` | deterministic | free | agent answers from memory instead of looking up real data |
| `no_unintended_writes` | deterministic | free | agent silently writes to the garden when asked an opinion |
| `groundedness` | LLM judge | judge call | generic advice that ignores the user's actual garden |
| `no_hallucinated_data` | LLM judge | judge call | invented forecasts, dates, bed sizes |
| `Retrieval*` | LLM judge | judge call | RAG quality |

The deterministic pair read the trace directly — no model, no key, no flake.
Those are the ones worth running on every prompt edit.

> ⚠️ Judge instructions must return `"yes"`/`"no"`. MLflow silently casts
> `"pass"`/`"fail"` to `None` and drops them from metrics with no warning.

## Write safety

Two tools mutate: `add_plant_to_garden` and `create_task` (see
`chat_tools.WRITE_TOOLS`). The agent decides on its own whether to call them, so
an eval question like *"should I plant cucumbers?"* can write a real row.

`run_eval.build_fixture_db()` therefore builds its **own in-memory SQLite garden**
and never touches `DATABASE_URL`. An eval run cannot mutate production Neon. Do
not "simplify" this by reusing the app's session.

The dataset includes deliberate trap cases (`forbid_writes: True`) phrased near a
mutation, plus one case that *should* write ("remind me to fertilise…").

## Running it

```bash
uv pip install "mlflow>=3.8"
ollama serve                      # separate terminal

# 3-question gate — always run this first
uv run python -m ml.chat_eval.run_eval --dry-run

# full set (deterministic scorers only — free)
uv run python -m ml.chat_eval.run_eval

# add LLM judges + RAG scorers
uv run python -m ml.chat_eval.run_eval --judge-model ollama:/llama3.1 --retrieval-scorers

# inspect traces
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

`run_eval` calls `load_dotenv()` before importing anything else — `llm_provider`
reads `LLM_PROVIDER`/`LLM_MODEL` at import time, so a late load silently
evaluates the wrong provider. That bug cost a dry run.

MLflow 3.x put the `./mlruns` file store into maintenance mode and refuses to
open one, so the local backend is `sqlite:///mlflow.db` (gitignored).

## Known environment problem: Ollama + CUDA

**Ollama 0.32.0 on this machine's RTX 3060 fails on every request**, with any
model, with or without tools:

```
llama-server process has terminated: exit status 0xc0000409
CUDA error: device kernel image is invalid
```

`device kernel image is invalid` means Ollama's bundled CUDA kernels weren't
built for the GPU's compute capability. It is not a model, schema, or agent
problem — a 1B model with no tools fails identically.

**Workaround (verified):** force CPU inference.

```bash
OLLAMA_NUM_GPU=0 uv run python -m ml.chat_eval.run_eval
```

`_run_ollama_loop` passes `options.num_gpu` through when `OLLAMA_NUM_GPU` is set,
and leaves Ollama's own GPU decision alone otherwise. CPU is slow but correct —
`llama3.1:latest` scored 3/3 on tool selection this way.

**Real fixes, in order of likelihood:** update the NVIDIA driver; reinstall or
roll back Ollama (0.32.0 may have shipped kernels missing `sm_86`); confirm
`ollama ps` shows the GPU at all.

### A second finding: `gemma4:e2b` is the wrong model for this

`.env` sets `LLM_MODEL=gemma4:e2b`, a ~2B model. Even once CUDA is fixed, a model
that small selecting between 12 tools is a poor bet. `llama3.1:latest` is
already pulled locally and handles the tool loop correctly.

---

## Cost: self-hosting a model vs. calling an API

Asked during Phase 2. Short answer: **for this app, APIs win by roughly three
orders of magnitude, and it isn't close.**

### The numbers

Cloud GPU rental is billed by wall-clock time, whether or not you're serving
anything:

| GPU | ~$/hr | $/month at 24×7 |
|---|---|---|
| RTX 4090 (RunPod community) | $0.34 | ~$245 |
| RTX 4090 (JarvisLabs) | $0.59 | ~$425 |
| L4 | $0.44 | ~$317 |
| A100 80GB (on-demand) | $1.07–1.99 | ~$770–1,430 |
| H100 | $2.34–3.29 | ~$1,685–2,370 |

Serverless open-model APIs are billed per token:

| Model | Provider | $/M input | $/M output |
|---|---|---|---|
| Llama 3.1 8B | DeepInfra | ~$0.02–0.06 | — |
| Llama 3.1 8B | Groq | $0.05 | — |
| Llama 3.3 70B | DeepInfra | $0.23 | $0.40 |
| Llama 3.3 70B | Groq | $0.59 | $0.79 |
| Llama 3.3 70B | Together | ~$0.88 | ~$0.90 |

### Applied to this app

The agent loop is token-heavy: system prompt + 12 tool schemas + history + tool
results, up to 5 rounds. Estimate ~20K input and ~1K output tokens per question.

At DeepInfra's Llama 3.3 70B rate: **~$0.005 per question** — half a cent.

- 100 questions/month → **$0.50/month**
- Break-even against a $245/month 4090 → **~49,000 questions/month**, about
  1,600 per day, sustained

For a personal garden app, utilisation is effectively zero. You would be renting
a GPU by the hour to serve a handful of questions a day.

### When self-hosting does make sense

- **Sustained high volume** — past roughly 1,600 questions/day the arithmetic flips.
- **Data that cannot leave your infrastructure** — a compliance argument, not a cost one.
- **You already own the GPU.** Your RTX 3060 costs only electricity: ~200W for an
  hour a day at $0.15/kWh is **under $1/month**. This is why local Ollama is the
  right choice for development and eval — once CUDA works.

### If you want cloud chat anyway

Note that **local Ollama cannot serve the deployed app**: Render's free instance
has 512 MB and no GPU, and your phone talks to Render, not your desktop. Options:

1. **Serverless open-model API** (DeepInfra/Groq) — add an OpenAI-compatible
   provider to `llm_provider.py`, which already has the dispatch structure. Cents
   per month.
2. **Keep `ANTHROPIC_API_KEY` on Render** — already supported today.
3. **Scale-to-zero GPU** (RunPod serverless) — per-second billing, but a 70B cold
   start is 1–2 minutes, which is a bad chat experience.

Recommendation: local Ollama for dev and eval, a serverless API for production.
Renting a dedicated GPU is the one option that makes no sense at this scale.

---

## Why MLflow's backend store is a database (and the Neon question)

Asked during Phase 2: *what's the issue with using a Neon branch to record ML
experimentation?*

**There isn't one — it's actively the supported direction.** MLflow 3.x refuses
to open the old `./mlruns` file store:

> The filesystem tracking backend is in maintenance mode and will not receive
> further updates. Please migrate to a database backend.

The tracking backend is any SQLAlchemy URL, so a Neon Postgres branch works
exactly like the local SQLite:

```bash
export MLFLOW_TRACKING_URI="postgresql://…neon.tech/mlflow"
uv run python -m ml.chat_eval.run_eval
```

Genuine advantages: results survive a laptop rebuild, CI runs and local runs land
in one place, and Neon branching gives a throwaway store per experiment.

Real trade-offs to weigh:

- **Traces are bulky.** Every span, prompt and tool result is stored. Your Neon
  free tier is 0.5 GB with ~54 MB used; a few hundred agent traces with full
  prompts will make a visible dent. Use a **separate database or branch**, never
  the app's tables.
- **Latency.** Each trace write becomes a network round-trip. Local SQLite is
  faster for tight iteration.
- **It couples experiments to prod infrastructure.** A schema migration or branch
  reset can take your experiment history with it.

Sensible split: **SQLite locally** (default, zero setup, gitignored), **a Neon
branch when you want durable or shared history** — which pairs naturally with
Phase 3, since that's Neon branching anyway.

---

## Baseline (2026-07-26)

`llama3.1:latest`, CPU inference, 20 questions, deterministic scorers:

| Scorer | Score |
|---|---|
| `tool_selection` | **0.90** (18/20) |
| `no_unintended_writes` | **1.00** (20/20) |

Two genuine failures remain, both worth fixing in the system prompt:

1. **"When is my last frost date?"** → called `get_garden_plan` instead of
   `check_planting_calendar`. It reached for the general garden-state tool rather
   than the specific one. The tool descriptions likely need sharper boundaries.
2. **"What is the capital of France?"** → called `search_growing_guides`. The
   agent has no notion of an out-of-scope question and reaches for its corpus
   anyway.

`no_unintended_writes` at 1.00 is the genuinely reassuring result: across every
trap question phrased near a mutation, the agent never wrote to the garden.

### The first run measured the eval's own bugs

Worth recording, because it will happen again. The first full run scored
`tool_selection` 0.75 — but **three of those five failures were faults in this
dataset, not the agent**:

- "How deep should I plant seedlings?" listed two acceptable tools, which the
  scorer read as *both required*. That's now `expected_any`.
- Two opinion questions ("should I add cucumbers?") expected **zero** tool calls,
  marking reasonable context-gathering as wrong. Those now use `forbid_tools`,
  which targets the behaviour that actually matters — not writing.

Fixing the expectations moved the score 0.75 → 0.90 without the agent changing at
all. **Treat the 0.75 as void.** When a new eval produces a bad number, suspect
the eval before the agent.

Because `tool_selection` is deterministic over the trace, the corrected figure was
obtained by re-scoring the recorded traces rather than re-running the agent —
same result, seconds instead of a long CPU run.

## Status

- ✅ Tracing wired; production verified safe with MLflow absent
- ✅ `chat_logger.py` deleted; its error paths now report to Sentry instead of an
  ephemeral file
- ✅ 20-question dataset, including write traps and RAG questions
- ✅ Deterministic scorers working, baseline recorded above
- ⬜ LLM-judge and retrieval scorers written but **not yet executed** — they need
  a working judge model, and Ollama's CUDA fault makes judge runs impractically
  slow on CPU
- ⬜ RAG scorers therefore unvalidated: the RETRIEVER span is emitted and shaped
  correctly, but no run has yet scored against it
- ⬜ Not wired into CI — worth doing once the deterministic scorers are trusted,
  since they need no API key
