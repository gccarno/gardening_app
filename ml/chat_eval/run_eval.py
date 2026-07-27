"""
Offline evaluation for the garden chat agent.

Runs the REAL agent (apps.ml_service.app.chat_tools.run_agentic_loop) against a
throwaway in-memory SQLite garden, traces every run with MLflow, and scores the
traces.

SAFETY: the agent can call add_plant_to_garden and create_task, which write. This
harness builds its own SQLite database and never touches DATABASE_URL, so an eval
run cannot mutate production Neon. Do not "simplify" this by reusing the app's
session.

Usage
-----
    uv pip install "mlflow>=3.8"
    ollama serve                                    # in another terminal

    uv run python -m ml.chat_eval.run_eval --dry-run          # 3 questions
    uv run python -m ml.chat_eval.run_eval                    # full set
    uv run python -m ml.chat_eval.run_eval --judge-model ollama:/llama3.1

    uv run mlflow ui --backend-store-uri sqlite:///mlflow.db             # inspect traces
"""
import argparse
import os
from datetime import date

# Must run before llm_provider is imported anywhere: that module reads
# LLM_PROVIDER / LLM_MODEL from os.environ at import time, so a late load leaves
# the eval silently testing the wrong provider.
from dotenv import load_dotenv

load_dotenv()

import mlflow  # noqa: E402
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.ml_service.app.tracing import setup
from ml.chat_eval.dataset import FIXTURE_SUMMARY, RECORDS
from ml.chat_eval.scorers import no_unintended_writes, tool_selection

EXPERIMENT = 'garden-chat-agent'


def build_fixture_db():
    """A disposable garden matching dataset.FIXTURE_SUMMARY.

    Mirrors the shape of tests/conftest.py's fixtures, but standalone: the eval
    must not depend on pytest being in the picture.
    """
    from apps.backend.app.db.models import (
        Base, BedPlant, Garden, GardenBed, Plant, PlantLibrary,
    )

    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    garden = Garden(
        name='Eval Garden', usda_zone='5b', last_frost_date=date(2026, 4, 15),
        latitude=41.8, longitude=-87.6, city='Chicago', state='IL',
    )
    db.add(garden)
    db.flush()

    bed = GardenBed(name='Raised Bed A', garden_id=garden.id,
                    width_ft=4.0, height_ft=8.0)
    db.add(bed)
    db.flush()

    lib = PlantLibrary(name='Tomato', type='vegetable', spacing_in=24,
                       sunlight='Full sun', water='Moderate',
                       days_to_germination=7, days_to_harvest=70)
    db.add(lib)
    db.flush()

    plant = Plant(name='Tomato', type='vegetable', garden_id=garden.id,
                  library_id=lib.id, planted_date=date(2026, 5, 1), status='growing')
    db.add(plant)
    db.flush()
    db.add(BedPlant(bed_id=bed.id, plant_id=plant.id))
    db.commit()
    db.refresh(garden)
    return db, garden


SYSTEM_PROMPT = (
    'You are a helpful gardening assistant for a specific garden. '
    f'Context: {FIXTURE_SUMMARY}. '
    'Use the provided tools to look up real data about this garden before '
    'answering. Only add plants or create tasks when the user explicitly asks '
    'you to. Keep responses under 200 words.'
)


def make_predict_fn(db, garden):
    """MLflow calls predict_fn(**inputs), so the parameter name must match the
    dataset's input key exactly ('question')."""
    from apps.ml_service.app.chat_tools import run_agentic_loop

    def predict(question: str) -> str:
        messages = [{'role': 'user', 'content': question}]
        try:
            return run_agentic_loop(SYSTEM_PROMPT, messages, garden, db)
        except Exception as exc:
            # A crash must not abort the whole run — record it as the answer so
            # the scorers mark it failed and the rest of the set still executes.
            return f'[agent error] {type(exc).__name__}: {exc}'

    return predict


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                    help='Run only the first 3 questions (the skill\'s Step 3.5 gate)')
    ap.add_argument('--judge-model', default=None,
                    help='MLflow model URI for LLM judges, e.g. ollama:/llama3.1. '
                         'Omitted = deterministic scorers only (free, no API calls).')
    ap.add_argument('--retrieval-scorers', action='store_true',
                    help='Add MLflow built-in RAG scorers (requires --judge-model)')
    args = ap.parse_args()

    uri, name = setup(EXPERIMENT)
    print(f'MLflow tracking : {uri}\nExperiment      : {name}')

    provider = os.environ.get('LLM_PROVIDER', 'anthropic')
    model = os.environ.get('LLM_MODEL', '(provider default)')
    print(f'Agent under test: provider={provider} model={model}')

    if provider == 'anthropic':
        # Only the Anthropic path goes through an SDK MLflow can autolog; the
        # Ollama path is instrumented by hand in chat_tools.
        mlflow.anthropic.autolog()

    records = RECORDS[:3] if args.dry_run else RECORDS
    data = [
        {
            'inputs': {'question': r['question']},
            'expectations': {
                'expected_tools': r.get('expected_tools', []),
                'forbid_writes': r.get('forbid_writes', False),
                'expectations': r.get('expectations', ''),
            },
        }
        for r in records
    ]

    scorers = [tool_selection, no_unintended_writes]
    if args.judge_model:
        from ml.chat_eval.scorers import build_judges
        scorers += build_judges(args.judge_model)
        if args.retrieval_scorers:
            from ml.chat_eval.scorers import build_retrieval_scorers
            scorers += build_retrieval_scorers(args.judge_model)
    print(f'Scorers         : {[getattr(s, "name", type(s).__name__) for s in scorers]}')
    print(f'Questions       : {len(data)}\n')

    db, garden = build_fixture_db()
    try:
        results = mlflow.genai.evaluate(
            data=data,
            predict_fn=make_predict_fn(db, garden),
            scorers=scorers,
        )
    finally:
        db.close()

    # ASCII only: the Windows console is cp1252 and box-drawing characters
    # raise UnicodeEncodeError at print time.
    print('\n-- Metrics --')
    for k, v in (results.metrics or {}).items():
        print(f'  {k}: {v}')
    print(f'\nInspect traces: uv run mlflow ui --backend-store-uri {uri}')
    return results


if __name__ == '__main__':
    main()
