"""
Plant-ID baseline: what the current production path (Claude vision via
POST /api/identify) gets right on the same held-out iNaturalist photos the
local model is scored on — and what the hybrid would do (answer locally when
the calibrated confidence >= tau, otherwise ask Claude).

Uses identify.py's own prompt, image prep and reply parsing, and the
production VISION_MODEL, so the baseline is the real endpoint minus HTTP.

Scoring rule, applied identically to Claude and the local model: a prediction
is correct when its genus + species (first two words of the species key)
match the label. Claude names taxa in current nomenclature while library
labels can carry a trinomial; binomial matching keeps that from counting
against either side.

Each answer is cached in ml/data/processed/plantid_claude_baseline.csv
(committed), so re-runs only call the API for new images.

Run (needs ANTHROPIC_API_KEY; ~300 calls, well under $1 on Haiku):
    uv run --no-sync python ml/evaluation/plantid_claude_baseline.py --backbone mobileclip2_s0
"""
import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.evaluation.plantid_metrics import expected_calibration_error  # noqa: E402
from ml.features.plantid_data import species_key  # noqa: E402

RESULTS_DIR = _ROOT / 'ml' / 'experiments' / 'results'
CACHE_CSV = _ROOT / 'ml' / 'data' / 'processed' / 'plantid_claude_baseline.csv'
FIELDS = ['path', 'species_key', 'model', 'candidates', 'top1', 'top1_conf', 'latency_s']
SEED = 42


def binomial(key: str) -> str:
    return ' '.join(key.split()[:2])


def _ask_claude(path: Path) -> tuple[list[dict], float]:
    from apps.backend.app.routers.identify import MODES, _SYSTEM, _parse_reply, _prepare_image
    from apps.ml_service.app.llm_provider import complete_vision
    img_b64, media_type = _prepare_image(path.read_bytes())
    t0 = time.perf_counter()
    reply = complete_vision(_SYSTEM, MODES['identify'], img_b64, media_type)
    return _parse_reply(reply)['candidates'][:3], time.perf_counter() - t0


def _load_cache() -> dict[str, dict]:
    if not CACHE_CSV.exists():
        return {}
    with CACHE_CSV.open(newline='', encoding='utf-8') as f:
        return {r['path']: r for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backbone', required=True)
    ap.add_argument('--n', type=int, default=300)
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(_ROOT / '.env')
    from apps.ml_service.app.llm_provider import VISION_MODEL

    results = json.loads((RESULTS_DIR / 'plantid_backbones.json').read_text(encoding='utf-8'))
    tau = results[args.backbone]['tau']
    with (RESULTS_DIR / f'plantid_predictions_{args.backbone}.csv').open(newline='', encoding='utf-8') as f:
        local = list(csv.DictReader(f))
    sample = random.Random(SEED).sample(local, min(args.n, len(local)))

    cache = _load_cache()
    new_file = not CACHE_CSV.exists()
    with CACHE_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for i, r in enumerate(sample, 1):
            if r['path'] in cache:
                continue
            try:
                cands, latency = _ask_claude(_ROOT / r['path'])
            except Exception as exc:     # one bad call shouldn't sink a 300-image run
                print(f'  {r["path"]}: {exc}')
                continue
            top = cands[0] if cands else {}
            row = {
                'path': r['path'], 'species_key': r['species_key'], 'model': VISION_MODEL,
                'candidates': json.dumps([c.get('scientific_name') or '' for c in cands]),
                'top1': top.get('scientific_name') or '',
                'top1_conf': top.get('confidence') if top.get('confidence') is not None else '',
                'latency_s': f'{latency:.2f}',
            }
            writer.writerow(row)
            f.flush()
            cache[r['path']] = row
            print(f'[{i}/{len(sample)}] {r["species_key"]} -> {row["top1"]}')

    rows = [(r, cache[r['path']]) for r in sample if r['path'] in cache]
    n = len(rows)
    label = [binomial(r['species_key']) for r, _ in rows]
    claude_top1 = np.array([binomial(species_key(c['top1'])) == y for (_, c), y in zip(rows, label)])
    claude_top3 = np.array([y in {binomial(species_key(s)) for s in json.loads(c['candidates'])}
                            for (_, c), y in zip(rows, label)])
    local_ok = np.array([binomial(r['pred']) == y for (r, _), y in zip(rows, label)])
    local_conf = np.array([float(r['conf']) for r, _ in rows])
    crop = np.array([r['is_crop'] == '1' for r, _ in rows])

    has_conf = np.array([c['top1_conf'] != '' for _, c in rows])
    claude_conf = np.array([float(c['top1_conf']) if c['top1_conf'] != '' else 0.0 for _, c in rows])
    claude_ece = expected_calibration_error(
        np.clip(claude_conf[has_conf], 0, 1), claude_top1[has_conf]) if has_conf.any() else None

    use_local = local_conf >= tau if tau is not None else np.zeros(n, dtype=bool)
    hybrid_ok = np.where(use_local, local_ok, claude_top1)
    latency = np.array([float(c['latency_s']) for _, c in rows])

    def pct(x):
        return f'{x.mean() * 100:5.1f}%' if len(x) else '  —  '

    print(f'\n{n} test-half photos, local = {args.backbone} (tau={tau}), Claude = {rows[0][1]["model"] if rows else "?"}')
    print(f'{"":<22} {"all":>7} {"crops":>7}')
    print(f'{"local top-1":<22} {pct(local_ok):>7} {pct(local_ok[crop]):>7}')
    print(f'{"Claude top-1":<22} {pct(claude_top1):>7} {pct(claude_top1[crop]):>7}')
    print(f'{"Claude top-3":<22} {pct(claude_top3):>7} {pct(claude_top3[crop]):>7}')
    print(f'{"hybrid top-1":<22} {pct(hybrid_ok):>7} {pct(hybrid_ok[crop]):>7}')
    print(f'{"answered locally":<22} {pct(use_local):>7} {pct(use_local[crop]):>7}')
    print(f'local accuracy when it answers: {pct(local_ok[use_local])}')
    print(f'Claude self-reported confidence ECE: {claude_ece if claude_ece is None else round(claude_ece, 3)}')
    print(f'Claude latency: median {np.median(latency):.1f}s' if n else '')

    summary = {
        'backbone': args.backbone, 'tau': tau, 'n': n,
        'claude_model': rows[0][1]['model'] if rows else None,
        'local_top1': float(local_ok.mean()), 'claude_top1': float(claude_top1.mean()),
        'claude_top3': float(claude_top3.mean()), 'hybrid_top1': float(hybrid_ok.mean()),
        'local_share': float(use_local.mean()),
        'local_accuracy_when_answering': float(local_ok[use_local].mean()) if use_local.any() else None,
        'claude_confidence_ece': claude_ece,
        'claude_median_latency_s': float(np.median(latency)) if n else None,
        'crop': {
            'n': int(crop.sum()),
            'local_top1': float(local_ok[crop].mean()) if crop.any() else None,
            'claude_top1': float(claude_top1[crop].mean()) if crop.any() else None,
            'hybrid_top1': float(hybrid_ok[crop].mean()) if crop.any() else None,
        },
    }
    out = RESULTS_DIR / f'plantid_claude_baseline_{args.backbone}.json'
    out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f'\nsummary -> {out.relative_to(_ROOT)}')


if __name__ == '__main__':
    main()
