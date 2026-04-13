"""
Backfill frost date data from apis.joelgrant.dev for all gardens that have a
zip_code but are missing frost data (or use --force to refresh all gardens).

Usage:
    uv run python scripts/backfill_frost_dates.py
    uv run python scripts/backfill_frost_dates.py --force
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import requests as http
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Allow running from repo root or scripts/ directory
_REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from apps.backend.app.db.models import Garden

_DEFAULT_DB = _REPO_ROOT / 'apps' / 'api' / 'instance' / 'garden.db'
DATABASE_URL = f'sqlite:///{_DEFAULT_DB}'


def _parse_frost_date(mm_dd: str, year: int) -> date | None:
    try:
        m, d = mm_dd.split('/')
        return date(year, int(m), int(d))
    except Exception:
        return None


def _fetch_frost(zip_code: str) -> dict | None:
    """Call the frost API; return parsed data or None on failure."""
    try:
        r = http.get(f'https://apis.joelgrant.dev/api/v1/frost/{zip_code}', timeout=8)
        r.raise_for_status()
        return r.json().get('data', {})
    except Exception as e:
        print(f'  ERROR fetching frost for {zip_code}: {e}')
        return None


def _apply_frost_data(garden: Garden, data: dict) -> None:
    garden.frost_free                = data.get('frost_free', False)
    station = data.get('weather_station', {})
    garden.frost_station_id          = station.get('station_id')
    garden.frost_station_name        = station.get('name')
    garden.frost_station_distance_km = station.get('distance_km')

    frost_dates = data.get('frost_dates', {})
    last_frost_probs  = frost_dates.get('last_frost_32f', {})
    first_frost_probs = frost_dates.get('first_frost_32f', {})
    year = date.today().year

    if last_frost_probs:
        garden.last_frost_dates_json = json.dumps(last_frost_probs)
        fifty = last_frost_probs.get('50%')
        if fifty:
            garden.last_frost_date = _parse_frost_date(fifty, year)

    if first_frost_probs:
        garden.first_frost_dates_json = json.dumps(first_frost_probs)
        fifty = first_frost_probs.get('50%')
        if fifty:
            garden.first_frost_date = _parse_frost_date(fifty, year)


def main():
    parser = argparse.ArgumentParser(description='Backfill frost dates for all gardens.')
    parser.add_argument('--force', action='store_true',
                        help='Refresh frost data even if already populated.')
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        gardens = db.query(Garden).filter(Garden.zip_code.isnot(None)).all()
        print(f'Found {len(gardens)} garden(s) with a zip code.')

        updated = skipped = failed = 0
        for g in gardens:
            if not args.force and g.first_frost_date and g.last_frost_dates_json:
                print(f'  [{g.id}] {g.name} — already populated, skipping.')
                skipped += 1
                continue

            print(f'  [{g.id}] {g.name} (zip={g.zip_code}) — fetching...', end=' ')
            data = _fetch_frost(g.zip_code)
            if data is None:
                failed += 1
                continue

            _apply_frost_data(g, data)
            db.commit()
            lf = g.last_frost_date.strftime('%b %d') if g.last_frost_date else 'n/a'
            ff = g.first_frost_date.strftime('%b %d') if g.first_frost_date else 'n/a'
            print(f'done  (last spring frost={lf}, first fall frost={ff})')
            updated += 1

        print(f'\nDone. updated={updated}  skipped={skipped}  failed={failed}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
