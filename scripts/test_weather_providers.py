"""Test alternative weather-provider APIs, locally and from the Render backend.

Why: the app's weather stack is 100% Open-Meteo, which is keyless and
rate-limits/403s by source IP. Render free-tier services share egress IPs, so
Open-Meteo may fail from Render while working fine locally. This script probes
several providers from both places so we can pick a replacement that works
from Render.

Usage:
    uv run python scripts/test_weather_providers.py                # remote (Render)
    uv run python scripts/test_weather_providers.py --local        # this machine
    uv run python scripts/test_weather_providers.py --both         # side-by-side
    uv run python scripts/test_weather_providers.py --lat 40 --lon -75.2
    uv run python scripts/test_weather_providers.py --json         # raw JSON

Providers probed (see apps/backend/app/services/weather_probes.py):
    keyless:  open-meteo (forecast + archive, baseline), nws (US-only),
              met-norway
    key-based (status "no_key" until the key is set):
              openweathermap  (OPENWEATHERMAP_API_KEY)
              weatherapi      (WEATHERAPI_KEY)
              visual-crossing (VISUAL_CROSSING_KEY)
              tomorrow-io     (TOMORROW_IO_KEY or TOMORROW_IO)

Adding keys:
    locally  -> put KEY=value lines in the repo-root .env
    on Render -> Dashboard -> garden-app -> Environment -> add the same vars
                 (declared sync:false in render.yaml), then redeploy.

Remote mode needs JOB_TOKEN in the repo-root .env (same shared secret as the
other /api/admin/* endpoints; value visible in the Render dashboard env vars).

Interpreting results:
    - status "error" with HTTP 403/429 from --remote but "ok" from --local
      => the provider blocks/limits Render's shared egress IP. That is the
      failure mode we suspect for Open-Meteo.
    - "egress_ip" in the remote output is Render's actual outbound IP.
    - fields.et0=false => the provider can't feed the watering engine's ET0
      input directly; we'd need a Hargreaves-style estimate from temp_max/min.
    - status "no_key" => probe skipped, add the key and rerun.

Exit code: 0 if at least one non-Open-Meteo provider is fully ok (all contract
fields available) in the last run printed, else 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_URL = "https://garden-app-wa0b.onrender.com"

FIELD_COLS = ("precip_sum_daily", "temp_max", "temp_min",
              "precip_prob_forecast", "et0")


def run_remote(lat: float | None, lon: float | None) -> dict:
    token = dotenv_values(REPO_ROOT / ".env").get("JOB_TOKEN")
    if not token:
        sys.exit("JOB_TOKEN is not set in the repo-root .env "
                 "(copy it from the Render dashboard env vars).")
    params = {}
    if lat is not None:
        params["lat"] = lat
    if lon is not None:
        params["lon"] = lon
    # Long timeout: free-tier cold start + 8 sequential probes.
    resp = requests.post(f"{SERVICE_URL}/api/admin/test-weather-providers",
                         params=params, headers={"X-Job-Token": token},
                         timeout=180)
    resp.raise_for_status()
    return resp.json()


def run_local(lat: float | None, lon: float | None) -> dict:
    sys.path.insert(0, str(REPO_ROOT))
    from apps.backend.app.services.weather_probes import run_all_probes
    return run_all_probes(lat, lon)


def fmt_val(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def print_table(report: dict, label: str) -> None:
    print(f"\n=== {label}: ran from {report.get('ran_from')} "
          f"(egress IP {report.get('egress_ip') or 'unknown'}), "
          f"lat={report.get('lat')} lon={report.get('lon')} ===")
    headers = ["provider", "status", "HTTP", "ms"] + list(FIELD_COLS) + ["error"]
    rows = []
    for r in report["results"]:
        sample = r.get("sample") or {}
        rows.append(
            [r["provider"], r["status"], fmt_val(r.get("http_status")),
             fmt_val(r.get("latency_ms"))]
            + [fmt_val(sample.get(f)) for f in FIELD_COLS]
            + [(r.get("error") or "")[:60]]
        )
    widths = [max(len(h), *(len(row[i]) for row in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


def has_full_alternative(report: dict) -> bool:
    """True if a non-Open-Meteo provider is ok with every contract field."""
    for r in report["results"]:
        if r["provider"].startswith("open-meteo"):
            continue
        if r["status"] == "ok" and all(r["fields"].get(f) for f in FIELD_COLS):
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe alternative weather APIs locally and/or from Render")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--remote", action="store_true",
                      help="run probes on the Render backend (default)")
    mode.add_argument("--local", action="store_true",
                      help="run probes from this machine")
    mode.add_argument("--both", action="store_true",
                      help="run both and print side by side")
    parser.add_argument("--lat", type=float, help="latitude override")
    parser.add_argument("--lon", type=float, help="longitude override")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print raw JSON instead of tables")
    args = parser.parse_args()

    reports: list[tuple[str, dict]] = []
    if args.local or args.both:
        reports.append(("LOCAL", run_local(args.lat, args.lon)))
    if args.both or not args.local:
        reports.append(("RENDER", run_remote(args.lat, args.lon)))

    if args.as_json:
        print(json.dumps({label: rep for label, rep in reports}, indent=2))
    else:
        for label, rep in reports:
            print_table(rep, label)
        if len(reports) == 2:
            a, b = reports[0][1], reports[1][1]
            diff = []
            statuses_a = {r["provider"]: r["status"] for r in a["results"]}
            for r in b["results"]:
                sa = statuses_a.get(r["provider"])
                if sa != r["status"]:
                    diff.append(f"  {r['provider']}: {reports[0][0].lower()}="
                                f"{sa} vs {reports[1][0].lower()}={r['status']}")
            print("\n=== Differences (provider works one place, not the other) ===")
            print("\n".join(diff) if diff else "  none — same status everywhere")

    sys.exit(0 if has_full_alternative(reports[-1][1]) else 1)


if __name__ == "__main__":
    main()
