"""Fetch and parse recent logs from the Render web service for debugging.

Usage:
    uv run python scripts/render_logs.py                    # last 100 lines
    uv run python scripts/render_logs.py --limit 300
    uv run python scripts/render_logs.py --errors           # level=error, HTTP >= 400, tracebacks
    uv run python scripts/render_logs.py --grep "plants"    # substring filter
    uv run python scripts/render_logs.py --json             # machine-readable output

Requires RENDER_API_KEY in the repo-root .env (or the environment):
Render Dashboard -> avatar menu -> Account Settings -> API Keys -> Create.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from dotenv import dotenv_values

API = "https://api.render.com/v1"
SERVICE_URL = "https://garden-app-wa0b.onrender.com"

# uvicorn access-log line inside a Render message, e.g.
#   10.204.108.201:0 - "GET /api/plants?garden_id=1 HTTP/1.1" 200
ACCESS_RE = re.compile(
    r'"(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(?P<path>\S+)\s+HTTP/[\d.]+"\s+(?P<status>\d{3})'
)


@dataclass
class LogRecord:
    timestamp: str
    level: str            # from Render labels; '' when absent
    message: str
    method: str | None    # HTTP fields set only for uvicorn access lines
    path: str | None
    status: int | None


def parse_entry(entry: dict) -> LogRecord:
    """Turn one Render /v1/logs entry into a structured record."""
    level = ""
    for label in entry.get("labels") or []:
        if label.get("name") == "level":
            level = label.get("value", "")
    message = entry.get("message", "")
    m = ACCESS_RE.search(message)
    return LogRecord(
        timestamp=entry.get("timestamp", ""),
        level=level,
        message=message,
        method=m["method"] if m else None,
        path=m["path"] if m else None,
        status=int(m["status"]) if m else None,
    )


def is_error(rec: LogRecord) -> bool:
    return (
        rec.level == "error"
        or (rec.status is not None and rec.status >= 400)
        or "Traceback" in rec.message
    )


def format_record(rec: LogRecord) -> str:
    prefix = f"[{rec.level or '-'}]"
    if rec.status is not None:
        prefix += f" {rec.status} {rec.method} {rec.path}"
    return f"{rec.timestamp}  {prefix}  {rec.message}"


def load_api_key() -> str | None:
    env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    return env.get("RENDER_API_KEY") or os.environ.get("RENDER_API_KEY")


def make_session(key: str) -> requests.Session:
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {key}"
    return session


def find_service(session: requests.Session) -> dict:
    """Locate our web service by its public URL (name alone could collide)."""
    resp = session.get(f"{API}/services", params={"limit": 100})
    resp.raise_for_status()
    services = [item["service"] for item in resp.json()]
    for svc in services:
        if svc.get("serviceDetails", {}).get("url") == SERVICE_URL:
            return svc
    names = ", ".join(s["name"] for s in services) or "(none)"
    raise LookupError(f"No service with URL {SERVICE_URL} found. Services visible to this key: {names}")


def fetch_logs(session: requests.Session, svc: dict, limit: int = 100) -> list[LogRecord]:
    resp = session.get(
        f"{API}/logs",
        params={"ownerId": svc["ownerId"], "resource": [svc["id"]], "limit": limit},
    )
    resp.raise_for_status()
    return [parse_entry(e) for e in resp.json().get("logs", [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and parse Render service logs")
    parser.add_argument("--limit", type=int, default=100, help="max log lines (default 100)")
    parser.add_argument("--grep", help="only show lines containing this substring")
    parser.add_argument("--errors", action="store_true",
                        help="only errors: level=error, HTTP status >= 400, or tracebacks")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print records as JSON lines")
    args = parser.parse_args()

    key = load_api_key()
    if not key:
        sys.exit(
            "RENDER_API_KEY is not set.\n"
            "Create one at Render Dashboard -> Account Settings -> API Keys,\n"
            "then add `RENDER_API_KEY=rnd_...` to the repo-root .env."
        )

    session = make_session(key)
    try:
        svc = find_service(session)
    except LookupError as exc:
        sys.exit(str(exc))
    print(f"# service: {svc['name']} ({svc['id']}), suspended={svc.get('suspended')}", file=sys.stderr)

    records = fetch_logs(session, svc, args.limit)
    shown = 0
    for rec in records:
        if args.errors and not is_error(rec):
            continue
        if args.grep and args.grep not in rec.message:
            continue
        print(json.dumps(asdict(rec)) if args.as_json else format_record(rec))
        shown += 1
    if not shown:
        print("(no matching log lines)", file=sys.stderr)


if __name__ == "__main__":
    main()
