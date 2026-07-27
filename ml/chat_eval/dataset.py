"""
Seed records for the chat-agent evaluation dataset.

These are the source of truth for the questions; `run_eval.py` feeds them to
`mlflow.genai.datasets.create_dataset()`, which is what actually stores and
versions the dataset. Do not build a bespoke runner around this list — the whole
point is that MLflow owns the dataset, scorers, traces and results together.

Three independent expectations drive the tool-selection scorer. All tool names
must exist in chat_tools.TOOL_SCHEMAS:

* `expected_tools` — ALL of these must be called.
* `expected_any`   — at LEAST ONE must be called, for questions that two tools
  could each legitimately answer.
* `forbid_tools`   — none of these may be called.

Extra tool calls are NOT failures. The first version of this file expressed
"either tool is fine" as a plain list, which the scorer read as "both required",
and marked reasonable context-gathering as wrong. If a question has no hard
requirement, give it only `forbid_tools` and let the answer-quality judges
handle the rest.

`forbid_writes=True` marks the trap cases: questions phrased near a mutation
("should I plant X?") where calling add_plant_to_garden / create_task would
silently corrupt the user's garden. These are the highest-value cases in the set.
"""

# The fixture garden every question is asked against (see run_eval.build_fixture_db):
#   Zone 5b, Chicago IL, last frost 2026-04-15
#   Bed "Raised Bed A" 4x8 ft, containing one Tomato
FIXTURE_SUMMARY = 'Zone 5b garden in Chicago IL, one 4x8 bed with a tomato'

RECORDS = [
    # ── Garden-state questions: must read real data, not generalise ──────────
    {
        'question': "What's currently planted in my garden?",
        'expected_tools': ['get_garden_plan'],
        'expectations': 'Names the tomato and the bed "Raised Bed A" from the garden data.',
    },
    {
        'question': 'How many beds do I have and how big are they?',
        'expected_tools': ['get_garden_plan'],
        'expectations': 'States one bed, 4x8 ft. Does not invent additional beds.',
    },
    {
        'question': 'Do I have room in my beds for four more tomato plants?',
        'expected_tools': ['check_spacing_requirements'],
        'expectations': 'Reasons about the 4x8 bed and tomato spacing (~24in).',
        'forbid_writes': True,
    },

    # ── Timing / frost: the classic wrong-tool case ──────────────────────────
    {
        'question': 'When is my last frost date?',
        'expected_tools': ['check_planting_calendar'],
        'expectations': 'Gives a spring frost date consistent with zone 5b, not a generic answer.',
    },
    {
        'question': 'Is it too late to start peppers from seed this year?',
        'expected_tools': ['check_planting_calendar'],
        'expectations': 'References frost timing and days-to-harvest rather than guessing.',
    },
    {
        'question': 'When should I direct sow carrots here?',
        'expected_tools': ['check_planting_calendar'],
        'expectations': 'Ties the answer to the local frost date.',
    },

    # ── Companion planting ──────────────────────────────────────────────────
    {
        'question': 'Can I plant basil next to my tomato?',
        'expected_tools': ['check_companion_planting'],
        'expectations': 'Says the pairing is good, referencing companion data.',
        'forbid_writes': True,
    },
    {
        'question': 'Is fennel a bad neighbour for what I am already growing?',
        'expected_tools': ['check_companion_planting'],
        'expectations': 'Identifies fennel as a poor companion for tomato.',
    },

    # ── Care info ───────────────────────────────────────────────────────────
    {
        'question': 'How much sun do tomatoes need?',
        'expected_tools': ['get_plant_care_info'],
        'expectations': 'Full sun / ~6-8 hours.',
    },
    {
        'question': 'How deep should I plant tomato seedlings?',
        'expected_any': ['get_plant_care_info', 'search_growing_guides'],
        'expectations': 'Practical planting-depth guidance.',
    },

    # ── Weather / watering ──────────────────────────────────────────────────
    {
        'question': 'Do I need to water today?',
        'expected_tools': ['get_watering_recommendation'],
        'expectations': 'Gives a yes/no grounded in watering status, not generic advice.',
    },
    {
        'question': "What's the weather forecast for my garden?",
        'expected_tools': ['get_weather_forecast'],
        'expectations': 'Reports forecast data or says it is unavailable — never invents one.',
    },
    {
        'question': 'When did I last water?',
        'expected_tools': ['get_watering_history'],
        'expectations': 'Reads watering history; says none recorded if empty.',
    },

    # ── Tasks ───────────────────────────────────────────────────────────────
    {
        'question': "What's on my task list for the next couple of weeks?",
        'expected_tools': ['list_upcoming_tasks'],
        'expectations': 'Lists upcoming tasks, or says there are none.',
    },
    {
        'question': 'Remind me to fertilise the tomatoes next Saturday.',
        'expected_tools': ['create_task'],
        'expectations': 'Creates the task and confirms it. This one SHOULD write.',
    },

    # ── RAG: questions only the growing-guide corpus can answer ─────────────
    {
        'question': 'What do my growing guides say about preventing blossom end rot?',
        'expected_tools': ['search_growing_guides'],
        'expectations': 'Cites guide content about calcium/watering consistency.',
    },
    {
        'question': 'Look up what the guides recommend for improving heavy clay soil.',
        'expected_tools': ['search_growing_guides'],
        'expectations': 'Returns retrieved guide passages rather than generic advice.',
    },

    # ── Write traps: phrased near a mutation, must NOT write ────────────────
    {
        'question': 'Should I add cucumbers to my garden this year?',
        'forbid_tools': ['add_plant_to_garden'],
        'expectations': 'Gives advice. Must NOT call add_plant_to_garden — the user '
                        'asked for an opinion, not an action.',
        'forbid_writes': True,
    },
    {
        'question': 'I am thinking about planting garlic in the fall, what do you think?',
        'forbid_tools': ['add_plant_to_garden'],
        'expectations': 'Discusses fall garlic. Must NOT write anything.',
        'forbid_writes': True,
    },

    # ── Out of scope: should decline rather than hallucinate a tool ─────────
    {
        'question': 'What is the capital of France?',
        'forbid_tools': ['search_growing_guides', 'add_plant_to_garden', 'create_task'],
        'expectations': 'Answers briefly or redirects to gardening. Calls no tools.',
        'forbid_writes': True,
    },
]
