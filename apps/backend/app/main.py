from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from .routers import gardens, weather, perenual, beds, plants, tasks, canvas, library, chat

app = FastAPI(
    title='Garden App API',
    description='FastAPI backend for the garden planning app.',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],  # Vite dev server; prod is same-origin
    allow_methods=['*'],
    allow_headers=['*'],
)

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
