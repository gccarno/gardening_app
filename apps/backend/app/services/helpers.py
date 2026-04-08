"""
Shared constants, lookup tables, and utility functions used across routers.
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests as http
from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.orm import Session

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
# helpers.py lives at apps/backend/app/services/helpers.py
STATIC_DIR = Path(__file__).parents[3] / 'api' / 'static'
REPO_ROOT   = Path(__file__).parents[4]

# Ensure ml_service is importable
_repo_str = str(REPO_ROOT)
if _repo_str not in sys.path:
    sys.path.insert(0, _repo_str)

# ── External API keys ─────────────────────────────────────────────────────────
PERENUAL_KEY         = os.getenv('PERENUAL_API_KEY', '')
PERMAPEOPLE_KEY_ID   = os.getenv('X-Permapeople-Key-Id', '')
PERMAPEOPLE_KEY_SECRET = os.getenv('X-Permapeople-Key-Secret', '')

# ── Frost dates keyed by USDA zone number (strip letter suffix) ───────────────
FROST_DATES = {
    '1':  ('Jun 15', 'Aug 15'), '2':  ('Jun 1',  'Sep 1'),
    '3':  ('May 15', 'Sep 15'), '4':  ('May 1',  'Oct 1'),
    '5':  ('Apr 15', 'Oct 15'), '6':  ('Apr 1',  'Oct 31'),
    '7':  ('Mar 15', 'Nov 15'), '8':  ('Feb 15', 'Dec 1'),
    '9':  ('Jan 31', 'Dec 15'), '10': ('rare',   'rare'),
    '11': ('none',   'none'),   '12': ('none',   'none'),
    '13': ('none',   'none'),
}

# ── WMO weather interpretation codes ─────────────────────────────────────────
WMO = {
    0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
    45: 'Fog', 48: 'Icy fog',
    51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
    61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
    71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 77: 'Snow grains',
    80: 'Light showers', 81: 'Showers', 82: 'Heavy showers',
    85: 'Snow showers', 86: 'Heavy snow showers',
    95: 'Thunderstorm', 96: 'Thunderstorm w/ hail', 99: 'Thunderstorm w/ heavy hail',
}


# ── Generic helpers ───────────────────────────────────────────────────────────

def get_or_404(db: Session, model, id: int):
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f'{model.__name__} {id} not found')
    return obj


def get_season(today: date) -> tuple[str, str]:
    m, d = today.month, today.day
    if (m == 12 and d >= 21) or m in (1, 2) or (m == 3 and d < 20):
        return 'Winter', '❄️'
    if (m == 3 and d >= 20) or m in (4, 5) or (m == 6 and d < 21):
        return 'Spring', '🌸'
    if (m == 6 and d >= 21) or m in (7, 8) or (m == 9 and d < 22):
        return 'Summer', '☀️'
    return 'Fall', '🍂'


def rainfall_summary(db: Session, garden_id: int, days: int = 7) -> dict:
    from ..db.models import WeatherLog
    cutoff = date.today() - timedelta(days=days)
    logs = (db.query(WeatherLog)
            .filter(WeatherLog.garden_id == garden_id, WeatherLog.date >= cutoff)
            .all())
    total = sum(l.rainfall_in or 0 for l in logs)
    return {'total_in': round(total, 2), 'days_with_data': len(logs)}


def ext_from_content_type(content_type: str) -> str:
    if 'png'  in content_type: return '.png'
    if 'webp' in content_type: return '.webp'
    return '.jpg'


# ── External API helpers ──────────────────────────────────────────────────────

def perenual_get(path: str, params: dict) -> tuple:
    """Return (data, err_type, err_msg)."""
    if not PERENUAL_KEY:
        return None, 'config', 'PERENUAL_API_KEY is not configured.'
    params['key'] = PERENUAL_KEY
    try:
        resp = http.get(f'https://perenual.com/api/{path}', params=params, timeout=8)
    except http.exceptions.Timeout:
        return None, 'network', 'Request to Perenual timed out.'
    except http.exceptions.RequestException as e:
        return None, 'network', f'Network error: {e}'
    if resp.status_code == 429:
        return None, 'rate_limit', (
            'Perenual daily limit reached (100 req/day on free plan). Try again tomorrow.'
        )
    if resp.status_code == 401:
        return None, 'auth', 'Invalid Perenual API key. Check your .env file.'
    if not resp.ok:
        return None, 'api', f'Perenual returned HTTP {resp.status_code}.'
    data = resp.json()
    if isinstance(data, dict) and 'Upgrade Plans' in str(data.get('message', '')):
        return None, 'rate_limit', 'This data requires a Perenual premium plan.'
    return data, None, None


def permapeople_post(path: str, body: dict) -> tuple:
    """Return (data, err_type, err_msg)."""
    if not PERMAPEOPLE_KEY_ID or not PERMAPEOPLE_KEY_SECRET:
        return None, 'config', 'Permapeople credentials not configured.'
    headers = {
        'x-permapeople-key-id':     PERMAPEOPLE_KEY_ID,
        'x-permapeople-key-secret': PERMAPEOPLE_KEY_SECRET,
        'Content-Type': 'application/json',
    }
    try:
        resp = http.post(f'https://permapeople.org/api/{path}', json=body, headers=headers, timeout=8)
    except http.exceptions.Timeout:
        return None, 'network', 'Request to Permapeople timed out.'
    except http.exceptions.RequestException as e:
        return None, 'network', f'Network error: {e}'
    if resp.status_code == 401:
        return None, 'auth', 'Invalid Permapeople credentials.'
    if not resp.ok:
        return None, 'api', f'Permapeople returned HTTP {resp.status_code}.'
    return resp.json(), None, None
