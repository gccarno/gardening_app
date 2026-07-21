import logging
import logging.handlers
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from .db.session import engine
from .routers import gardens, weather, perenual, beds, plants, tasks, canvas, library, chat, admin, tips
from .routers import auth, identify, seed_room, observations, journal, compost
from .routers.weather import run_daily_weather_fetch
from .services.auth import get_current_user
from .jobs.gcs_backup import run_backup as run_gcs_backup
from .jobs.ml_snapshot import run_ml_snapshot

# ── Logging setup ────────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).parents[4] / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
    force=True,
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / 'startup.log', maxBytes=1_000_000, backupCount=3
        ),
    ],
)
logger = logging.getLogger('garden.main')

_GARDEN_MIGRATIONS = [
    ('first_frost_date',           'ALTER TABLE garden ADD COLUMN first_frost_date DATE'),
    ('frost_free',                 'ALTER TABLE garden ADD COLUMN frost_free BOOLEAN'),
    ('frost_station_id',           'ALTER TABLE garden ADD COLUMN frost_station_id VARCHAR(20)'),
    ('frost_station_name',         'ALTER TABLE garden ADD COLUMN frost_station_name VARCHAR(100)'),
    ('frost_station_distance_km',  'ALTER TABLE garden ADD COLUMN frost_station_distance_km FLOAT'),
    ('last_frost_dates_json',      'ALTER TABLE garden ADD COLUMN last_frost_dates_json TEXT'),
    ('first_frost_dates_json',     'ALTER TABLE garden ADD COLUMN first_frost_dates_json TEXT'),
]


_PLANT_LIBRARY_MIGRATIONS = [
    ('cloned_from_id', 'ALTER TABLE plant_library ADD COLUMN cloned_from_id INTEGER REFERENCES plant_library(id)'),
    ('is_custom',      'ALTER TABLE plant_library ADD COLUMN is_custom BOOLEAN DEFAULT 0'),
]


def _run_migrations():
    t0 = time.perf_counter()
    # Create any tables that don't yet exist (safe — skips existing tables).
    # Works on both SQLite and Postgres; a fresh Postgres DB gets the full
    # current schema this way. Future schema changes go through Alembic
    # (apps/backend/alembic/) — do NOT add to the PRAGMA lists below.
    from .db.models import Base
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == 'sqlite':
        # Legacy column backfills for pre-existing SQLite databases only.
        with engine.connect() as conn:
            from sqlalchemy import text
            cols = [row[1] for row in conn.execute(text('PRAGMA table_info(garden)'))]
            for col, ddl in _GARDEN_MIGRATIONS:
                if col not in cols:
                    conn.execute(text(ddl))
                    conn.commit()
                    logger.info('[migration] Added garden.%s', col)
            lib_cols = [row[1] for row in conn.execute(text('PRAGMA table_info(plant_library)'))]
            for col, ddl in _PLANT_LIBRARY_MIGRATIONS:
                if col not in lib_cols:
                    conn.execute(text(ddl))
                    conn.commit()
                    logger.info('[migration] Added plant_library.%s', col)
    logger.info('[startup] migrations done — %.0fms', (time.perf_counter() - t0) * 1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t_start = time.perf_counter()
    logger.info('[startup] begin')

    _run_migrations()

    # On free-tier cloud hosts the process spins down when idle, so in-process
    # cron never fires — set ENABLE_SCHEDULER=0 there and trigger the admin job
    # endpoints from GitHub Actions cron instead (.github/workflows/scheduled-jobs.yaml).
    scheduler = None
    if os.environ.get('ENABLE_SCHEDULER', '1') != '0':
        t_sched = time.perf_counter()
        scheduler = BackgroundScheduler()
        # Fetch weather for all gardens daily at 2 AM.
        scheduler.add_job(run_daily_weather_fetch, 'cron', hour=2, minute=0)
        # NOTE: removed immediate startup weather fetch — it made external HTTP calls
        # (open-meteo) on every restart, slowing startup. The nightly cron is sufficient.
        # Watering-model snapshot/label-backfill/prune — right after the weather fetch.
        scheduler.add_job(run_ml_snapshot, 'cron', hour=2, minute=10)
        scheduler.add_job(run_gcs_backup, 'cron', hour=3, minute=0)
        scheduler.start()
        logger.info('[startup] scheduler started — %.0fms', (time.perf_counter() - t_sched) * 1000)
    logger.info('[startup] app ready — %.0fms total', (time.perf_counter() - t_start) * 1000)

    yield

    if scheduler:
        scheduler.shutdown()
        logger.info('[shutdown] scheduler stopped')


app = FastAPI(
    title='Garden App API',
    description='FastAPI backend for the garden planning app.',
    version='0.1.0',
    lifespan=lifespan,
)

# Vite dev server by default; prod is same-origin. Override with a
# comma-separated CORS_ORIGINS env var when hosting web and API separately.
_cors_origins = [
    o.strip() for o in os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',')
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def log_slow_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    if ms > 200:
        logger.warning('SLOW %s %s — %.0fms', request.method, request.url.path, ms)
    return response

# Open routes: login/register + health. admin.router is guarded by X-Job-Token.
app.include_router(auth.router)
app.include_router(admin.router)

# Everything else requires a logged-in user (Authorization: Bearer <token>).
_require_login = [Depends(get_current_user)]
for _router in (
    gardens.router, weather.router, perenual.router, beds.router, plants.router,
    tasks.router, canvas.router, library.router, chat.router, tips.router,
    seed_room.router, observations.router, journal.router, compost.router,
    identify.router, auth.members_router,
):
    app.include_router(_router, dependencies=_require_login)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


_ROOT = Path(__file__).parents[3]  # gardening_app/
_STATIC_DIR = _ROOT / 'apps' / 'api' / 'static'   # images, CSS — keep in place (no migration needed)
_DIST_DIR = _ROOT / 'apps' / 'web' / 'dist'       # React build output

# Serve plant images, CSS, and other legacy static assets.
# Locally these live on disk; in the cloud (no local tree) they live in a
# PRIVATE GCS bucket, and the backend proxies /static/* using its service
# account key — the bucket never needs public access. Image filenames are
# unique and their content never changes, so the response is marked immutable
# and browsers/Coil cache it on-device: each image is downloaded from GCS at
# most once per device.
_GCS_STATIC_BUCKET = os.environ.get('GCS_STATIC_BUCKET')
if _GCS_STATIC_BUCKET:
    # The repo ships a partial static tree (css/js + a few images), so the
    # directory exists even in the cloud — a plain "dir exists → mount" check
    # would serve those few files and 404 everything else. Serve local files
    # first, then fall back to the private bucket.
    import mimetypes

    from starlette.responses import Response

    _STATIC_ROOT = _STATIC_DIR.resolve()

    @app.get('/static/{path:path}', include_in_schema=False)
    def static_local_then_gcs(path: str):
        # sync `def` on purpose: the GCS download blocks, so FastAPI runs it
        # in a worker thread instead of stalling the event loop
        try:
            target = (_STATIC_ROOT / path).resolve()
        except (OSError, ValueError):
            return Response(status_code=404)
        if not target.is_relative_to(_STATIC_ROOT):  # block ../ traversal
            return Response(status_code=404)
        if target.is_file():
            return FileResponse(str(target))
        from .services.storage import read_static
        data = read_static(path)
        if data is None:
            return Response(status_code=404)
        media_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        return Response(
            content=data,
            media_type=media_type,
            headers={'Cache-Control': 'public, max-age=31536000, immutable'},
        )
elif _STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(_STATIC_DIR)), name='static')

# SPA catch-all — MUST come after all API routers so it never shadows /api/* routes.
# If the React build doesn't exist yet (pre-`npm run build`), this block is skipped
# and only the API is available (which is fine for development).
if _DIST_DIR.exists():
    @app.get('/{full_path:path}', include_in_schema=False)
    async def spa_catchall(full_path: str):
        """Serve the React SPA for any path that isn't a known API route."""
        target = _DIST_DIR / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_DIST_DIR / 'index.html'))
