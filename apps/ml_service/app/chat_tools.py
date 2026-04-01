"""
Tool schemas and agentic loop for the Garden AI Chat.

All tool implementations run inside a Flask app context and query SQLAlchemy
models directly -- no HTTP round-trips to other routes.
"""

import json
import os
from datetime import date, timedelta, datetime

CHAT_MODEL = os.environ.get('CHAT_MODEL', 'claude-sonnet-4-6')

# Frost dates (duplicated from main.py to avoid circular imports)
_FROST_DATES = {
    '1':  ('Jun 15', 'Aug 15'), '2':  ('Jun 1',  'Sep 1'),
    '3':  ('May 15', 'Sep 15'), '4':  ('May 1',  'Oct 1'),
    '5':  ('Apr 15', 'Oct 15'), '6':  ('Apr 1',  'Oct 31'),
    '7':  ('Mar 15', 'Nov 15'), '8':  ('Feb 15', 'Dec 1'),
    '9':  ('Jan 31', 'Dec 15'), '10': ('rare',   'rare'),
    '11': ('none',   'none'),   '12': ('none',   'none'),
    '13': ('none',   'none'),
}

# ── Tool schemas ──────────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        'name': 'get_garden_plan',
        'description': (
            'Get the current garden layout: name, zone, beds, and the plants in each bed. '
            'Call this first to understand what the gardener is working with.'
        ),
        'input_schema': {'type': 'object', 'properties': {}, 'required': []},
    },
    {
        'name': 'check_companion_planting',
        'description': (
            'Check which plants are good or bad companions for a given plant, '
            'or check if two specific plants are compatible with each other.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'plant_name': {
                    'type': 'string',
                    'description': 'Name of the plant to check companions for (e.g. "Tomato")',
                },
                'companion_name': {
                    'type': 'string',
                    'description': 'Optional: second plant name to check pairwise compatibility',
                },
            },
            'required': ['plant_name'],
        },
    },
    {
        'name': 'check_planting_calendar',
        'description': (
            'Check when a plant should be started indoors, transplanted, or direct-sown, '
            'based on the garden zone and last frost date.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'plant_name': {
                    'type': 'string',
                    'description': 'Name of the plant (e.g. "Tomato", "Basil")',
                },
            },
            'required': ['plant_name'],
        },
    },
    {
        'name': 'check_spacing_requirements',
        'description': (
            'Return recommended spacing in inches for a plant, '
            'and optionally estimate how many plants fit in a specific bed.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'plant_name': {'type': 'string', 'description': 'Name of the plant'},
                'bed_name': {
                    'type': 'string',
                    'description': 'Optional: bed name to estimate capacity for',
                },
            },
            'required': ['plant_name'],
        },
    },
    {
        'name': 'get_plant_care_info',
        'description': (
            'Get detailed care info for a plant: sunlight, water, difficulty, '
            'soil pH, days to harvest, and growing tips.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'plant_name': {'type': 'string', 'description': 'Name of the plant'},
            },
            'required': ['plant_name'],
        },
    },
    {
        'name': 'add_plant_to_garden',
        'description': (
            'Add a plant to the gardener\'s garden. Creates a Plant record and '
            'optionally assigns it to a specific bed.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'plant_name': {'type': 'string', 'description': 'Name of the plant to add'},
                'bed_name': {
                    'type': 'string',
                    'description': 'Optional: name of the bed to add the plant to',
                },
                'notes': {'type': 'string', 'description': 'Optional notes about this planting'},
            },
            'required': ['plant_name'],
        },
    },
    {
        'name': 'create_task',
        'description': (
            'Create a gardening task such as watering, fertilizing, seeding, or harvesting. '
            'Dates are auto-calculated from frost dates when not specified.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'task_type': {
                    'type': 'string',
                    'description': 'Type of task',
                    'enum': [
                        'seeding', 'transplanting', 'watering', 'fertilizing',
                        'mulching', 'harvest', 'weeding', 'other',
                    ],
                },
                'plant_name': {
                    'type': 'string',
                    'description': 'Optional: name of the garden plant this task is for',
                },
                'due_date': {
                    'type': 'string',
                    'description': 'Optional: due date YYYY-MM-DD. Auto-calculated if omitted.',
                },
                'title': {
                    'type': 'string',
                    'description': 'Optional: custom task title (auto-generated if omitted)',
                },
                'description': {
                    'type': 'string',
                    'description': 'Optional: additional notes for the task',
                },
            },
            'required': ['task_type'],
        },
    },
    {
        'name': 'list_upcoming_tasks',
        'description': 'List upcoming incomplete tasks for the garden in the next N days.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'days': {
                    'type': 'integer',
                    'description': 'Number of days ahead to look (default 14)',
                },
            },
            'required': [],
        },
    },
    {
        'name': 'get_weather_forecast',
        'description': (
            'Get the 7-day weather forecast for the garden location, including daily '
            'temperature, precipitation probability, expected rain (mm), wind speed, '
            'and ET0 (reference evapotranspiration). Use before making watering recommendations.'
        ),
        'input_schema': {'type': 'object', 'properties': {}, 'required': []},
    },
    {
        'name': 'get_watering_history',
        'description': (
            'Get recent rainfall logs and the last watering date for each bed. '
            'Use alongside get_weather_forecast to reason about watering needs.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'days_back': {
                    'type': 'integer',
                    'description': 'How many days of history to return (default 14)',
                },
            },
            'required': [],
        },
    },
    {
        'name': 'get_watering_recommendation',
        'description': (
            'Calculate per-bed watering urgency scores and recommendations based on '
            'soil moisture deficit, recent rainfall, and today\'s forecast. '
            'Use when the user asks whether they need to water or wants a watering schedule.'
        ),
        'input_schema': {'type': 'object', 'properties': {}, 'required': []},
    },
    {
        'name': 'search_growing_guides',
        'description': (
            'Search authoritative gardening guides and books for detailed plant care information. '
            'Sources include Texas A&M University vegetable guides and Black & Decker regional '
            'gardening books. Use for questions about pests, diseases, fertilizing, planting '
            'techniques, soil prep, or any topic not covered by other tools.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Search query (e.g. "tomato blossom end rot", "pepper fertilizer schedule")',
                },
                'plant_name': {
                    'type': 'string',
                    'description': 'Optional: plant name to filter results (e.g. "Tomato")',
                },
            },
            'required': ['query'],
        },
    },
]

# Ollama / OpenAI-style tool schemas (converted from TOOL_SCHEMAS at import time)
# Ollama 0.3+ accepts `tools` in this format for models that support tool calling (llama3.1+).
_OLLAMA_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name':        t['name'],
            'description': t['description'],
            'parameters':  t['input_schema'],
        },
    }
    for t in TOOL_SCHEMAS
]


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_models():
    """Lazily import SQLAlchemy models (requires active Flask app context)."""
    from apps.api.app.db.models import (
        Garden, GardenBed, Plant, BedPlant, PlantLibrary, Task, db,
    )
    return Garden, GardenBed, Plant, BedPlant, PlantLibrary, Task, db


def _find_library_plant(name: str):
    """Case-insensitive search in PlantLibrary. Returns first match or None."""
    _, _, _, _, PlantLibrary, _, _ = _get_models()
    entry = PlantLibrary.query.filter(PlantLibrary.name.ilike(name)).first()
    if entry:
        return entry
    return PlantLibrary.query.filter(PlantLibrary.name.ilike(f'%{name}%')).first()


def _find_garden_plant(name: str, garden):
    """Find a Plant record in the garden by name (case-insensitive)."""
    if not garden:
        return None
    for p in garden.plants:
        if p.name.lower() == name.lower():
            return p
    return None


def _find_bed(name: str, garden):
    """Find a GardenBed by name in the garden (case-insensitive)."""
    if not garden:
        return None
    for b in garden.beds:
        if b.name.lower() == name.lower():
            return b
    return None


def _get_frost_date(garden):
    """Return last spring frost date as a date object, or None."""
    if garden and garden.last_frost_date:
        return garden.last_frost_date
    if garden and garden.usda_zone:
        zone_num = ''.join(filter(str.isdigit, garden.usda_zone or ''))
        spring_str, _ = _FROST_DATES.get(zone_num, (None, None))
        if spring_str and spring_str not in ('none', 'rare', 'unknown'):
            try:
                return datetime.strptime(
                    f'{spring_str} {date.today().year}', '%b %d %Y'
                ).date()
            except ValueError:
                pass
    return None


# ── Tool implementations ──────────────────────────────────────────────────────

def _tool_get_garden_plan(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected. Please select a garden first.'}
    beds = []
    for bed in garden.beds:
        plants_in_bed = []
        for bp in bed.bed_plants:
            p = bp.plant
            if p:
                plants_in_bed.append({
                    'name': p.name,
                    'status': p.status,
                    'type': p.type,
                })
        beds.append({
            'name': bed.name,
            'size': f'{bed.width_ft}ft x {bed.height_ft}ft',
            'plants': plants_in_bed,
        })
    return {
        'garden': garden.name,
        'zone': garden.usda_zone or 'unknown',
        'last_frost': garden.last_frost_date.isoformat() if garden.last_frost_date else None,
        'beds': beds,
        'total_plants': sum(len(b['plants']) for b in beds),
    }


def _tool_check_companion_planting(input_data: dict, garden) -> dict:
    plant_name = input_data.get('plant_name', '')
    companion_name = input_data.get('companion_name')

    entry = _find_library_plant(plant_name)
    if not entry:
        return {'error': f'Plant "{plant_name}" not found in the library.'}

    good, bad = [], []
    for field, lst in ((entry.good_neighbors, good), (entry.bad_neighbors, bad)):
        if field:
            try:
                raw = json.loads(field)
                lst.extend(raw[:15] if isinstance(raw, list) else [])
            except (json.JSONDecodeError, TypeError):
                pass

    result = {
        'plant': entry.name,
        'good_companions': good,
        'bad_companions': bad,
    }

    if companion_name:
        comp_lower = companion_name.lower()
        compatible   = any(comp_lower in str(g).lower() for g in good)
        incompatible = any(comp_lower in str(b).lower() for b in bad)
        if compatible:
            result['pairwise'] = f'{entry.name} and {companion_name} are GOOD companions.'
        elif incompatible:
            result['pairwise'] = (
                f'{entry.name} and {companion_name} are BAD companions — avoid planting together.'
            )
        else:
            result['pairwise'] = (
                f'No specific companion data for {entry.name} + {companion_name}.'
            )

    return result


def _tool_check_planting_calendar(input_data: dict, garden) -> dict:
    plant_name = input_data.get('plant_name', '')
    entry = _find_library_plant(plant_name)
    if not entry:
        return {'error': f'Plant "{plant_name}" not found in the library.'}

    frost = _get_frost_date(garden)
    today = date.today()
    zone  = (garden.usda_zone or 'unknown') if garden else 'unknown'

    result = {
        'plant': entry.name,
        'zone': zone,
        'today': today.isoformat(),
        'last_spring_frost': frost.isoformat() if frost else 'unknown',
    }

    if frost:
        if entry.sow_indoor_weeks:
            d = frost - timedelta(weeks=entry.sow_indoor_weeks)
            result['start_indoors'] = d.isoformat()
            result['start_indoors_note'] = (
                f'{entry.sow_indoor_weeks} weeks before last frost (~{d.strftime("%b %d")})'
            )
        if entry.transplant_offset is not None:
            d = frost + timedelta(weeks=entry.transplant_offset)
            result['transplant'] = d.isoformat()
            result['transplant_note'] = (
                f'{abs(entry.transplant_offset)} weeks '
                f'{"after" if entry.transplant_offset >= 0 else "before"} last frost '
                f'(~{d.strftime("%b %d")})'
            )
        if entry.direct_sow_offset is not None:
            d = frost + timedelta(weeks=entry.direct_sow_offset)
            result['direct_sow'] = d.isoformat()
            result['direct_sow_note'] = (
                f'{abs(entry.direct_sow_offset)} weeks '
                f'{"after" if entry.direct_sow_offset >= 0 else "before"} last frost '
                f'(~{d.strftime("%b %d")})'
            )

    if entry.days_to_harvest:
        result['days_to_harvest'] = entry.days_to_harvest

    has_timing = any(k in result for k in ('start_indoors', 'transplant', 'direct_sow'))
    if not has_timing:
        result['note'] = (
            'No planting timing data is available for this plant in the database. '
            'Use general knowledge to advise based on plant type and zone.'
        )

    return result


def _tool_check_spacing_requirements(input_data: dict, garden) -> dict:
    plant_name = input_data.get('plant_name', '')
    bed_name   = input_data.get('bed_name')

    entry = _find_library_plant(plant_name)
    if not entry:
        return {'error': f'Plant "{plant_name}" not found in the library.'}

    result = {
        'plant': entry.name,
        'spacing_in': entry.spacing_in,
        'row_spacing_cm': entry.row_spacing_cm,
    }
    if entry.spacing_in:
        result['note'] = (
            f'Plant {entry.name} {entry.spacing_in}" apart '
            f'(~{entry.spacing_in / 12:.1f} ft).'
        )

    if bed_name and garden:
        bed = _find_bed(bed_name, garden)
        if bed:
            result['bed'] = {
                'name': bed.name,
                'size': f'{bed.width_ft}ft x {bed.height_ft}ft',
                'area_sqft': round(bed.width_ft * bed.height_ft, 1),
            }
            if entry.spacing_in:
                s = entry.spacing_in / 12.0
                capacity = max(int((bed.width_ft / s) * (bed.height_ft / s)), 1)
                result['bed']['estimated_capacity'] = capacity
        else:
            result['bed_error'] = f'Bed "{bed_name}" not found in this garden.'

    return result


def _tool_get_plant_care_info(input_data: dict, garden) -> dict:
    plant_name = input_data.get('plant_name', '')
    entry = _find_library_plant(plant_name)
    if not entry:
        return {'error': f'Plant "{plant_name}" not found in the library.'}

    result = {
        'plant': entry.name,
        'scientific_name': entry.scientific_name,
        'type': entry.type,
        'sunlight': entry.sunlight,
        'water': entry.water,
        'difficulty': entry.difficulty,
        'days_to_germination': entry.days_to_germination,
        'days_to_harvest': entry.days_to_harvest,
        'soil_ph_range': (
            f'{entry.soil_ph_min}–{entry.soil_ph_max}'
            if entry.soil_ph_min and entry.soil_ph_max else None
        ),
        'hardiness_zones': (
            f'{entry.min_zone}–{entry.max_zone}'
            if entry.min_zone and entry.max_zone else None
        ),
        'notes': (entry.notes or '')[:300] or None,
    }

    if entry.how_to_grow:
        try:
            htg = json.loads(entry.how_to_grow)
            if isinstance(htg, dict) and 'starting' in htg:
                result['getting_started'] = htg['starting'][:200]
        except (json.JSONDecodeError, TypeError):
            pass

    return {k: v for k, v in result.items() if v is not None}


def _tool_add_plant_to_garden(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected. Please select a garden first.'}

    _, _, Plant, BedPlant, _, _, db = _get_models()

    plant_name = input_data.get('plant_name', '')
    bed_name   = input_data.get('bed_name')
    notes      = input_data.get('notes')

    lib = _find_library_plant(plant_name)

    plant = Plant(
        name=lib.name if lib else plant_name,
        type=lib.type if lib else None,
        library_id=lib.id if lib else None,
        garden_id=garden.id,
        planted_date=date.today(),
        notes=notes,
        status='growing',
    )
    db.session.add(plant)
    db.session.flush()

    result = {'added': plant.name, 'garden': garden.name, 'plant_id': plant.id}

    if bed_name:
        bed = _find_bed(bed_name, garden)
        if bed:
            db.session.add(BedPlant(bed_id=bed.id, plant_id=plant.id))
            result['bed'] = bed.name
        else:
            result['bed_warning'] = (
                f'Bed "{bed_name}" not found; plant added to garden without a bed.'
            )

    db.session.commit()
    return result


def _tool_create_task(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected. Please select a garden first.'}

    _, _, _, _, _, Task, db = _get_models()

    task_type    = input_data.get('task_type', 'other')
    plant_name   = input_data.get('plant_name')
    due_date_str = input_data.get('due_date')
    title        = input_data.get('title')
    description  = input_data.get('description')

    plant = _find_garden_plant(plant_name, garden) if plant_name else None
    lib   = plant.library_entry if plant else None
    frost = _get_frost_date(garden)
    due_date = None

    if task_type == 'seeding' and lib and lib.sow_indoor_weeks and frost:
        due_date = frost - timedelta(weeks=lib.sow_indoor_weeks)
    elif task_type == 'transplanting' and lib and lib.transplant_offset is not None and frost:
        due_date = frost + timedelta(weeks=lib.transplant_offset)
    elif task_type == 'harvest':
        if plant and plant.planted_date and lib and lib.days_to_harvest:
            due_date = plant.planted_date + timedelta(days=lib.days_to_harvest)
        elif plant and plant.expected_harvest:
            due_date = plant.expected_harvest
    elif task_type == 'watering':
        due_date = date.today()

    if due_date_str:
        try:
            due_date = date.fromisoformat(due_date_str)
        except ValueError:
            pass

    if not title:
        label = plant.name if plant else (plant_name or '')
        title = {
            'seeding':       f'Seed {label}'.strip(),
            'transplanting': f'Transplant {label}'.strip(),
            'harvest':       f'Harvest {label}'.strip(),
            'watering':      f'Water {label or garden.name}'.strip(),
            'fertilizing':   f'Fertilize {label or garden.name}'.strip(),
            'mulching':      f'Mulch {label or garden.name}'.strip(),
            'weeding':       f'Weed {garden.name}',
        }.get(task_type, f'Task: {label or garden.name}'.strip())

    task = Task(
        title=title,
        description=description,
        task_type=task_type,
        due_date=due_date,
        plant_id=plant.id if plant else None,
        garden_id=garden.id,
    )
    db.session.add(task)
    db.session.commit()

    return {
        'created': task.title,
        'task_id': task.id,
        'due_date': due_date.isoformat() if due_date else None,
        'task_type': task_type,
    }


def _tool_list_upcoming_tasks(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected.'}

    _, _, _, _, _, Task, _ = _get_models()

    days   = int(input_data.get('days') or 14)
    today  = date.today()
    cutoff = today + timedelta(days=days)

    tasks = (
        Task.query
        .filter_by(garden_id=garden.id, completed=False)
        .filter(Task.due_date != None)  # noqa: E711
        .filter(Task.due_date <= cutoff)
        .order_by(Task.due_date)
        .limit(20)
        .all()
    )

    return {
        'tasks': [
            {
                'title':     t.title,
                'task_type': t.task_type,
                'due_date':  t.due_date.isoformat() if t.due_date else None,
                'plant':     t.plant.name if t.plant else None,
            }
            for t in tasks
        ],
        'count':  len(tasks),
        'window': f'Next {days} days',
    }


def _tool_get_weather_forecast(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected.'}
    if not garden.latitude or not garden.longitude:
        return {'error': 'Garden has no location set. Add a zip code or coordinates first.'}
    from apps.ml_service.app.watering_engine import fetch_7day_forecast
    forecast = fetch_7day_forecast(garden.latitude, garden.longitude)
    if forecast is None:
        return {'error': 'Could not fetch forecast. Check your internet connection.'}
    return {
        'garden': garden.name,
        'location': f'{garden.city}, {garden.state}' if garden.city else 'see garden settings',
        'forecast': forecast,
    }


def _tool_get_watering_history(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected.'}

    _, _, _, _, _, _, _ = _get_models()  # ensure models importable
    from apps.api.app.db.models import WeatherLog

    days_back = int(input_data.get('days_back') or 14)
    cutoff    = date.today() - timedelta(days=days_back)

    logs = (WeatherLog.query
            .filter_by(garden_id=garden.id)
            .filter(WeatherLog.date >= cutoff)
            .order_by(WeatherLog.date.desc())
            .all())

    rainfall_events = [
        {
            'date':        lg.date.isoformat(),
            'rainfall_in': lg.rainfall_in,
            'rainfall_mm': round((lg.rainfall_in or 0) * 25.4, 1),
        }
        for lg in logs if (lg.rainfall_in or 0) > 0
    ]

    # Per-bed last watered
    bed_status = []
    for bed in garden.beds:
        most_recent = None
        for bp in bed.bed_plants:
            if bp.last_watered:
                if most_recent is None or bp.last_watered > most_recent:
                    most_recent = bp.last_watered
        dsw = (date.today() - most_recent).days if most_recent else None
        bed_status.append({
            'bed':                 bed.name,
            'last_watered':        most_recent.isoformat() if most_recent else 'never',
            'days_since_watered':  dsw,
        })

    total_rain_mm = round(sum(lg.rainfall_in or 0 for lg in logs) * 25.4, 1)

    return {
        'rainfall_events':  rainfall_events,
        'total_rain_mm':    total_rain_mm,
        'period_days':      days_back,
        'has_weather_data': len(logs) > 0,
        'bed_watering_status': bed_status,
    }


def _tool_get_watering_recommendation(input_data: dict, garden) -> dict:
    if not garden:
        return {'error': 'No garden selected.'}

    from apps.api.app.db.models import WeatherLog
    from apps.ml_service.app.watering_engine import (
        fetch_forecast_today, get_watering_recommendations,
    )

    cutoff = date.today() - timedelta(days=14)
    weather_logs = (WeatherLog.query
                    .filter_by(garden_id=garden.id)
                    .filter(WeatherLog.date >= cutoff)
                    .all())

    forecast_today = None
    if garden.latitude and garden.longitude:
        forecast_today = fetch_forecast_today(garden.latitude, garden.longitude)

    beds = get_watering_recommendations(garden, weather_logs, forecast_today)

    if not beds:
        return {
            'message': 'No beds with plants found in this garden.',
            'beds': [],
        }

    urgent = [b for b in beds if b['label'] in ('urgent', 'water_today')]
    ok     = [b for b in beds if b['label'] == 'ok']

    summary = (
        f'{len(urgent)} bed(s) need watering today, {len(ok)} bed(s) are fine.'
        if urgent else
        'All beds have adequate moisture.'
    )

    return {
        'summary':        summary,
        'forecast_today': forecast_today,
        'beds':           beds,
        'weather_data_available': len(weather_logs) > 0,
        'tip': (
            'Run "Fetch Weather History" from the garden detail page to improve '
            'accuracy with recent rainfall data.'
            if not weather_logs else None
        ),
    }


def _tool_search_growing_guides(input_data: dict, garden) -> dict:
    """Search the RAG database of gardening guides and books."""
    import sys
    import os

    # Add scripts directory to path so we can import build_rag.search_guides
    _scripts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'scripts',
    )
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)

    query      = input_data.get('query', '')
    plant_name = input_data.get('plant_name', '')

    if not query:
        return {'error': 'query is required'}

    try:
        from build_rag import search_guides
    except ImportError:
        return {
            'error': 'RAG database not built yet. Run: python scripts/build_rag.py',
            'results': [],
        }

    # Optionally filter by the garden's region
    region_filter = None
    if garden and hasattr(garden, 'state') and garden.state:
        # Rough state → region mapping for B&D books
        _STATE_REGION = {
            'TX': 'Lower South', 'OK': 'Lower South', 'LA': 'Lower South',
            'MS': 'Lower South', 'AL': 'Lower South', 'GA': 'Lower South',
            'FL': 'Lower South', 'AR': 'Lower South',
            'ME': 'Northeast', 'NH': 'Northeast', 'VT': 'Northeast',
            'MA': 'Northeast', 'RI': 'Northeast', 'CT': 'Northeast',
            'NY': 'Northeast', 'PA': 'Northeast', 'NJ': 'Northeast',
            'MD': 'Mid-Atlantic', 'DE': 'Mid-Atlantic', 'VA': 'Mid-Atlantic',
            'WV': 'Mid-Atlantic', 'NC': 'Mid-Atlantic',
            'WA': 'Northwest', 'OR': 'Northwest', 'ID': 'Northwest',
            'MN': 'Upper Midwest', 'WI': 'Upper Midwest', 'MI': 'Upper Midwest',
            'IA': 'Upper Midwest', 'ND': 'Upper Midwest', 'SD': 'Upper Midwest',
            'OH': 'Lower Midwest', 'IN': 'Lower Midwest', 'IL': 'Lower Midwest',
            'MO': 'Lower Midwest', 'KY': 'Lower Midwest', 'TN': 'Lower Midwest',
            'KS': 'Western Plains', 'NE': 'Western Plains', 'CO': 'Western Plains',
            'WY': 'Western Plains', 'MT': 'Western Plains',
        }
        region_filter = _STATE_REGION.get(garden.state.upper()[:2])

    results = search_guides(query, plant_name=plant_name or None, n_results=3,
                            region_filter=region_filter)

    if not results:
        return {
            'message': (
                'No results found in growing guides. '
                'Run python scripts/build_rag.py to build the index if not done yet.'
            ),
            'results': [],
        }

    return {
        'query':   query,
        'results': [
            {
                'source':  r['source'],
                'region':  r['region'],
                'passage': r['text'][:800],   # trim to keep context manageable
                'score':   r['score'],
            }
            for r in results
        ],
    }


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def execute_tool(name: str, input_data: dict, garden) -> dict:
    """Route a tool call to its implementation. Returns a result dict."""
    handlers = {
        'get_garden_plan':            lambda: _tool_get_garden_plan(input_data, garden),
        'check_companion_planting':   lambda: _tool_check_companion_planting(input_data, garden),
        'check_planting_calendar':    lambda: _tool_check_planting_calendar(input_data, garden),
        'check_spacing_requirements': lambda: _tool_check_spacing_requirements(input_data, garden),
        'get_plant_care_info':        lambda: _tool_get_plant_care_info(input_data, garden),
        'add_plant_to_garden':        lambda: _tool_add_plant_to_garden(input_data, garden),
        'create_task':                lambda: _tool_create_task(input_data, garden),
        'list_upcoming_tasks':        lambda: _tool_list_upcoming_tasks(input_data, garden),
        'get_weather_forecast':          lambda: _tool_get_weather_forecast(input_data, garden),
        'get_watering_history':          lambda: _tool_get_watering_history(input_data, garden),
        'get_watering_recommendation':   lambda: _tool_get_watering_recommendation(input_data, garden),
        'search_growing_guides':         lambda: _tool_search_growing_guides(input_data, garden),
    }
    handler = handlers.get(name)
    if handler is None:
        return {'error': f'Unknown tool: {name}'}
    try:
        return handler()
    except Exception as exc:
        return {'error': f'Tool {name} failed: {exc}'}


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _run_ollama_loop(system: str, messages: list, garden, max_rounds: int = 5) -> str:
    """
    Agentic loop for Ollama (llama3.1+) using the OpenAI-compatible tool-calling API.
    Passes the full conversation history and supports multi-round tool use.
    """
    import requests
    base  = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    model = os.environ.get('LLM_MODEL') or 'llama3.1'

    working = [{'role': 'system', 'content': system}] + list(messages)

    for _ in range(max_rounds):
        resp = requests.post(
            f'{base}/api/chat',
            json={
                'model':    model,
                'messages': working,
                'tools':    _OLLAMA_TOOL_SCHEMAS,
                'stream':   False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        msg = resp.json()['message']   # {'role': 'assistant', 'content': ..., 'tool_calls': [...]}
        working.append(msg)

        tool_calls = msg.get('tool_calls') or []
        if not tool_calls:
            return (msg.get('content') or '').strip() or 'Done.'

        for tc in tool_calls:
            fn   = tc['function']
            args = fn.get('arguments', {})
            if isinstance(args, str):
                args = json.loads(args)
            result = execute_tool(fn['name'], args, garden)
            working.append({'role': 'tool', 'content': json.dumps(result)})

    return 'I ran into a loop. Please try rephrasing your question.'


def run_agentic_loop(
    system: str,
    messages: list,
    garden,
    max_tool_rounds: int = 5,
) -> str:
    """
    Run multi-turn tool loop until Claude returns a pure text response.
    Returns the final assistant reply string.

    Falls back to a plain complete() call for non-Anthropic providers.
    """
    from apps.ml_service.app.llm_provider import PROVIDER, complete as _llm_complete

    if PROVIDER == 'ollama':
        return _run_ollama_loop(system, messages, garden, max_tool_rounds)

    if PROVIDER != 'anthropic':
        # Other non-Anthropic providers: pass the last user message only (no tool support)
        last_user = next(
            (m['content'] for m in reversed(messages) if m['role'] == 'user'), ''
        )
        if isinstance(last_user, list):
            last_user = ' '.join(
                block.get('text', '') for block in last_user
                if isinstance(block, dict) and block.get('type') == 'text'
            )
        return _llm_complete(system, last_user)

    import anthropic

    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        raise RuntimeError(
            'The garden assistant is not configured. '
            'Add ANTHROPIC_API_KEY to your .env file.'
        )

    client = anthropic.Anthropic(api_key=key)
    working_messages = list(messages)

    for _ in range(max_tool_rounds):
        response = client.messages.create(
            model=CHAT_MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOL_SCHEMAS,
            messages=working_messages,
        )

        # Append assistant turn to working history
        working_messages.append({'role': 'assistant', 'content': response.content})

        if response.stop_reason != 'tool_use':
            text_parts = [
                block.text for block in response.content
                if hasattr(block, 'text')
            ]
            return '\n'.join(text_parts).strip() or 'Done.'

        # Execute each tool_use block and collect results
        tool_results = []
        for block in response.content:
            if block.type != 'tool_use':
                continue
            result = execute_tool(block.name, block.input, garden)
            tool_results.append({
                'type':        'tool_result',
                'tool_use_id': block.id,
                'content':     json.dumps(result),
            })

        working_messages.append({'role': 'user', 'content': tool_results})

    # Max rounds hit — return whatever text exists in the last assistant turn
    for m in reversed(working_messages):
        if m['role'] == 'assistant':
            content = m['content']
            parts = []
            if isinstance(content, list):
                parts = [b.text for b in content if hasattr(b, 'text')]
            elif isinstance(content, str):
                parts = [content]
            if parts:
                return '\n'.join(parts).strip()

    return 'I ran into a loop. Please try rephrasing your question.'
