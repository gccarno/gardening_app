"""
Scorers for the chat agent.

Two families, deliberately separated:

* **Deterministic** (`tool_selection`, `no_unintended_writes`) read the MLflow
  trace directly. No LLM, no API key, no cost, no flake. These are the ones worth
  running on every prompt edit.
* **LLM judges** (`groundedness`, plus MLflow's built-in retrieval scorers) need a
  judge model. On this project that means Ollama, which is free but slower and
  less reliable than a hosted judge — see `docs/chat-eval.md`.

⚠ Judge instructions must ask for "yes"/"no". MLflow silently casts "pass"/"fail"
to None and drops the result from metrics with no warning.
"""
from mlflow.entities import SpanType
from mlflow.genai.scorers import scorer

from apps.ml_service.app.chat_tools import WRITE_TOOLS


def _tools_called(trace):
    """Tool names invoked in a trace, in call order.

    Every tool goes through chat_tools.execute_tool, which carries one TOOL span
    per call, so the tool name is the span's `name` input.
    """
    if trace is None:
        return []
    names = []
    for span in trace.search_spans(span_type=SpanType.TOOL):
        inputs = span.inputs or {}
        name = inputs.get('name')
        if name:
            names.append(name)
    return names


@scorer
def tool_selection(trace, expectations):
    """Did the agent call the tool(s) the question requires?

    Three independent expectations, because the first version of this scorer
    conflated them and scored the agent down for reasonable behaviour:

    * `expected_tools`  — ALL of these must be called.
    * `expected_any`    — at LEAST ONE of these must be called (for questions a
      couple of different tools could legitimately answer).
    * `forbid_tools`    — none of these may be called.

    Extra tool calls are otherwise fine: an agent gathering more context before
    answering is not making a mistake. Only `forbid_tools` makes a call wrong.
    """
    exp = expectations or {}
    required = set(exp.get('expected_tools') or [])
    any_of = set(exp.get('expected_any') or [])
    forbidden = set(exp.get('forbid_tools') or [])
    called = set(_tools_called(trace))

    if forbidden & called:
        return 'no'
    if required and not required <= called:
        return 'no'
    if any_of and not (any_of & called):
        return 'no'
    return 'yes'


@scorer
def no_unintended_writes(trace, expectations):
    """Did the agent avoid mutating the database when it shouldn't?

    The failure this guards against is the expensive one: a question phrased as
    an opinion ("should I plant cucumbers?") that the agent answers by silently
    writing a row into the user's real garden.
    """
    if not (expectations or {}).get('forbid_writes'):
        return 'yes'          # not a trap case — nothing to judge
    called = set(_tools_called(trace))
    return 'no' if called & WRITE_TOOLS else 'yes'


def build_judges(model):
    """LLM-judge scorers. Separate function so a run can skip them entirely.

    `model` is an MLflow model URI (e.g. 'openai:/gpt-4.1-mini'). MLflow's default
    judge requires OPENAI_API_KEY, which this project does not use, so the caller
    must pass one explicitly.
    """
    from mlflow.genai.judges import make_judge

    groundedness = make_judge(
        name='groundedness',
        instructions=(
            'You are checking a gardening assistant that has live access to the '
            "user's own garden data.\n\n"
            'Question: {{ inputs }}\n'
            'Assistant answer: {{ outputs }}\n'
            'What a correct answer should contain: {{ expectations }}\n\n'
            'Does the answer use the specific garden data (its plants, beds, zone, '
            'frost dates) rather than giving generic gardening advice that would '
            'apply to anyone? Answer "yes" or "no".'
        ),
        model=model,
    )

    no_hallucinated_data = make_judge(
        name='no_hallucinated_data',
        instructions=(
            'Question: {{ inputs }}\n'
            'Assistant answer: {{ outputs }}\n'
            'Expected content: {{ expectations }}\n\n'
            'Does the answer state specific facts about the garden (plant names, '
            'bed sizes, dates, watering history) that were NOT available to it? '
            'Inventing a forecast or a watering date it could not know is a '
            'hallucination. Answer "yes" if the answer is free of invented '
            'specifics, "no" if it invents any.'
        ),
        model=model,
    )

    return [groundedness, no_hallucinated_data]


def build_retrieval_scorers(model):
    """MLflow's built-in RAG scorers, per the eval skill's retrieval guidance.

    These only produce a score on traces containing a RETRIEVER span — that is
    the span added around `search_guides` in chat_tools._tool_search_growing_guides.
    Questions that never hit the guide corpus will show as None here, which is
    expected, not a failure.
    """
    from mlflow.genai.scorers import (
        RetrievalGroundedness, RetrievalRelevance, RetrievalSufficiency,
    )
    return [
        RetrievalGroundedness(model=model),   # is the answer supported by what was retrieved?
        RetrievalRelevance(model=model),      # were the retrieved chunks on-topic?
        RetrievalSufficiency(model=model),    # was enough retrieved to answer at all?
    ]
