"""Find and remove leftover E2E test data from the live server / Neon DB.

The E2E suite prefixes every entity it creates with '[E2E]' (see
tests/e2e/README.md). Teardown normally removes everything, but a failed run
can leave residue. This script sweeps it:

    uv run python scripts/e2e_cleanup.py             # dry run: report residue
    uv run python scripts/e2e_cleanup.py --apply     # actually delete it
    uv run python scripts/e2e_cleanup.py --apply --sql   # also SQL-clean what
                                                         # the API can't delete

Two phases:
 1. API phase — logs in with USERNAME/PASSWORD from the repo-root .env (read
    from the file, never the process env: Windows reserves USERNAME) and
    deletes [E2E]-prefixed gardens bottom-up (canvas plants, plants, beds,
    tasks, journal, seed trays, compost bins, then the garden), plus stray
    [E2E] tasks. Garden delete does NOT cascade, so order matters.
 2. SQL phase (--sql, requires DATABASE_URL in .env) — removes what has no
    delete endpoint: [E2E] PlantLibrary clones (+ their images) and orphaned
    rows left pointing at deleted gardens (weather logs, plants, beds, tasks).

Only entities whose name/title starts EXACTLY with '[E2E]' are ever touched.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = 'https://garden-app-wa0b.onrender.com'
PREFIX = '[E2E]'


def load_env() -> dict:
    return {k: v for k, v in dotenv_values(REPO_ROOT / '.env').items() if v}


def login(base_url: str, env: dict) -> requests.Session:
    email, password = env.get('USERNAME'), env.get('PASSWORD')
    if not email or not password:
        sys.exit('USERNAME/PASSWORD missing from repo-root .env')
    s = requests.Session()
    resp = s.post(f'{base_url}/api/auth/login',
                  json={'email': email, 'password': password}, timeout=120)
    resp.raise_for_status()
    s.headers['Authorization'] = f"Bearer {resp.json()['token']}"
    return s


def is_test_entity(name: str | None) -> bool:
    return bool(name) and name.startswith(PREFIX)


class Sweeper:
    def __init__(self, session: requests.Session, base_url: str, apply: bool):
        self.s = session
        self.base = base_url
        self.apply = apply
        self.found: list[str] = []

    def _delete(self, label: str, method: str, path: str) -> None:
        self.found.append(label)
        if not self.apply:
            print(f'  would delete: {label}')
            return
        resp = self.s.request(method, f'{self.base}{path}', timeout=60)
        status = 'ok' if resp.ok else f'FAILED {resp.status_code}'
        print(f'  delete {label}: {status}')

    def _get(self, path: str):
        resp = self.s.get(f'{self.base}{path}', timeout=60)
        resp.raise_for_status()
        return resp.json()

    def sweep_garden(self, garden: dict) -> None:
        gid = garden['id']
        print(f"[E2E] garden #{gid} '{garden['name']}':")
        for cp in self._get(f'/api/gardens/{gid}/canvas-plants'):
            self._delete(f'canvas-plant #{cp["id"]}', 'POST',
                         f'/api/canvas-plants/{cp["id"]}/delete')
        # Plant delete cascades its bed_plants (and their observations).
        for p in self._get(f'/api/plants?garden_id={gid}'):
            self._delete(f'plant #{p["id"]} {p.get("name", "")}', 'DELETE',
                         f'/api/plants/{p["id"]}')
        for b in self._get(f'/api/beds?garden_id={gid}'):
            self._delete(f'bed #{b["id"]} {b.get("name", "")}', 'POST',
                         f'/api/beds/{b["id"]}/delete')
        for t in self._get(f'/api/tasks?garden_id={gid}'):
            self._delete(f'task #{t["id"]} {t.get("title", "")}', 'DELETE',
                         f'/api/tasks/{t["id"]}')
        journal = self._get(f'/api/gardens/{gid}/journal?per_page=100')
        for e in journal.get('entries', []):
            self._delete(f'journal #{e["id"]}', 'DELETE', f'/api/journal/{e["id"]}')
        for tray in self._get(f'/api/gardens/{gid}/seed-room'):
            self._delete(f'seed-tray #{tray["id"]}', 'DELETE',
                         f'/api/seed-room/{tray["id"]}')
        for bin_ in self._get(f'/api/gardens/{gid}/compost'):
            self._delete(f'compost-bin #{bin_["id"]}', 'DELETE',
                         f'/api/compost/{bin_["id"]}')
        self._delete(f"garden #{gid} '{garden['name']}'", 'DELETE',
                     f'/api/gardens/{gid}')

    def run(self) -> None:
        gardens = [g for g in self._get('/api/gardens') if is_test_entity(g.get('name'))]
        for g in gardens:
            self.sweep_garden(g)
        # Stray [E2E] tasks not tied to a swept garden.
        for t in self._get('/api/tasks'):
            if is_test_entity(t.get('title')):
                self._delete(f'stray task #{t["id"]} {t["title"]}', 'DELETE',
                             f'/api/tasks/{t["id"]}')
        # Library clones are report-only here: no delete endpoint (use --sql).
        lib = self._get(f'/api/library?q={requests.utils.quote(PREFIX)}&per_page=100')
        entries = lib.get('entries', lib if isinstance(lib, list) else [])
        for e in entries:
            if is_test_entity(e.get('name')):
                self.found.append(f'library clone #{e["id"]} (needs --sql)')
                print(f'  library clone #{e["id"]} {e["name"]}: no API delete, use --sql')


def sql_phase(apply: bool) -> list[str]:
    """Delete what the API can't: [E2E] library clones and orphaned rows."""
    sys.path.insert(0, str(REPO_ROOT))
    from apps.backend.app.db.models import (
        CanvasPlant, Garden, GardenBed, Plant, PlantLibrary, PlantLibraryImage,
        Task, WeatherLog,
    )
    from apps.backend.app.db.session import DATABASE_URL, SessionLocal

    if DATABASE_URL.startswith('sqlite'):
        sys.exit('--sql refused: DATABASE_URL is not set (would hit the SQLite backup)')

    found: list[str] = []
    db = SessionLocal()
    try:
        garden_ids = {gid for (gid,) in db.query(Garden.id).all()}

        clones = db.query(PlantLibrary).filter(PlantLibrary.name.like(f'{PREFIX}%')).all()
        for entry in clones:
            imgs = db.query(PlantLibraryImage).filter_by(plant_library_id=entry.id).all()
            found.append(f'library clone #{entry.id} {entry.name} (+{len(imgs)} images)')
            if apply:
                for img in imgs:
                    db.delete(img)
                # Canvas plants referencing the clone would block/orphan it.
                for cp in db.query(CanvasPlant).filter_by(library_id=entry.id).all():
                    db.delete(cp)
                db.delete(entry)

        def orphans(model, name_col, label):
            rows = (db.query(model)
                    .filter(model.garden_id.isnot(None),
                            model.garden_id.notin_(garden_ids)).all())
            rows += (db.query(model)
                     .filter(model.garden_id.is_(None),
                             name_col.like(f'{PREFIX}%')).all()) if name_col is not None else []
            for r in rows:
                found.append(f'orphan {label} #{r.id}')
                if apply:
                    db.delete(r)

        orphans(WeatherLog, None, 'weather-log')
        orphans(Plant, Plant.name, 'plant')
        orphans(GardenBed, GardenBed.name, 'bed')
        orphans(Task, Task.title, 'task')
        orphans(CanvasPlant, None, 'canvas-plant')

        if apply:
            db.commit()
    finally:
        db.close()
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='delete (default: dry-run report)')
    ap.add_argument('--sql', action='store_true',
                    help='also run the direct-DB phase (library clones, orphans)')
    ap.add_argument('--base-url', default=None,
                    help=f'server URL (default: GARDEN_TEST_BASE_URL from .env or {DEFAULT_BASE_URL})')
    args = ap.parse_args()

    env = load_env()
    base_url = (args.base_url or env.get('GARDEN_TEST_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')
    mode = 'APPLY' if args.apply else 'DRY RUN'
    print(f'E2E cleanup [{mode}] against {base_url}')

    sweeper = Sweeper(login(base_url, env), base_url, args.apply)
    sweeper.run()

    sql_found = sql_phase(args.apply) if args.sql else []
    for line in sql_found:
        print(f'  {"deleted" if args.apply else "would delete"} (SQL): {line}')

    total = len(sweeper.found) + len(sql_found)
    if total == 0:
        print('No [E2E] residue found.')
    else:
        verb = 'removed' if args.apply else 'found'
        print(f'{total} [E2E] item(s) {verb}.')
        if not args.apply:
            sys.exit(1)  # non-zero so the orchestrator can flag residue


if __name__ == '__main__':
    main()
