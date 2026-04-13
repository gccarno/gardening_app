"""
Enrich PlantLibrary with data extracted from Texas A&M University vegetable guides.

TAMU publishes two authoritative PDF guide series:
  1. Easy Gardening Series (~27 plants) — consumer-focused, Texas climate emphasis
  2. Commercial Crop Guides (~40 plants) — detailed production data

Since PDFs contain narrative/tabular text with no consistent HTML structure,
this script uses a hybrid approach:
  1. Download PDFs to scripts/tamu_pdfs/ (skips existing files)
  2. Extract text with pdfplumber
  3. Send text to claude-haiku to extract structured PlantLibrary fields as JSON
  4. Fill-in-blank merge into PlantLibrary

Strategy:
  - Never overwrites existing non-null values
  - Plants matched by common name (exact then partial)
  - --dry-run previews extracted JSON without writing
  - --plant filters to a single plant name for testing

Usage:
    python scripts/tamu_sync.py --dry-run
    python scripts/tamu_sync.py --plant tomatoes --dry-run
    python scripts/tamu_sync.py
    python scripts/tamu_sync.py --force    # re-extract even if notes already set
    python scripts/tamu_sync.py --download-only  # just download PDFs

Requirements:
    pdfplumber, anthropic (both in pyproject.toml)
    ANTHROPIC_API_KEY in .env
"""
import argparse
import json
import logging
import os
import re
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'backend'))

from dotenv import load_dotenv
load_dotenv()

# gemma4:e2b is too large for batch extraction; fall back to gemma3:4b for Ollama
if os.environ.get('LLM_PROVIDER', '').lower() == 'ollama':
    os.environ['LLM_MODEL'] = os.environ.get('TAMU_LLM_MODEL', 'gemma4:e2b')

import requests

LOG_DIR = os.path.join(_REPO_ROOT, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'tamu_sync.log')

logger = logging.getLogger('tamu_sync')

PDF_DIR = os.path.join(os.path.dirname(__file__), 'tamu_pdfs')

_EASY_BASE = 'https://aggie-horticulture.tamu.edu/wp-content/uploads/sites/10/2013/09'
_COMM_BASE = 'https://aggie-horticulture.tamu.edu/vegetable/wp-content/uploads/sites/10/2011/10'

# (plant_name, pdf_filename_or_url, series)
TAMU_PDFS = [
    # ── Easy Gardening Series ──────────────────────────────────────────────
    ('Artichoke',       f'{_EASY_BASE}/EHT-065.pdf',                                  'easy'),
    ('Asparagus',       f'{_EASY_BASE}/EHT-066.pdf',                                  'easy'),
    ('Beet',            f'{_EASY_BASE}/EHT-050.pdf',                                  'easy'),
    ('Carrot',          f'{_EASY_BASE}/EHT-035.pdf',                                  'easy'),
    ('Cilantro',        f'{_EASY_BASE}/EHT-032.pdf',                                  'easy'),
    ('Cole Crops',      f'{_EASY_BASE}/EHT-067.pdf',                                  'easy'),
    ('Collard Greens',  f'{_EASY_BASE}/EHT-051.pdf',                                  'easy'),
    ('Cucumber',        f'{_EASY_BASE}/EHT-033.pdf',                                  'easy'),
    ('Dill',            f'{_EASY_BASE}/EHT-053.pdf',                                  'easy'),
    ('Eggplant',        f'{_EASY_BASE}/EHT-036.pdf',                                  'easy'),
    ('Ginger',          'https://aggie-horticulture.tamu.edu/wp-content/uploads/sites/10/2013/09/EHT-014-Easy-Gardening-Ginger.pdf', 'easy'),
    ('Green Bean',      f'{_EASY_BASE}/EHT-057.pdf',                                  'easy'),
    ('Melon',           f'{_EASY_BASE}/EHT-034.pdf',                                  'easy'),
    ('Okra',            f'{_EASY_BASE}/EHT-058.pdf',                                  'easy'),
    ('Onion',           f'{_EASY_BASE}/EHT-037.pdf',                                  'easy'),
    ('Pepper',          f'{_EASY_BASE}/EHT-038.pdf',                                  'easy'),
    ('Potato',          f'{_EASY_BASE}/EHT-068.pdf',                                  'easy'),
    ('Radish',          f'{_EASY_BASE}/EHT-042.pdf',                                  'easy'),
    ('Rosemary',        f'{_EASY_BASE}/EHT039.pdf',                                   'easy'),
    ('Spinach',         f'{_EASY_BASE}/EHT-040.pdf',                                  'easy'),
    ('Squash',          f'{_EASY_BASE}/EHT-041.pdf',                                  'easy'),
    ('Sugar Snap Pea',  'https://aggie-horticulture.tamu.edu/wp-content/uploads/sites/10/2013/09/EHT-015-Easy-Gardening-Sugar-Snap-Peas.pdf', 'easy'),
    ('Sweet Corn',      f'{_EASY_BASE}/EHT-044.pdf',                                  'easy'),
    ('Sweet Potato',    'https://aggie-horticulture.tamu.edu/wp-content/uploads/sites/10/2013/09/EHT-026-Easy-Gardening-Sweet-Potatoes.pdf', 'easy'),
    ('Tomato',          f'{_EASY_BASE}/EHT-043.pdf',                                  'easy'),
    ('Tomatillo',       'https://aggie-horticulture.tamu.edu/wp-content/uploads/sites/10/2013/09/EHT-025-Easy-Gardening-Tomatillos.pdf', 'easy'),
    ('Turnip',          f'{_EASY_BASE}/EHT-061.pdf',                                  'easy'),
    # ── Commercial Crop Guides ─────────────────────────────────────────────
    ('Asparagus',       f'{_COMM_BASE}/asparagus.pdf',         'commercial'),
    ('Green Bean',      f'{_COMM_BASE}/bean.pdf',              'commercial'),
    ('Pinto Bean',      f'{_COMM_BASE}/pintobean.pdf',         'commercial'),
    ('Beet',            f'{_COMM_BASE}/beets1.pdf',            'commercial'),
    ('Broccoli',        f'{_COMM_BASE}/broccoli.pdf',          'commercial'),
    ('Cabbage',         f'{_COMM_BASE}/cabbage1.pdf',          'commercial'),
    ('Cantaloupe',      f'{_COMM_BASE}/cantaloupe.pdf',        'commercial'),
    ('Carrot',          f'{_COMM_BASE}/carrot1.pdf',           'commercial'),
    ('Cauliflower',     f'{_COMM_BASE}/cauliflower3.pdf',      'commercial'),
    ('Celery',          f'{_COMM_BASE}/celery2.pdf',           'commercial'),
    ('Chinese Cabbage', f'{_COMM_BASE}/chinesecabbage.pdf',    'commercial'),
    ('Cilantro',        f'{_COMM_BASE}/cilantro.pdf',          'commercial'),
    ('Collard',         f'{_COMM_BASE}/collardskale.pdf',      'commercial'),
    ('Cucumber',        f'{_COMM_BASE}/slicers.pdf',           'commercial'),
    ('Pickling Cucumber', f'{_COMM_BASE}/pickles.pdf',         'commercial'),
    ('Eggplant',        f'{_COMM_BASE}/eggplant.pdf',          'commercial'),
    ('Garlic',          f'{_COMM_BASE}/garlic.pdf',            'commercial'),
    ('Honeydew Melon',  f'{_COMM_BASE}/honeydew.pdf',          'commercial'),
    ('Kohlrabi',        f'{_COMM_BASE}/kohlrabi.pdf',          'commercial'),
    ('Lettuce',         f'{_COMM_BASE}/lettuce.pdf',           'commercial'),
    ('Mustard Green',   f'{_COMM_BASE}/mustardgreens1.pdf',    'commercial'),
    ('Okra',            f'{_COMM_BASE}/okra.pdf',              'commercial'),
    ('Onion',           f'{_COMM_BASE}/onion1.pdf',            'commercial'),
    ('Parsley',         f'{_COMM_BASE}/parsley.pdf',           'commercial'),
    ('Bell Pepper',     f'{_COMM_BASE}/pepper-Bell.pdf',       'commercial'),
    ('Jalapeno Pepper', f'{_COMM_BASE}/pepper-jalapeno.pdf',   'commercial'),
    ('Potato',          f'{_COMM_BASE}/potato.pdf',            'commercial'),
    ('Pumpkin',         f'{_COMM_BASE}/pumpkin.pdf',           'commercial'),
    ('Radish',          f'{_COMM_BASE}/radish.pdf',            'commercial'),
    ('Southern Pea',    f'{_COMM_BASE}/southernpea.pdf',       'commercial'),
    ('Spinach',         f'{_COMM_BASE}/spinach.pdf',           'commercial'),
    ('Squash',          f'{_COMM_BASE}/squash.pdf',            'commercial'),
    ('Sweet Corn',      f'{_COMM_BASE}/sweetcorn.pdf',         'commercial'),
    ('Sweet Potato',    f'{_COMM_BASE}/sweetpotato.pdf',       'commercial'),
    ('Swiss Chard',     f'{_COMM_BASE}/swisschard.pdf',        'commercial'),
    ('Tomato',          f'{_COMM_BASE}/tomato.pdf',            'commercial'),
    ('Turnip',          f'{_COMM_BASE}/turnipgreens.pdf',      'commercial'),
    ('Watermelon',      f'{_COMM_BASE}/watermelon.pdf',        'commercial'),
    ('Seedless Watermelon', f'{_COMM_BASE}/seedlesswatermelon.pdf', 'commercial'),
]

# JSON schema the LLM should return
_EXTRACTION_SCHEMA = """{
  "days_to_germination": <int or null>,
  "days_to_harvest": <int or null>,
  "spacing_in": <int or null>,
  "soil_ph_min": <float or null>,
  "soil_ph_max": <float or null>,
  "soil_type": <"Clay" | "Loam" | "Sandy loam" | "Sandy" or null>,
  "temp_min_f": <int or null, coldest tolerated temperature in F>,
  "temp_max_f": <int or null, hottest tolerated temperature in F>,
  "min_zone": <int 1-13 or null>,
  "max_zone": <int 1-13 or null>,
  "sow_indoor_weeks": <int or null, weeks before last frost to start indoors>,
  "direct_sow_offset": <int or null, weeks relative to last frost; negative=before frost>,
  "transplant_offset": <int or null, weeks after last frost to transplant out>,
  "difficulty": <"Easy" | "Moderate" | "Hard" or null>,
  "how_to_grow": <object or null with keys: "starting", "seedling", "vegetative", "flowering", "harvest" — each a 1-2 sentence string>,
  "good_neighbors": <array of plant name strings or null>,
  "bad_neighbors": <array of plant name strings or null>,
  "faqs": <array of {"q": str, "a": str} objects or null>
}"""

_SYSTEM_PROMPT = (
    'You are a plant data extraction assistant. Given the text of a gardening guide, '
    'extract structured data into the exact JSON schema provided. '
    'Return ONLY valid JSON — no markdown, no explanation. '
    'Use null for any field not mentioned in the text. '
    'All numeric values must be numbers, not strings.'
)


# ── PDF download ───────────────────────────────────────────────────────────────

def download_pdf(plant_name, url, series):
    """Download a PDF if not already present. Returns local path or None."""
    os.makedirs(PDF_DIR, exist_ok=True)
    safe_name = re.sub(r'[^\w-]', '_', plant_name.lower())
    filename = f'{series}_{safe_name}.pdf'
    dest = os.path.join(PDF_DIR, filename)

    if os.path.exists(dest):
        return dest

    try:
        r = requests.get(url, timeout=30,
                         headers={'User-Agent': 'GardenApp/1.0 (educational)'})
        if r.status_code == 404:
            logger.warning('404 not found: %s', url)
            return None
        r.raise_for_status()
        with open(dest, 'wb') as f:
            f.write(r.content)
        logger.info('downloaded %s (%d KB)', filename, len(r.content) // 1024)
        return dest
    except Exception as e:
        logger.error('download error %s: %s', url, e)
        return None


# ── PDF text extraction ────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path):
    """Extract all text from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError('pdfplumber required: uv add pdfplumber')

    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
    except Exception as e:
        logger.error('PDF read error %s: %s', pdf_path, e)
        return ''

    return '\n\n'.join(text_parts)


# ── LLM extraction ─────────────────────────────────────────────────────────────

def _llm_complete(system, user):
    """Call llm_provider.complete via the ml_service module."""
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        'llm_provider',
        os.path.join(_REPO_ROOT, 'apps', 'ml_service', 'app', 'llm_provider.py'),
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod.complete(system, user)


def extract_fields_with_llm(plant_name, pdf_text):
    """Use the configured local LLM to extract structured fields from PDF text. Returns dict or None."""

    # Truncate very long PDFs to ~6000 chars
    if len(pdf_text) > 6000:
        pdf_text = pdf_text[:6000] + '\n[... truncated ...]'

    user_prompt = (
        f'Plant: {plant_name}\n\n'
        f'Guide text:\n{pdf_text}\n\n'
        f'Extract into this exact JSON schema:\n{_EXTRACTION_SCHEMA}'
    )

    raw = _llm_complete(_SYSTEM_PROMPT, user_prompt).strip()

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error('JSON parse error: %s', e)
        logger.debug('Raw LLM response: %s', raw[:300])
        return None


# ── Library matching ───────────────────────────────────────────────────────────

def find_library_entry(plant_name, all_entries):
    """Find a PlantLibrary entry by name (exact then partial, case-insensitive)."""
    name_lower = plant_name.lower()
    for entry in all_entries:
        if entry.name.lower() == name_lower:
            return entry
    for entry in all_entries:
        if name_lower in entry.name.lower() or entry.name.lower() in name_lower:
            return entry
    return None


# ── Merge ──────────────────────────────────────────────────────────────────────

def _blank(val):
    return val is None or (isinstance(val, str) and val.strip() == '')


def _is_valid_how_to_grow(val):
    if not val:
        return False
    try:
        d = json.loads(val) if isinstance(val, str) else val
        return bool(d)
    except Exception:
        return False


def merge_tamu_data(entry, extracted, dry_run):
    """Fill-in-blank merge of LLM-extracted TAMU data into PlantLibrary entry."""
    changed = []

    def _set(field, value):
        if value is None:
            return
        current = getattr(entry, field, None)
        if _blank(current):
            changed.append((field, value))
            if not dry_run:
                setattr(entry, field, value)

    def _set_json(field, value):
        """Set a JSON-encoded field if not already populated."""
        if value is None:
            return
        current = getattr(entry, field, None)
        if _blank(current):
            encoded = json.dumps(value) if not isinstance(value, str) else value
            changed.append((field, encoded))
            if not dry_run:
                setattr(entry, field, encoded)

    _set('days_to_germination', extracted.get('days_to_germination'))
    _set('days_to_harvest',     extracted.get('days_to_harvest'))
    _set('spacing_in',          extracted.get('spacing_in'))
    _set('soil_ph_min',         extracted.get('soil_ph_min'))
    _set('soil_ph_max',         extracted.get('soil_ph_max'))
    _set('soil_type',           extracted.get('soil_type'))
    _set('temp_min_f',          extracted.get('temp_min_f'))
    _set('temp_max_f',          extracted.get('temp_max_f'))
    _set('min_zone',            extracted.get('min_zone'))
    _set('max_zone',            extracted.get('max_zone'))
    _set('sow_indoor_weeks',    extracted.get('sow_indoor_weeks'))
    _set('direct_sow_offset',   extracted.get('direct_sow_offset'))
    _set('transplant_offset',   extracted.get('transplant_offset'))
    _set('difficulty',          extracted.get('difficulty'))

    # JSON fields
    how_to_grow = extracted.get('how_to_grow')
    if how_to_grow and not _is_valid_how_to_grow(getattr(entry, 'how_to_grow', None)):
        _set_json('how_to_grow', how_to_grow)

    good = extracted.get('good_neighbors')
    if good and _blank(getattr(entry, 'good_neighbors', None)):
        _set_json('good_neighbors', good)

    bad = extracted.get('bad_neighbors')
    if bad and _blank(getattr(entry, 'bad_neighbors', None)):
        _set_json('bad_neighbors', bad)

    faqs = extracted.get('faqs')
    if faqs and _blank(getattr(entry, 'faqs', None)):
        _set_json('faqs', faqs)

    return changed


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Sync PlantLibrary with TAMU PDF guides')
    p.add_argument('--plant',         default=None,
                   help='Process only this plant name (substring match)')
    p.add_argument('--dry-run',       action='store_true',
                   help='Print extracted JSON without writing to DB')
    p.add_argument('--force',         action='store_true',
                   help='Re-process even if plant already has how_to_grow data')
    p.add_argument('--download-only', action='store_true',
                   help='Download PDFs only, no LLM extraction')
    p.add_argument('--delay',         type=float, default=1.0,
                   help='Seconds between LLM calls (default 1.0)')
    p.add_argument('--log-level',     default='INFO',
                   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                   help='Log verbosity (default INFO)')
    return p.parse_args()


def main():
    args = parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger.info('tamu_sync starting (dry_run=%s, force=%s)', args.dry_run, args.force)

    from app.db.session import SessionLocal
    from app.db.models import PlantLibrary

    db = SessionLocal()
    try:
        all_entries = db.query(PlantLibrary).all()
        logger.info('%d library entries loaded', len(all_entries))

        n_updated = n_skipped = n_no_match = n_errors = n_downloaded = 0

        # Filter to single plant if requested
        pdf_list = TAMU_PDFS
        if args.plant:
            filter_lower = args.plant.lower()
            pdf_list = [(p, u, s) for p, u, s in TAMU_PDFS
                        if filter_lower in p.lower()]
            logger.info('Filtered to %d PDF(s) matching %r', len(pdf_list), args.plant)

        for plant_name, url, series in pdf_list:
            logger.info('[%s] %s', series, plant_name)

            # Download PDF
            pdf_path = download_pdf(plant_name, url, series)
            if not pdf_path:
                n_errors += 1
                continue
            n_downloaded += 1

            if args.download_only:
                continue

            # Find library entry
            entry = find_library_entry(plant_name, all_entries)
            if not entry:
                logger.warning('no library match for %r', plant_name)
                n_no_match += 1
                continue

            # Skip if already enriched (unless --force)
            if not args.force and not _blank(getattr(entry, 'how_to_grow', None)):
                logger.debug('%r already has how_to_grow, skipping', plant_name)
                n_skipped += 1
                continue

            # Extract text from PDF
            text = extract_pdf_text(pdf_path)
            if not text.strip():
                logger.warning('empty text from PDF: %s', pdf_path)
                n_errors += 1
                continue

            logger.info('extracted %d chars from PDF', len(text))

            # LLM extraction
            extracted = extract_fields_with_llm(plant_name, text)
            time.sleep(args.delay)

            if not extracted:
                logger.error('LLM extraction failed for %r', plant_name)
                n_errors += 1
                continue

            if args.dry_run:
                logger.info('[dry-run] would update %r: %s', entry.name, json.dumps(extracted, indent=2))
                n_updated += 1
                continue

            # Merge
            changes = merge_tamu_data(entry, extracted, dry_run=False)
            if changes:
                db.commit()
                logger.info('updated %r: %s', entry.name, [c[0] for c in changes])
                n_updated += 1
            else:
                logger.info('no new fields to set for %r', entry.name)
                n_skipped += 1

        logger.info(
            'Done. downloaded=%d updated=%d skipped=%d no_match=%d errors=%d',
            n_downloaded, n_updated, n_skipped, n_no_match, n_errors,
        )
    finally:
        db.close()


if __name__ == '__main__':
    main()
