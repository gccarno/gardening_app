"""
Unit tests for all 12 LLM-callable tools in apps/ml_service/app/chat_tools.py.

Each test calls execute_tool() directly with a real in-memory SQLite session.
External calls (Open-Meteo, ChromaDB) are mocked via unittest.mock.
"""
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.ml_service.app.chat_tools import execute_tool
from apps.backend.app.db.models import Plant, BedPlant, Task


# ── 1. get_garden_plan ────────────────────────────────────────────────────────

def test_get_garden_plan_no_garden(db):
    result = execute_tool('get_garden_plan', {}, None, db)
    assert 'error' in result


def test_get_garden_plan_empty(db, garden):
    result = execute_tool('get_garden_plan', {}, garden, db)
    assert result['garden'] == 'Test Garden'
    assert result['zone'] == '5b'
    assert result['beds'] == []
    assert result['total_plants'] == 0


def test_get_garden_plan_with_plant(db, garden, plant_in_bed):
    result = execute_tool('get_garden_plan', {}, garden, db)
    assert result['total_plants'] == 1
    bed = result['beds'][0]
    assert bed['name'] == 'Raised Bed A'
    assert any(p['name'] == 'Tomato' for p in bed['plants'])


# ── 2. check_companion_planting ───────────────────────────────────────────────

def test_check_companion_planting_not_found(db, garden):
    result = execute_tool('check_companion_planting', {'plant_name': 'Unicorn Fruit'}, garden, db)
    assert 'error' in result


def test_check_companion_planting_single(db, garden, library_plant):
    result = execute_tool('check_companion_planting', {'plant_name': 'Tomato'}, garden, db)
    assert result['plant'] == 'Tomato'
    assert 'Basil' in result['good_companions']
    assert 'Fennel' in result['bad_companions']


def test_check_companion_planting_pair_compatible(db, garden, library_plant):
    result = execute_tool(
        'check_companion_planting',
        {'plant_name': 'Tomato', 'companion_name': 'Basil'},
        garden, db,
    )
    assert 'pairwise' in result
    assert 'GOOD' in result['pairwise']


def test_check_companion_planting_pair_incompatible(db, garden, library_plant):
    result = execute_tool(
        'check_companion_planting',
        {'plant_name': 'Tomato', 'companion_name': 'Fennel'},
        garden, db,
    )
    assert 'pairwise' in result
    assert 'BAD' in result['pairwise']


# ── 3. check_planting_calendar ────────────────────────────────────────────────

def test_check_planting_calendar_not_found(db, garden):
    result = execute_tool('check_planting_calendar', {'plant_name': 'Unobtainium'}, garden, db)
    assert 'error' in result


def test_check_planting_calendar(db, garden, library_plant):
    result = execute_tool('check_planting_calendar', {'plant_name': 'Tomato'}, garden, db)
    assert result['plant'] == 'Tomato'
    assert result['zone'] == '5b'
    # Tomato has sow_indoor_weeks=6, transplant_offset=0, direct_sow_offset=2
    assert 'start_indoors' in result
    assert 'transplant' in result
    assert 'direct_sow' in result
    # Dates should be ISO strings
    date.fromisoformat(result['start_indoors'])
    date.fromisoformat(result['transplant'])


# ── 4. check_spacing_requirements ────────────────────────────────────────────

def test_check_spacing_requirements_not_found(db, garden):
    result = execute_tool('check_spacing_requirements', {'plant_name': 'Unobtainium'}, garden, db)
    assert 'error' in result


def test_check_spacing_requirements_no_bed(db, garden, library_plant):
    result = execute_tool('check_spacing_requirements', {'plant_name': 'Tomato'}, garden, db)
    assert result['spacing_in'] == 24


def test_check_spacing_requirements_with_bed(db, garden, bed, library_plant):
    result = execute_tool(
        'check_spacing_requirements',
        {'plant_name': 'Tomato', 'bed_name': 'Raised Bed A'},
        garden, db,
    )
    assert result['bed']['name'] == 'Raised Bed A'
    assert isinstance(result['bed']['estimated_capacity'], int)
    assert result['bed']['estimated_capacity'] > 0


# ── 5. get_plant_care_info ────────────────────────────────────────────────────

def test_get_plant_care_info_not_found(db, garden):
    result = execute_tool('get_plant_care_info', {'plant_name': 'Unobtainium'}, garden, db)
    assert 'error' in result


def test_get_plant_care_info(db, garden, library_plant):
    result = execute_tool('get_plant_care_info', {'plant_name': 'Tomato'}, garden, db)
    assert result['plant'] == 'Tomato'
    assert result['sunlight'] == 'Full sun'
    assert result['water'] == 'Moderate'
    assert result['days_to_harvest'] == 70


# ── 6. add_plant_to_garden ────────────────────────────────────────────────────

def test_add_plant_to_garden_no_garden(db):
    result = execute_tool('add_plant_to_garden', {'plant_name': 'Tomato'}, None, db)
    assert 'error' in result


def test_add_plant_to_garden(db, garden, library_plant):
    before = db.query(Plant).filter_by(garden_id=garden.id).count()
    result = execute_tool('add_plant_to_garden', {'plant_name': 'Tomato'}, garden, db)
    assert result['added'] == 'Tomato'
    assert result['garden'] == 'Test Garden'
    assert db.query(Plant).filter_by(garden_id=garden.id).count() == before + 1


def test_add_plant_to_garden_with_bed(db, garden, bed, library_plant):
    result = execute_tool(
        'add_plant_to_garden',
        {'plant_name': 'Tomato', 'bed_name': 'Raised Bed A'},
        garden, db,
    )
    assert result.get('bed') == 'Raised Bed A'
    plant_id = result['plant_id']
    bp = db.query(BedPlant).filter_by(plant_id=plant_id).first()
    assert bp is not None
    assert bp.bed_id == bed.id


# ── 7. create_task ────────────────────────────────────────────────────────────

def test_create_task_no_garden(db):
    result = execute_tool('create_task', {'task_type': 'watering'}, None, db)
    assert 'error' in result


def test_create_task_watering(db, garden):
    result = execute_tool('create_task', {'task_type': 'watering'}, garden, db)
    assert result['task_type'] == 'watering'
    assert result['due_date'] == date.today().isoformat()
    task = db.query(Task).filter_by(id=result['task_id']).first()
    assert task is not None
    assert task.garden_id == garden.id


def test_create_task_auto_due_date_seeding(db, garden, plant_in_bed):
    # Seeding auto-calculates from frost date and sow_indoor_weeks.
    # plant_in_bed places a 'Tomato' Plant (linked to library_plant) in the garden.
    result = execute_tool(
        'create_task',
        {'task_type': 'seeding', 'plant_name': 'Tomato'},
        garden, db,
    )
    assert 'error' not in result
    assert result['task_type'] == 'seeding'
    # Should have a due_date: 6 weeks before frost (Apr 15) = Mar 4, 2026
    assert result['due_date'] is not None
    due = date.fromisoformat(result['due_date'])
    expected = date(2026, 4, 15) - timedelta(weeks=6)
    assert due == expected


# ── 8. list_upcoming_tasks ────────────────────────────────────────────────────

def test_list_upcoming_tasks_no_garden(db):
    result = execute_tool('list_upcoming_tasks', {}, None, db)
    assert 'error' in result


def test_list_upcoming_tasks(db, garden, upcoming_task):
    result = execute_tool('list_upcoming_tasks', {}, garden, db)
    assert result['count'] == 1
    assert result['tasks'][0]['title'] == 'Water tomatoes'


def test_list_upcoming_tasks_excludes_far_future(db, garden, upcoming_task):
    # upcoming_task is due in 5 days; window of 2 days should exclude it
    result = execute_tool('list_upcoming_tasks', {'days': 2}, garden, db)
    assert result['count'] == 0


def test_list_upcoming_tasks_excludes_completed(db, garden, upcoming_task):
    # upcoming_task fixture creates completed=False; verify completed tasks are excluded
    upcoming_task.completed = True
    db.flush()
    result = execute_tool('list_upcoming_tasks', {}, garden, db)
    assert result['count'] == 0


# ── 9. get_weather_forecast ───────────────────────────────────────────────────

def test_get_weather_forecast_no_coords(db, garden):
    garden.latitude = None
    garden.longitude = None
    result = execute_tool('get_weather_forecast', {}, garden, db)
    assert 'error' in result


def test_get_weather_forecast_mocked(db, garden):
    mock_forecast = [
        {
            'date': (date.today() + timedelta(days=i)).isoformat(),
            'high_c': 20, 'low_c': 10, 'precip_prob': 20, 'precip_mm': 0,
            'wind_kmh': 15, 'et0_mm': 3.5, 'condition': 'Partly cloudy',
        }
        for i in range(7)
    ]
    with patch('apps.ml_service.app.watering_engine.fetch_7day_forecast',
               return_value=mock_forecast):
        result = execute_tool('get_weather_forecast', {}, garden, db)
    assert 'error' not in result
    assert result['garden'] == 'Test Garden'
    assert len(result['forecast']) == 7
    assert 'high_c' in result['forecast'][0]


# ── 10. get_watering_history ──────────────────────────────────────────────────

def test_get_watering_history_no_garden(db):
    result = execute_tool('get_watering_history', {}, None, db)
    assert 'error' in result


def test_get_watering_history(db, garden, weather_log):
    result = execute_tool('get_watering_history', {}, garden, db)
    assert result['has_weather_data'] is True
    assert len(result['rainfall_events']) == 1
    assert result['rainfall_events'][0]['rainfall_in'] == pytest.approx(0.4)


def test_get_watering_history_no_data(db, garden):
    result = execute_tool('get_watering_history', {}, garden, db)
    assert result['has_weather_data'] is False
    assert result['rainfall_events'] == []


# ── 11. get_watering_recommendation ──────────────────────────────────────────

def test_get_watering_recommendation_no_garden(db):
    result = execute_tool('get_watering_recommendation', {}, None, db)
    assert 'error' in result


def test_get_watering_recommendation(db, garden, plant_in_bed, weather_log):
    mock_today = {
        'et0_mm': 4.0, 'precip_mm': 0.0, 'temp_max_c': 22,
        'temp_min_c': 12, 'wind_kmh': 10, 'precip_prob': 5,
    }
    with patch('apps.ml_service.app.watering_engine.fetch_forecast_today',
               return_value=mock_today):
        result = execute_tool('get_watering_recommendation', {}, garden, db)
    assert 'beds' in result
    assert 'summary' in result


# ── 12. search_growing_guides ─────────────────────────────────────────────────

def test_search_growing_guides_no_query(db, garden):
    result = execute_tool('search_growing_guides', {'query': ''}, garden, db)
    assert 'error' in result


def test_search_growing_guides_mocked(db, garden):
    mock_results = [
        {
            'source': 'TAMU Easy Gardening: Tomatoes',
            'region': None,
            'text': 'Tomatoes need full sun and consistent moisture.',
            'score': 0.92,
        }
    ]
    with patch('build_rag.search_guides', return_value=mock_results, create=True):
        # Patch the import inside the function body
        with patch.dict('sys.modules', {'build_rag': MagicMock(search_guides=lambda *a, **kw: mock_results)}):
            result = execute_tool(
                'search_growing_guides',
                {'query': 'tomato watering', 'plant_name': 'Tomato'},
                garden, db,
            )
    assert 'results' in result
    if result.get('results'):
        assert 'source' in result['results'][0]
        assert 'passage' in result['results'][0]


def test_search_growing_guides_no_rag_index(db, garden):
    # If build_rag is not importable, should return a graceful error
    import sys
    original = sys.modules.get('build_rag')
    sys.modules.pop('build_rag', None)

    result = execute_tool(
        'search_growing_guides',
        {'query': 'tomato care'},
        garden, db,
    )
    # Either an import error message or empty results — not an unhandled exception
    assert 'results' in result or 'error' in result

    if original is not None:
        sys.modules['build_rag'] = original
