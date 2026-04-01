"""
Enrich PlantLibrary with data scraped from UFSeeds (ufseeds.com).

UFSeeds carries 2,000+ seed products across vegetables, herbs, and flowers.
Each product page contains structured growing data: days to maturity, spacing,
sunlight, plant height, botanical name, growth habit.

Strategy:
  - Crawl category listing pages (pagination handled automatically)
  - For each product page, parse attributes with regex
  - Match product to PlantLibrary entry by name (fuzzy matching on base plant type)
  - Fill-in-blank merge — never overwrites existing data
  - Resumable via AppSetting('ufseeds_sync_cursor') (last processed URL)

Usage:
    python scripts/ufseeds_sync.py --dry-run
    python scripts/ufseeds_sync.py --category vegetables/tomatoes
    python scripts/ufseeds_sync.py
    python scripts/ufseeds_sync.py --force
    python scripts/ufseeds_sync.py --collect-only   # print discovered URLs only

Rate limit: polite 1.5s delay between requests
"""
import argparse
import difflib
import json
import os
import re
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'api'))

from dotenv import load_dotenv
load_dotenv()

import requests
from bs4 import BeautifulSoup
from app.main import create_app
from app.db.models import db, PlantLibrary, AppSetting

BASE_URL = 'https://www.ufseeds.com'

# Categories to crawl — add/remove as needed
CATEGORIES = [
    'vegetables/artichokes', 'vegetables/asparagus', 'vegetables/beans',
    'vegetables/beets', 'vegetables/broccoli', 'vegetables/brussel-sprouts',
    'vegetables/cabbage', 'vegetables/carrots', 'vegetables/cauliflower',
    'vegetables/celery', 'vegetables/chard', 'vegetables/chicory',
    'vegetables/chinese-cabbage', 'vegetables/collards', 'vegetables/corn',
    'vegetables/cucumbers', 'vegetables/eggplant', 'vegetables/fennel',
    'vegetables/garlic', 'vegetables/greens', 'vegetables/kale',
    'vegetables/kohlrabi', 'vegetables/leeks', 'vegetables/lettuce',
    'vegetables/melons', 'vegetables/okra', 'vegetables/onions',
    'vegetables/peas', 'vegetables/peppers', 'vegetables/potatoes',
    'vegetables/pumpkin', 'vegetables/radish', 'vegetables/shallots',
    'vegetables/spinach', 'vegetables/squash', 'vegetables/sweet-potatoes',
    'vegetables/tomatillo', 'vegetables/tomatoes', 'vegetables/turnips',
    'vegetables/watermelon',
    'herbs/basil', 'herbs/cilantro', 'herbs/dill', 'herbs/mint',
    'herbs/oregano', 'herbs/parsley', 'herbs/rosemary', 'herbs/sage',
    'herbs/thyme', 'herbs/lavender',
]

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'GardenApp/1.0 (garden-planning-tool; educational use)'


# ── Category crawling ──────────────────────────────────────────────────────────

def get_category_product_urls(category_path, delay=1.5):
    """Collect all product page URLs from a category listing (handles pagination)."""
    urls = []
    start = 0
    sz = 72

    while True:
        url = f'{BASE_URL}/{category_path}/?sz={sz}&start={start}'
        try:
            r = SESSION.get(url, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f'    category error {url}: {e}')
            break

        soup = BeautifulSoup(r.text, 'html.parser')
        links = [
            a['href'] for a in soup.find_all('a', href=True)
            if a['href'].startswith('/product/')
        ]
        new = []
        seen = set(urls)
        for link in links:
            full = BASE_URL + link
            if full not in seen:
                seen.add(full)
                new.append(full)
        urls.extend(new)

        # Parse "X - Y of Z" to determine if there are more pages
        text = soup.get_text()
        m = re.search(r'(\d[\d,]*)\s*-\s*(\d[\d,]*)\s+of\s+(\d[\d,]*)', text)
        if m:
            end_idx = int(m.group(2).replace(',', ''))
            total = int(m.group(3).replace(',', ''))
            if end_idx >= total or not new:
                break
            start += sz
        else:
            break

        time.sleep(delay)

    return urls


# ── Product page parsing ───────────────────────────────────────────────────────

def parse_product_page(url):
    """Fetch and parse a UFSeeds product page. Returns (data_dict, error_str)."""
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return None, str(e)

    soup = BeautifulSoup(r.text, 'html.parser')
    text = soup.get_text(' ', strip=True)

    data = {}

    # Product name from <h1>
    h1 = soup.find('h1')
    if h1:
        data['product_name'] = h1.get_text(strip=True)

    # Days to maturity → days_to_harvest (take average of range)
    m = re.search(r'Days?\s+[Tt]o\s+[Mm]aturity[^:]*[:\s]+(\d+)\s*[-–—]\s*(\d+)', text)
    if m:
        data['days_to_harvest'] = int(round((int(m.group(1)) + int(m.group(2))) / 2))
    else:
        m = re.search(r'Days?\s+[Tt]o\s+[Mm]aturity[^:]*[:\s]+(\d+)', text)
        if m:
            data['days_to_harvest'] = int(m.group(1))

    # Plant spacing in inches → spacing_in
    m = re.search(r'Plant\s+Spacing[^:]*[:\s]+"?(\d+)"', text)
    if m:
        data['spacing_in'] = int(m.group(1))
    else:
        m = re.search(r'Plant\s+Spacing[^:]*[:\s]+([\d.]+)\s*(?:inch|in\b)', text, re.IGNORECASE)
        if m:
            data['spacing_in'] = int(float(m.group(1)))

    # Row spacing → row_spacing_cm (source may be in feet or inches)
    m = re.search(r'Row\s+Spacing[^:]*[:\s]+([\d.]+)\s*(?:\'|feet|ft\b)', text)
    if m:
        data['row_spacing_cm'] = int(float(m.group(1)) * 30.48)
    else:
        m = re.search(r'Row\s+Spacing[^:]*[:\s]+([\d.]+)"', text)
        if m:
            data['row_spacing_cm'] = int(float(m.group(1)) * 2.54)

    # Plant height → average_height_cm (may be range)
    m = re.search(r'Plant\s+Height[^:]*[:\s]+([\d.]+)\s*[-–]\s*([\d.]+)\s*(?:\'|feet|ft\b)', text)
    if m:
        avg_ft = (float(m.group(1)) + float(m.group(2))) / 2
        data['average_height_cm'] = int(avg_ft * 30.48)
    else:
        m = re.search(r'Plant\s+Height[^:]*[:\s]+([\d.]+)\s*(?:\'|feet|ft\b)', text)
        if m:
            data['average_height_cm'] = int(float(m.group(1)) * 30.48)

    # Sunlight
    m = re.search(r'Sun(?:light)?[:\s]+([^\d\n]{3,40}?)(?:\s{2,}|\bDays|\bBotanical|\bRow|\bPlant|\bGrowth|$)',
                  text)
    if m:
        raw = m.group(1).strip().lower()
        if 'full sun' in raw:
            data['sunlight'] = 'Full sun'
        elif 'partial shade' in raw or 'part shade' in raw:
            data['sunlight'] = 'Partial shade'
        elif 'partial sun' in raw or 'part sun' in raw:
            data['sunlight'] = 'Partial sun'
        elif 'full shade' in raw:
            data['sunlight'] = 'Full shade'

    # Botanical name → scientific_name
    m = re.search(r'Botanical\s+Name[:\s]+([A-Z][a-z]+ [a-z]+(?:\s+(?:var\.|subsp\.)\s+\S+)?)', text)
    if m:
        data['scientific_name'] = m.group(1).strip()

    # Growth habit
    m = re.search(r'Growth\s+Habit[:\s]+([^\n\r,]{3,40}?)(?:\s{2,}|\bSun|\bDays|\bBotanical|$)', text)
    if m:
        data['growth_habit'] = m.group(1).strip()

    # Propagation: check if transplant is mentioned
    if re.search(r'\btransplant\b', text, re.IGNORECASE):
        data['propagation_methods'] = json.dumps(['Transplant', 'Seed'])
    else:
        data['propagation_methods'] = json.dumps(['Seed'])

    return data, None


# ── Name matching ──────────────────────────────────────────────────────────────

# Words to strip from product names to get base plant type
_STRIP_WORDS = re.compile(
    r'\b(?:seeds?|f1|f2|f3|hybrid|heirloom|organic|open\s+pollinated|op'
    r'|untreated|pelleted|treated|certified|giant|dwarf|baby|mini|micro'
    r'|early|late|mid|season|improved|select)\b',
    re.IGNORECASE,
)


def _base_plant_name(product_name):
    """Strip variety/brand/type qualifiers to get base plant name."""
    name = re.sub(r'\([^)]+\)', '', product_name)       # remove parenthetical
    name = re.sub(r'[™®]', '', name)                     # remove trademark
    name = _STRIP_WORDS.sub('', name)
    name = ' '.join(name.split())                        # collapse whitespace
    return name.strip()


def find_library_match(product_name, library_names):
    """Fuzzy-match a product name to a PlantLibrary entry name."""
    base = _base_plant_name(product_name)
    base_lower = base.lower()

    # Exact match on base name
    for lib in library_names:
        if lib.lower() == base_lower:
            return lib

    # Library name is a substring of base (e.g. "Tomato" in "German Johnson Tomato")
    for lib in library_names:
        lib_lower = lib.lower()
        if re.search(r'\b' + re.escape(lib_lower) + r'\b', base_lower):
            return lib

    # Last 1–2 words of base match a library entry
    words = base.split()
    for n in [2, 1]:
        if len(words) >= n:
            suffix = ' '.join(words[-n:]).lower()
            for lib in library_names:
                if lib.lower() == suffix:
                    return lib

    # Fuzzy fallback
    lib_lowers = [n.lower() for n in library_names]
    hits = difflib.get_close_matches(base_lower, lib_lowers, n=1, cutoff=0.75)
    if hits:
        matched_lower = hits[0]
        for lib in library_names:
            if lib.lower() == matched_lower:
                return lib

    return None


# ── Merge ──────────────────────────────────────────────────────────────────────

def _blank(val):
    return val is None or str(val).strip() == ''


def merge_into_library(entry, data, dry_run):
    """Fill-in-blank merge of scraped data into a PlantLibrary entry.
    Returns list of (field, value) tuples for any fields updated."""
    changed = []

    def _set(field, value):
        if value is None:
            return
        if _blank(getattr(entry, field, None)):
            changed.append((field, value))
            if not dry_run:
                setattr(entry, field, value)

    _set('days_to_harvest',     data.get('days_to_harvest'))
    _set('spacing_in',          data.get('spacing_in'))
    _set('row_spacing_cm',      data.get('row_spacing_cm'))
    _set('average_height_cm',   data.get('average_height_cm'))
    _set('sunlight',            data.get('sunlight'))
    _set('scientific_name',     data.get('scientific_name'))
    _set('growth_habit',        data.get('growth_habit'))
    _set('propagation_methods', data.get('propagation_methods'))

    return changed


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Sync PlantLibrary with UFSeeds data')
    p.add_argument('--category',     default=None,
                   help='Single category path e.g. vegetables/tomatoes')
    p.add_argument('--dry-run',      action='store_true',
                   help='Preview changes without writing to DB')
    p.add_argument('--force',        action='store_true',
                   help='Ignore resume cursor, process from beginning')
    p.add_argument('--collect-only', action='store_true',
                   help='Print discovered product URLs only, no DB writes')
    p.add_argument('--delay',        type=float, default=1.5,
                   help='Seconds between requests (default 1.5)')
    return p.parse_args()


def main():
    args = parse_args()

    flask_app = create_app()
    with flask_app.app_context():
        all_entries = PlantLibrary.query.all()
        library_names = [e.name for e in all_entries]
        name_to_entry = {e.name: e for e in all_entries}
        print(f'{len(all_entries)} library entries loaded\n')

        categories = [args.category] if args.category else CATEGORIES

        # Resumable cursor
        cursor_key = 'ufseeds_sync_cursor'
        cursor_setting = AppSetting.query.filter_by(key=cursor_key).first()
        skip_until = (cursor_setting.value if cursor_setting else None) if not args.force else None

        n_updated = n_skipped = n_no_match = n_errors = 0

        for cat in categories:
            print(f'[category] {cat}')
            product_urls = get_category_product_urls(cat, delay=args.delay)
            print(f'  {len(product_urls)} products found')

            if args.collect_only:
                for u in product_urls:
                    print(f'  {u}')
                continue

            for url in product_urls:
                # Skip until cursor position
                if skip_until:
                    if url == skip_until:
                        skip_until = None
                    else:
                        n_skipped += 1
                        continue

                data, err = parse_product_page(url)
                time.sleep(args.delay)

                if err or not data:
                    print(f'  ERR {url}: {err}')
                    n_errors += 1
                    continue

                product_name = data.get('product_name', '')
                if not product_name:
                    n_errors += 1
                    continue

                matched_name = find_library_match(product_name, library_names)
                if not matched_name:
                    print(f'  no match: {product_name!r}')
                    n_no_match += 1
                    continue

                entry = name_to_entry[matched_name]
                changes = merge_into_library(entry, data, args.dry_run)

                if changes:
                    tag = '[dry]' if args.dry_run else '[upd]'
                    print(f'  {tag} {product_name!r} → {matched_name!r}')
                    for field, val in changes:
                        print(f'      {field} = {val!r}')
                    if not args.dry_run:
                        db.session.commit()
                        if not cursor_setting:
                            cursor_setting = AppSetting(key=cursor_key, value=url)
                            db.session.add(cursor_setting)
                            db.session.commit()
                        else:
                            cursor_setting.value = url
                            db.session.commit()
                    n_updated += 1
                else:
                    n_skipped += 1

        print(f'\nDone. updated={n_updated} skipped={n_skipped} '
              f'no_match={n_no_match} errors={n_errors}')


if __name__ == '__main__':
    main()
