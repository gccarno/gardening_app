"""
Convenience launcher for the garden app.

Production mode (serves React build):
    uv run python start.py

Development mode (React via Vite dev server on :5173, API on :8000):
    Terminal 1: uv run python start.py
    Terminal 2: cd apps/web && npm run dev
"""
import subprocess
import sys

subprocess.run(
    [
        sys.executable, '-m', 'uvicorn',
        'apps.backend.app.main:app',
        '--host', '0.0.0.0',
        '--port', '8000',
        '--reload',
    ],
    check=True,
)
