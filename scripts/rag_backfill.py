"""
Enrich PlantLibrary by querying the RAG system (ChromaDB) for plant-specific
passages and using an LLM to extract structured field data.

Designed for iterative use:
  1. --test first to validate prompt accuracy against known values
  2. --dry-run to preview what would be written
  3. Live run when accuracy gate is met (≥75% per field group)

Field groups:
  planting_calendar   — days_to_germination, days_to_harvest, sow_indoor_weeks,
                        direct_sow_offset, transplant_offset
  growing_conditions  — spacing_in, water, soil_ph_min/max, temp_min/max_f,
                        min_zone, max_zone, difficulty
  companion_planting  — good_neighbors, bad_neighbors
  how_to_grow         — how_to_grow (JSON with growing stages)
  faqs                — faqs (JSON Q&A array)

Usage:
    uv run python scripts/rag_backfill.py --test --field planting_calendar
    uv run python scripts/rag_backfill.py --dry-run --tamu-only
    uv run python scripts/rag_backfill.py --plant tomato --field growing_conditions --dry-run
    uv run python scripts/rag_backfill.py --tamu-only
    uv run python scripts/rag_backfill.py --confidence 0.65 --field planting_calendar
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'backend'))

from dotenv import load_dotenv
load_dotenv()


# ── Dynamic imports ─────────────────────────────────────────────────────────────

def _load_llm_provider():
    spec = importlib.util.spec_from_file_location(
        'llm_provider',
        os.path.join(_REPO_ROOT, 'apps', 'ml_service', 'app', 'llm_provider.py'),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_search_guides():
    spec = importlib.util.spec_from_file_location(
        'build_rag',
        os.path.join(_REPO_ROOT, 'scripts', 'build_rag.py'),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search_guides


# ── System prompt ───────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    'You are a plant data extraction assistant. Given passages from gardening guides, '
    'extract structured data into the exact JSON schema provided. '
    'Return ONLY valid JSON — no markdown, no explanation. '
    'Use null for any field not explicitly supported by the text. '
    'All numeric values must be numbers, not strings. '
    'Do not invent values — only extract what the text directly states.'
)

# ── Field group definitions ─────────────────────────────────────────────────────

FIELD_GROUPS = {
    'planting_calendar': {
        'fields': [
            'days_to_germination', 'days_to_harvest',
            'sow_indoor_weeks', 'direct_sow_offset', 'transplant_offset',
        ],
        'rag_queries': [
            '{plant} planting calendar sow germination',
            '{plant} frost dates transplant weeks',
        ],
        'extraction_schema': """{
  "days_to_germination": <int 3-30 or null, days from seed to sprout>,
  "days_to_harvest":     <int 20-300 or null, days from transplant or direct sow to harvest>,
  "sow_indoor_weeks":    <int 2-16 or null, weeks before last frost to start seeds indoors>,
  "direct_sow_offset":   <int -20 to +4 or null, weeks relative to last frost to direct sow; negative=weeks before frost>,
  "transplant_offset":   <int -4 to +8 or null, weeks after last frost to transplant outdoors>
}""",
        'json_fields': [],
        'validators': {
            'days_to_germination': lambda v: isinstance(v, int) and 2 <= v <= 60,
            'days_to_harvest':     lambda v: isinstance(v, int) and 10 <= v <= 400,
            'sow_indoor_weeks':    lambda v: isinstance(v, int) and 1 <= v <= 20,
            'direct_sow_offset':   lambda v: isinstance(v, int) and -25 <= v <= 8,
            'transplant_offset':   lambda v: isinstance(v, int) and -6 <= v <= 12,
        },
    },
    'growing_conditions': {
        'fields': [
            'spacing_in', 'water', 'soil_ph_min', 'soil_ph_max',
            'temp_min_f', 'temp_max_f', 'min_zone', 'max_zone', 'difficulty',
        ],
        'rag_queries': [
            '{plant} spacing planting distance rows',
            '{plant} watering soil pH temperature hardiness zone',
            '{plant} growing conditions requirements',
        ],
        'extraction_schema': """{
  "spacing_in":   <int 1-120 or null, inches between plants in row>,
  "water":        <"Low" | "Moderate" | "High" or null>,
  "soil_ph_min":  <float 4.0-8.5 or null>,
  "soil_ph_max":  <float 4.5-9.0 or null>,
  "temp_min_f":   <int 10-65 or null, minimum tolerated temperature in Fahrenheit>,
  "temp_max_f":   <int 70-115 or null, maximum tolerated temperature in Fahrenheit>,
  "min_zone":     <int 1-13 or null, minimum USDA hardiness zone>,
  "max_zone":     <int 1-13 or null, maximum USDA hardiness zone>,
  "difficulty":   <"Easy" | "Moderate" | "Hard" or null>
}""",
        'json_fields': [],
        'validators': {
            'spacing_in':  lambda v: isinstance(v, int) and 1 <= v <= 180,
            'water':       lambda v: v in ('Low', 'Moderate', 'High'),
            'soil_ph_min': lambda v: isinstance(v, (int, float)) and 3.0 <= v <= 9.0,
            'soil_ph_max': lambda v: isinstance(v, (int, float)) and 3.0 <= v <= 9.5,
            'temp_min_f':  lambda v: isinstance(v, int) and -20 <= v <= 70,
            'temp_max_f':  lambda v: isinstance(v, int) and 50 <= v <= 130,
            'min_zone':    lambda v: isinstance(v, int) and 1 <= v <= 13,
            'max_zone':    lambda v: isinstance(v, int) and 1 <= v <= 13,
            'difficulty':  lambda v: v in ('Easy', 'Moderate', 'Hard'),
        },
    },
    'companion_planting': {
        'fields': ['good_neighbors', 'bad_neighbors'],
        'rag_queries': [
            '{plant} companion plants good neighbors benefits',
            '{plant} bad companion plants avoid incompatible',
        ],
        'extraction_schema': """{
  "good_neighbors": <array of plant name strings (e.g. ["Basil", "Carrot"]) or null>,
  "bad_neighbors":  <array of plant name strings (e.g. ["Fennel", "Brassica"]) or null>
}""",
        'json_fields': ['good_neighbors', 'bad_neighbors'],
        'validators': {
            'good_neighbors': lambda v: isinstance(v, list) and len(v) > 0,
            'bad_neighbors':  lambda v: isinstance(v, list) and len(v) > 0,
        },
    },
    'how_to_grow': {
        'fields': ['how_to_grow'],
        'rag_queries': [
            '{plant} how to grow planting guide',
            '{plant} seedling care vegetative growing stages harvest',
        ],
        'extraction_schema': """{
  "how_to_grow": {
    "starting":   "<1-2 sentences on starting seeds or sourcing transplants>",
    "seedling":   "<1-2 sentences on seedling care and thinning>",
    "vegetative": "<1-2 sentences on fertilizing, watering, and support during growth>",
    "flowering":  "<1-2 sentences on pollination, fruit set, or flowering care>",
    "harvest":    "<1-2 sentences on when and how to harvest>"
  }
}""",
        'json_fields': ['how_to_grow'],
        'validators': {
            'how_to_grow': lambda v: (
                isinstance(v, dict)
                and all(k in v for k in ('starting', 'seedling', 'vegetative', 'flowering', 'harvest'))
                and all(isinstance(v[k], str) and len(v[k]) > 10 for k in v)
            ),
        },
    },
    'faqs': {
        'fields': ['faqs'],
        'rag_queries': [
            '{plant} common problems tips growing FAQ',
            '{plant} pests diseases troubleshooting',
        ],
        'extraction_schema': """{
  "faqs": [
    {"q": "<common question about growing this plant>", "a": "<practical answer>"},
    {"q": "...", "a": "..."}
  ]
}""",
        'json_fields': ['faqs'],
        'validators': {
            'faqs': lambda v: (
                isinstance(v, list)
                and len(v) >= 2
                and all(isinstance(x, dict) and 'q' in x and 'a' in x for x in v)
            ),
        },
    },
}

# Plants covered by TAMU guides (used with --tamu-only)
TAMU_PLANTS = {
    'artichoke', 'asparagus', 'beet', 'carrot', 'cilantro', 'cole crops',
    'collard', 'collard greens', 'cucumber', 'dill', 'eggplant', 'ginger',
    'green bean', 'melon', 'okra', 'onion', 'pepper', 'bell pepper',
    'jalapeno pepper', 'potato', 'radish', 'rosemary', 'spinach', 'squash',
    'sugar snap pea', 'sweet corn', 'sweet potato', 'tomato', 'tomatillo',
    'turnip', 'pinto bean', 'broccoli', 'cabbage', 'cantaloupe', 'cauliflower',
    'celery', 'chinese cabbage', 'garlic', 'honeydew melon', 'kohlrabi',
    'lettuce', 'mustard green', 'parsley', 'pumpkin', 'southern pea',
    'swiss chard', 'watermelon', 'seedless watermelon', 'pickling cucumber',
}


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _blank(val):
    return val is None or (isinstance(val, str) and val.strip() == '')


def _is_valid_json_field(val):
    if not val:
        return False
    try:
        parsed = json.loads(val) if isinstance(val, str) else val
        if isinstance(parsed, list):
            return len(parsed) > 0
        if isinstance(parsed, dict):
            return len(parsed) > 0
        return False
    except Exception:
        return False


def _deduplicate_passages(passages):
    """Remove near-duplicate passages (same first 100 chars)."""
    seen = set()
    unique = []
    for p in passages:
        key = p['text'][:100].strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _jaccard(a, b):
    """Jaccard similarity between two lists treated as sets (case-insensitive)."""
    if not a or not b:
        return 0.0
    sa = {x.lower() for x in a}
    sb = {x.lower() for x in b}
    intersection = len(sa & sb)
    union = len(sa | sb)
    return intersection / union if union else 0.0


def _numeric_match(known, extracted, pct=0.2, abs_tol=5):
    """True if extracted is within pct% or abs_tol of known."""
    if known is None or extracted is None:
        return False
    try:
        diff = abs(float(known) - float(extracted))
        threshold = max(abs(float(known)) * pct, abs_tol)
        return diff <= threshold
    except (TypeError, ValueError):
        return False


# ── LLM call ────────────────────────────────────────────────────────────────────

def llm_complete(system, user, llm_mod):
    return llm_mod.complete(system, user)


# ── RAG extraction ───────────────────────────────────────────────────────────────

def extract_fields_via_rag(plant_name, group_def, args, search_guides, llm_mod):
    """
    Query RAG for plant passages, call LLM for structured extraction.
    Returns (extracted_dict_or_None, max_rag_score).
    """
    passages = []
    for query_template in group_def['rag_queries']:
        query = query_template.format(plant=plant_name)
        results = search_guides(query, plant_name=plant_name, n_results=args.n_results)
        passages.extend(results)

    if not passages:
        return None, 0.0

    passages = sorted(passages, key=lambda r: r['score'], reverse=True)
    passages = _deduplicate_passages(passages)[:args.n_results]

    max_score = passages[0]['score'] if passages else 0.0
    if max_score < args.confidence:
        return None, max_score

    context = '\n\n---\n\n'.join(
        f"[Source: {r['source']}, Score: {r['score']:.2f}]\n{r['text']}"
        for r in passages
    )

    user_prompt = (
        f'Plant: {plant_name}\n\n'
        f'Gardening guide excerpts:\n{context}\n\n'
        f'Extract into this exact JSON schema:\n{group_def["extraction_schema"]}'
    )

    raw = llm_complete(_SYSTEM_PROMPT, user_prompt, llm_mod).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw), max_score
    except json.JSONDecodeError as e:
        print(f'    JSON parse error: {e}')
        print(f'    Raw (first 300): {raw[:300]}')
        return None, max_score


# ── Validation ──────────────────────────────────────────────────────────────────

def validate_extracted(extracted, group_def):
    """
    Apply per-field validators. Returns dict of field -> (value, valid_bool).
    Only returns fields that exist in extracted and are not None.
    """
    results = {}
    validators = group_def.get('validators', {})
    for field in group_def['fields']:
        val = extracted.get(field)
        if val is None:
            continue
        validator = validators.get(field)
        valid = validator(val) if validator else True
        results[field] = (val, valid)
    return results


# ── Merge ────────────────────────────────────────────────────────────────────────

def merge_into_entry(entry, validated, group_def, dry_run, force):
    """
    Fill-in-blank merge of validated extracted values into a PlantLibrary entry.
    Returns (fields_written, fields_skipped).
    """
    written = []
    skipped = []
    json_fields = set(group_def['json_fields'])

    for field, (value, valid) in validated.items():
        if not valid:
            skipped.append((field, 'validation_failed'))
            continue

        current = getattr(entry, field, None)
        is_json = field in json_fields

        if is_json:
            already_set = _is_valid_json_field(current)
        else:
            already_set = not _blank(current)

        if already_set and not force:
            skipped.append((field, 'already_populated'))
            continue

        if not dry_run:
            if is_json:
                setattr(entry, field, json.dumps(value) if not isinstance(value, str) else value)
            else:
                setattr(entry, field, value)

        written.append(field)

    return written, skipped


# ── Accuracy testing ─────────────────────────────────────────────────────────────

def _compare_values(field, known, extracted, group_def):
    """Compare a known value to an extracted value. Returns (match: bool, detail: str)."""
    json_fields = set(group_def['json_fields'])

    if field in json_fields:
        if field in ('good_neighbors', 'bad_neighbors'):
            known_list = json.loads(known) if isinstance(known, str) else known
            sim = _jaccard(known_list, extracted)
            match = sim >= 0.4
            return match, f'jaccard={sim:.2f}'
        elif field == 'how_to_grow':
            known_d = json.loads(known) if isinstance(known, str) else known
            if not isinstance(extracted, dict) or not isinstance(known_d, dict):
                return False, 'type_mismatch'
            keys_match = set(extracted.keys()) >= {'starting', 'seedling', 'vegetative', 'flowering', 'harvest'}
            return keys_match, f'has_required_keys={keys_match}'
        elif field == 'faqs':
            extracted_list = extracted if isinstance(extracted, list) else []
            match = len(extracted_list) >= 2
            return match, f'n_faqs={len(extracted_list)}'
        return False, 'unknown_json_field'
    else:
        # Scalar comparison
        known_val = known
        try:
            known_val = int(known) if isinstance(known, (int, float)) else known
        except (ValueError, TypeError):
            pass

        if isinstance(known_val, (int, float)):
            match = _numeric_match(known_val, extracted)
            return match, f'known={known_val}, extracted={extracted}'
        else:
            match = str(known_val).lower().strip() == str(extracted).lower().strip()
            return match, f'known={known_val!r}, extracted={extracted!r}'


def run_test_mode(group_name, group_def, args, db, search_guides, llm_mod):
    """
    Run accuracy test: extract values for plants that already have known values,
    compare extracted vs known, report accuracy per field.
    """
    from app.db.models import PlantLibrary

    print(f'\n{"="*60}')
    print(f'TEST MODE — field group: {group_name}')
    print(f'{"="*60}')

    # Find plants with at least one non-null known value for this group
    scalar_fields = [f for f in group_def['fields'] if f not in group_def['json_fields']]
    json_fields   = group_def['json_fields']

    test_plants = []
    all_entries = db.query(PlantLibrary).all()
    for entry in all_entries:
        has_known = False
        for f in scalar_fields:
            if not _blank(getattr(entry, f, None)):
                has_known = True
                break
        for f in json_fields:
            if _is_valid_json_field(getattr(entry, f, None)):
                has_known = True
                break
        if has_known:
            test_plants.append(entry)

    if not test_plants:
        print('  No plants with known values found for this group — nothing to test.')
        return

    if args.plant:
        name_lower = args.plant.lower()
        test_plants = [e for e in test_plants if args.plant.lower() in e.name.lower()]

    if args.limit:
        test_plants = test_plants[:args.limit]

    print(f'  Testing on {len(test_plants)} plant(s) with known values...\n')

    results = []
    field_totals = {f: {'match': 0, 'total': 0} for f in group_def['fields']}

    for entry in test_plants:
        print(f'  [{entry.name}] querying RAG...', end='', flush=True)
        extracted, max_score = extract_fields_via_rag(
            entry.name, group_def, args, search_guides, llm_mod
        )
        if extracted is None:
            print(f' skipped (score={max_score:.2f} < threshold={args.confidence})')
            continue
        print(f' score={max_score:.2f}')

        for field in group_def['fields']:
            known = getattr(entry, field, None)
            is_json = field in group_def['json_fields']

            # Skip fields that aren't populated in this plant
            if is_json and not _is_valid_json_field(known):
                continue
            if not is_json and _blank(known):
                continue

            extr_val = extracted.get(field)
            if extr_val is None:
                match = False
                detail = 'not_extracted'
            else:
                known_parsed = json.loads(known) if (is_json and isinstance(known, str)) else known
                match, detail = _compare_values(field, known_parsed, extr_val, group_def)

            field_totals[field]['total'] += 1
            if match:
                field_totals[field]['match'] += 1

            results.append({
                'plant':     entry.name,
                'field':     field,
                'known':     known,
                'extracted': extr_val,
                'rag_score': max_score,
                'match':     match,
                'detail':    detail,
            })

            status = '✓' if match else '✗'
            print(f'    {status} {field}: {detail}')

        time.sleep(0.3)  # avoid hammering LLM

    # Summary
    print(f'\n{"─"*60}')
    print(f'ACCURACY SUMMARY — {group_name}')
    print(f'{"─"*60}')
    overall_match = 0
    overall_total = 0
    field_accuracy = {}
    gate_passed = True
    for field, counts in field_totals.items():
        if counts['total'] == 0:
            continue
        acc = counts['match'] / counts['total']
        field_accuracy[field] = acc
        overall_match += counts['match']
        overall_total += counts['total']
        gate = '✓ PASS' if acc >= 0.75 else '✗ FAIL'
        if acc < 0.75:
            gate_passed = False
        print(f'  {field:30s}  {acc*100:5.1f}%  ({counts["match"]}/{counts["total"]})  {gate}')

    if overall_total > 0:
        overall_acc = overall_match / overall_total
        print(f'\n  Overall: {overall_acc*100:.1f}%  ({overall_match}/{overall_total})')
        print(f'\n  Gate (≥75% per field): {"✓ PASSED — safe to run live" if gate_passed else "✗ FAILED — refine prompts before bulk update"}')

    # Write JSON log
    log_dir = os.path.join(_REPO_ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f'rag_backfill_test_{group_name}_{ts}.json')
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'field_group': group_name,
        'n_tested': len([r for r in results]),
        'confidence_threshold': args.confidence,
        'results': results,
        'accuracy': field_accuracy,
        'overall_accuracy': overall_match / overall_total if overall_total else None,
        'gate_passed': gate_passed,
    }
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, default=str)
    print(f'\n  Log saved: {log_path}')


# ── Live run ─────────────────────────────────────────────────────────────────────

def run_backfill(group_name, group_def, args, db, search_guides, llm_mod):
    """
    Main backfill loop: for each plant, query RAG, extract, validate, merge.
    """
    from app.db.models import PlantLibrary

    mode = 'DRY RUN' if args.dry_run else 'LIVE'
    print(f'\n{"="*60}')
    print(f'{mode} — field group: {group_name}')
    print(f'{"="*60}')

    query = db.query(PlantLibrary)
    if args.plant:
        query = query.filter(PlantLibrary.name.ilike(f'%{args.plant}%'))
    if args.tamu_only:
        # Filter in Python since TAMU_PLANTS is a Python set
        all_entries = query.all()
        entries = [e for e in all_entries if e.name.lower() in TAMU_PLANTS]
    else:
        entries = query.all()

    if args.limit:
        entries = entries[:args.limit]

    print(f'  Processing {len(entries)} plant(s)...\n')

    log_dir = os.path.join(_REPO_ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f'rag_backfill_{group_name}_{ts}.jsonl')

    total_written = 0
    total_skipped_confidence = 0
    total_skipped_populated = 0
    total_validation_failed = 0

    with open(log_path, 'a', encoding='utf-8') as log_f:
        for entry in entries:
            print(f'  [{entry.name}] ', end='', flush=True)

            extracted, max_score = extract_fields_via_rag(
                entry.name, group_def, args, search_guides, llm_mod
            )

            if extracted is None:
                if max_score < args.confidence:
                    print(f'skipped (RAG score {max_score:.2f} < {args.confidence})')
                    total_skipped_confidence += 1
                else:
                    print(f'skipped (JSON parse error, score {max_score:.2f})')
                log_f.write(json.dumps({
                    'ts': datetime.now().isoformat(),
                    'plant_id': entry.id,
                    'plant': entry.name,
                    'field_group': group_name,
                    'rag_top_score': max_score,
                    'extracted': None,
                    'fields_written': [],
                    'fields_skipped': ['low_score_or_parse_error'],
                    'dry_run': args.dry_run,
                }, default=str) + '\n')
                continue

            validated = validate_extracted(extracted, group_def)
            written, skipped = merge_into_entry(
                entry, validated, group_def, args.dry_run, args.force
            )

            val_fails = [f for f, (_, ok) in validated.items() if not ok]
            already_pop = [f for f, reason in skipped if reason == 'already_populated']
            total_written += len(written)
            total_skipped_populated += len(already_pop)
            total_validation_failed += len(val_fails)

            if written:
                print(f'score={max_score:.2f}  wrote: {written}')
            elif already_pop:
                print(f'score={max_score:.2f}  already populated: {already_pop}')
            elif val_fails:
                print(f'score={max_score:.2f}  validation failed: {val_fails}')
            else:
                print(f'score={max_score:.2f}  nothing to write')

            log_f.write(json.dumps({
                'ts': datetime.now().isoformat(),
                'plant_id': entry.id,
                'plant': entry.name,
                'field_group': group_name,
                'rag_top_score': max_score,
                'rag_n_results': args.n_results,
                'extracted': extracted,
                'fields_written': written,
                'fields_skipped': skipped,
                'dry_run': args.dry_run,
            }, default=str) + '\n')

            if not args.dry_run and written:
                db.commit()

            time.sleep(0.2)

    print(f'\n{"─"*60}')
    print(f'Done — {group_name}')
    print(f'  Fields written:         {total_written}')
    print(f'  Skipped (populated):    {total_skipped_populated}')
    print(f'  Skipped (low score):    {total_skipped_confidence}')
    print(f'  Skipped (validation):   {total_validation_failed}')
    if not args.dry_run:
        print(f'  Log: {log_path}')
    else:
        print(f'  [DRY RUN — no DB writes]')


# ── CLI ──────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description='Backfill PlantLibrary fields using RAG-sourced LLM extraction'
    )
    p.add_argument('--plant',      default=None,
                   help='Process only plants whose name contains this string')
    p.add_argument('--field',      default='all',
                   choices=list(FIELD_GROUPS.keys()) + ['all'],
                   help='Field group to process (default: all)')
    p.add_argument('--dry-run',    action='store_true',
                   help='Show extractions without writing to DB')
    p.add_argument('--test',       action='store_true',
                   help='Test accuracy against known values (no DB writes)')
    p.add_argument('--confidence', type=float, default=0.6,
                   help='Minimum RAG cosine score to attempt extraction (default: 0.6)')
    p.add_argument('--n-results',  type=int, default=5,
                   help='RAG passages to retrieve per query (default: 5)')
    p.add_argument('--force',      action='store_true',
                   help='Overwrite existing non-null values')
    p.add_argument('--tamu-only',  action='store_true',
                   help='Only process plants covered by TAMU guides')
    p.add_argument('--limit',      type=int, default=None,
                   help='Process at most N plants (useful for spot checks)')
    return p.parse_args()


def main():
    args = parse_args()

    # Load modules
    try:
        llm_mod = _load_llm_provider()
    except Exception as e:
        print(f'ERROR loading llm_provider: {e}')
        sys.exit(1)

    try:
        search_guides = _load_search_guides()
    except Exception as e:
        print(f'ERROR loading build_rag: {e}')
        sys.exit(1)

    # Test RAG availability
    test_results = search_guides('tomato planting', plant_name='Tomato', n_results=1)
    if not test_results:
        print('WARNING: RAG database returned no results. Run scripts/build_rag.py first.')
        print('         Continuing — may produce null extractions.')
    else:
        print(f'RAG OK — top score for test query: {test_results[0]["score"]:.3f}')

    # DB session
    from app.db.session import SessionLocal
    db = SessionLocal()

    try:
        groups_to_run = (
            list(FIELD_GROUPS.keys()) if args.field == 'all'
            else [args.field]
        )

        for group_name in groups_to_run:
            group_def = FIELD_GROUPS[group_name]
            if args.test:
                run_test_mode(group_name, group_def, args, db, search_guides, llm_mod)
            else:
                run_backfill(group_name, group_def, args, db, search_guides, llm_mod)
    finally:
        db.close()

    print('\nAll done.')


if __name__ == '__main__':
    main()
