import logging
import logging.handlers
import time
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from .db.session import engine
from .routers import gardens, weather, perenual, beds, plants, tasks, canvas, library, chat
from .routers.weather import run_daily_weather_fetch
from .jobs.gcs_backup import run_backup as run_gcs_backup

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

    t_sched = time.perf_counter()
    scheduler = BackgroundScheduler()
    # Fetch weather for all gardens daily at 2 AM.
    scheduler.add_job(run_daily_weather_fetch, 'cron', hour=2, minute=0)
    # NOTE: removed immediate startup weather fetch — it made external HTTP calls
    # (open-meteo) on every restart, slowing startup. The nightly cron is sufficient.
    scheduler.add_job(run_gcs_backup, 'cron', hour=3, minute=0)
    scheduler.start()
    logger.info('[startup] scheduler started — %.0fms', (time.perf_counter() - t_sched) * 1000)
    logger.info('[startup] app ready — %.0fms total', (time.perf_counter() - t_start) * 1000)

    yield

    scheduler.shutdown()
    logger.info('[shutdown] scheduler stopped')


app = FastAPI(
    title='Garden App API',
    description='FastAPI backend for the garden planning app.',
    version='0.1.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],  # Vite dev server; prod is same-origin
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

app.include_router(gardens.router)
app.include_router(weather.router)
app.include_router(perenual.router)
app.include_router(beds.router)
app.include_router(plants.router)
app.include_router(tasks.router)
app.include_router(canvas.router)
app.include_router(library.router)
app.include_router(chat.router)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


_ROOT = Path(__file__).parents[3]  # gardening_app/
_STATIC_DIR = _ROOT / 'apps' / 'api' / 'static'   # images, CSS — keep in place (no migration needed)
_DIST_DIR = _ROOT / 'apps' / 'web' / 'dist'       # React build output

# Serve plant images, CSS, and other legacy static assets
if _STATIC_DIR.exists():
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
