"""
Integration test: time backend startup and key frontend API calls.

Usage:
    uv run python scripts/test_startup_timing.py

Results are printed to the terminal and appended to logs/startup_timing_test.log.
"""

import subprocess
import sys
import time
import threading
import requests
import json
from datetime import datetime
from pathlib import Path

BASE_URL = 'http://127.0.0.1:8000'
LOG_PATH = Path(__file__).parents[1] / 'logs' / 'startup_timing_test.log'
LOG_PATH.parent.mkdir(exist_ok=True)

HEALTH_TIMEOUT = 30   # seconds to wait for server to become ready
POLL_INTERVAL = 0.25  # seconds between health-check polls


def start_server() -> subprocess.Popen:
    """Launch uvicorn as a subprocess, streaming its stderr so startup logs appear."""
    return subprocess.Popen(
        [sys.executable, '-m', 'uvicorn',
         'apps.backend.app.main:app',
         '--host', '127.0.0.1',
         '--port', '8000',
         '--log-level', 'info'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=Path(__file__).parents[1],
    )


def stream_output(proc: subprocess.Popen, lines: list):
    """Thread: read server stdout/stderr and collect lines."""
    for line in proc.stdout:
        lines.append(line.rstrip())
        print(f'  [server] {line}', end='')


def wait_for_ready(timeout: float) -> float:
    """Poll /api/health until it responds. Returns seconds elapsed."""
    t0 = time.perf_counter()
    deadline = t0 + timeout
    while time.perf_counter() < deadline:
        try:
            r = requests.get(f'{BASE_URL}/api/health', timeout=1)
            if r.status_code == 200:
                return time.perf_counter() - t0
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f'Server not ready after {timeout}s')


def time_request(method: str, path: str, **kwargs) -> tuple[int, float]:
    """Make one HTTP request and return (status_code, ms)."""
    t0 = time.perf_counter()
    r = requests.request(method, f'{BASE_URL}{path}', timeout=10, **kwargs)
    return r.status_code, (time.perf_counter() - t0) * 1000, r


def get_first_garden_id() -> int | None:
    _, _, r = time_request('GET', '/api/gardens')
    gardens = r.json()
    if isinstance(gardens, list) and gardens:
        return gardens[0].get('id')
    return None


def server_already_running() -> bool:
    try:
        r = requests.get(f'{BASE_URL}/api/health', timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def run():
    print('=' * 60)
    print('Garden App -- Startup Timing Test')
    print(f'Started: {datetime.now().isoformat()}')
    print('=' * 60)

    server_lines: list[str] = []
    results = []
    proc = None

    already_up = server_already_running()
    if already_up:
        print('\n[!] Server already running on port 8000 -- skipping cold start.')
        print('    Restart the server manually to measure startup time.')
        print('    Proceeding with API response time measurements only.\n')
    else:
        proc = start_server()
        t = threading.Thread(target=stream_output, args=(proc, server_lines), daemon=True)
        t.start()

        print('\n[1] Waiting for server to become ready...')
        try:
            ready_s = wait_for_ready(HEALTH_TIMEOUT)
        except TimeoutError as e:
            print(f'FAIL: {e}')
            proc.terminate()
            return

        results.append(('Server ready (time-to-first-byte /api/health)', ready_s * 1000))
        print(f'    Ready in {ready_s*1000:.0f}ms')

    # ── Find a garden to use ────────────────────────────────────
    garden_id = get_first_garden_id()

    # ── Time individual API calls ────────────────────────────────
    print('\n[2] Timing individual API calls (sequential)...')
    endpoints = [
        ('GET', '/api/gardens'),
        ('GET', f'/api/beds{"?garden_id=" + str(garden_id) if garden_id else ""}'),
        ('GET', f'/api/canvas-plants{"?garden_id=" + str(garden_id) if garden_id else ""}'),
        ('GET', f'/api/plants{"?garden_id=" + str(garden_id) if garden_id else ""}'),
        ('GET', '/api/tasks'),
        ('GET', '/api/health'),
    ]

    for method, path in endpoints:
        status, ms, _ = time_request(method, path)
        label = f'{method} {path}'
        results.append((label, ms))
        flag = '  [SLOW]' if ms > 200 else ''
        print(f'    {ms:6.0f}ms  {status}  {path}{flag}')

    # ── Parallel burst (simulate frontend Promise.all) ──────────
    print('\n[3] Parallel burst (simulating frontend Promise.all)...')
    parallel_endpoints = [ep for ep in endpoints if ep[1] != '/api/health']
    t_parallel_start = time.perf_counter()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(parallel_endpoints)) as pool:
        futures = {pool.submit(time_request, m, p): p for m, p in parallel_endpoints}
        parallel_results = {}
        for f in concurrent.futures.as_completed(futures):
            path = futures[f]
            status, ms, _ = f.result()
            parallel_results[path] = (status, ms)

    parallel_total = (time.perf_counter() - t_parallel_start) * 1000
    for path, (status, ms) in parallel_results.items():
        print(f'    {ms:6.0f}ms  {status}  {path}')
    print(f'    -------------------------')
    print(f'    {parallel_total:6.0f}ms  total wall-clock (parallel)')
    results.append(('Parallel burst wall-clock', parallel_total))

    # ── Shutdown ────────────────────────────────────────────────
    if proc is not None:
        proc.terminate()
        proc.wait(timeout=5)

    # ── Report ──────────────────────────────────────────────────
    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    for label, ms in results:
        flag = '  *** SLOW ***' if ms > 500 else ('  [slow]' if ms > 200 else '')
        print(f'  {ms:7.0f}ms  {label}{flag}')

    # ── Write log ───────────────────────────────────────────────
    with open(LOG_PATH, 'a') as f:
        f.write(f'\n{"="*60}\n')
        f.write(f'Run: {datetime.now().isoformat()}\n')
        f.write(f'{"="*60}\n')
        for label, ms in results:
            f.write(f'  {ms:7.0f}ms  {label}\n')
        f.write('\nServer output:\n')
        for line in server_lines:
            f.write(f'  {line}\n')

    print(f'\nLog written to: {LOG_PATH}')


if __name__ == '__main__':
    run()
