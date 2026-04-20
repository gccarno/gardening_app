# ML Service

Python package imported directly by the FastAPI backend at request time — no separate process or network call.

## Modules

| File | Purpose |
|---|---|
| `app/chat_tools.py` | 12 AI chat tools + `run_agentic_loop` (Anthropic + Ollama agentic loops) |
| `app/llm_provider.py` | Model-agnostic `complete()` dispatch (Anthropic / OpenAI / Ollama / HuggingFace) |
| `app/chat_logger.py` | Per-session structured JSON logging to `logs/chat/` |
| `app/recommender.py` | Rule-based + ML plant scorer; falls back to rules if `recommender.pkl` is missing |
| `app/watering_engine.py` | FAO-56 ET₀ deficit calculation + urgency scoring per bed |

## Chat Tools

The agentic loop supports full multi-round tool use with Ollama (OpenAI-compatible format) and Anthropic. Other providers fall back to single-turn completion.

12 tools are available to the assistant:

- **Read**: `get_garden_plan`, `check_companion_planting`, `check_planting_calendar`, `check_spacing_requirements`, `get_plant_care_info`, `list_upcoming_tasks`, `get_weather_forecast`, `get_watering_history`, `get_watering_recommendation`, `search_growing_guides`
- **Write**: `add_plant_to_garden`, `create_task`

## Configuration

Set via `.env`:

```env
LLM_PROVIDER=ollama          # anthropic | openai | ollama | huggingface
LLM_MODEL=gemma4:e2b         # provider default used if unset
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=sk-ant-... # if using Anthropic
```

## Tests

```bash
# Unit tests (mocked externals, in-memory SQLite)
uv run pytest tests/unit/test_chat_tools.py -v

# Integration tests (real Ollama model required)
uv run pytest tests/integration/ -v
```
