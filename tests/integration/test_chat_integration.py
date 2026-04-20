"""
Integration tests for the agentic chat loop using the real local Ollama model.

These tests call run_agentic_loop() with the actual gemma4:e2b model and assert
that the model correctly invokes the expected tool for each prompt.

Run with:
    uv run pytest tests/integration/ -v

Skip condition: tests are skipped automatically if Ollama is not running.
Excluded from default test runs via: pytest -m "not integration"
"""
from dotenv import load_dotenv
load_dotenv()  # must happen before llm_provider is imported

import os

import pytest
import requests as _req

from apps.ml_service.app.chat_tools import run_agentic_loop
import apps.ml_service.app.chat_tools as _ct
import apps.ml_service.app.llm_provider as _llm

pytestmark = pytest.mark.integration

SYSTEM = (
    "You are a garden assistant. "
    "Use the available tools to look up real data before answering. "
    "Be brief."
)


def _ollama_running() -> bool:
    base = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    try:
        return _req.get(base, timeout=2).status_code == 200
    except Exception:
        return False


@pytest.fixture
def tool_calls(monkeypatch):
    """Ensure Ollama provider and record every execute_tool call."""
    if not _ollama_running():
        pytest.skip('Ollama not running at ' + os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'))
    monkeypatch.setattr(_llm, 'PROVIDER', 'ollama')
    called = []
    original = _ct.execute_tool

    def recording(name, input_data, garden, db):
        called.append(name)
        return original(name, input_data, garden, db)

    monkeypatch.setattr(_ct, 'execute_tool', recording)
    return called


def test_get_garden_plan(tool_calls, garden, plant_in_bed, db):
    messages = [{'role': 'user', 'content': 'What plants are currently in my garden?'}]
    reply = run_agentic_loop(SYSTEM, messages, garden, db, max_tool_rounds=2)
    assert 'get_garden_plan' in tool_calls
    assert reply


def test_companion_planting(tool_calls, garden, library_plant, db):
    messages = [{'role': 'user', 'content': 'Are tomatoes and basil good companion plants?'}]
    reply = run_agentic_loop(SYSTEM, messages, garden, db, max_tool_rounds=2)
    assert 'check_companion_planting' in tool_calls
    assert reply


def test_planting_calendar(tool_calls, garden, library_plant, db):
    messages = [{'role': 'user', 'content': 'When should I start tomatoes indoors?'}]
    reply = run_agentic_loop(SYSTEM, messages, garden, db, max_tool_rounds=2)
    assert 'check_planting_calendar' in tool_calls
    assert reply


def test_plant_care_info(tool_calls, garden, library_plant, db):
    messages = [{'role': 'user', 'content': 'What sunlight and water does a tomato need?'}]
    reply = run_agentic_loop(SYSTEM, messages, garden, db, max_tool_rounds=2)
    assert 'get_plant_care_info' in tool_calls
    assert reply


def test_list_upcoming_tasks(tool_calls, garden, upcoming_task, db):
    messages = [{'role': 'user', 'content': 'List my upcoming gardening tasks.'}]
    reply = run_agentic_loop(SYSTEM, messages, garden, db, max_tool_rounds=2)
    assert 'list_upcoming_tasks' in tool_calls
    assert reply


def test_create_task(tool_calls, garden, db):
    messages = [{'role': 'user', 'content': 'Add a watering task to my task list due tomorrow. Use the create_task tool.'}]
    reply = run_agentic_loop(SYSTEM, messages, garden, db, max_tool_rounds=2)
    assert 'create_task' in tool_calls
    assert reply
