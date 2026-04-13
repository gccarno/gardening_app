"""
Generate fun SVG plant icons using Ollama/Gemma for all PlantLibrary entries.

Files are named  {id}_{slug}.svg  e.g. 1_tomato.svg, 42_bell_pepper.svg
Saved to: apps/api/static/plant_svg_icons/

Resume-safe: skips plants that already have an SVG (unless --overwrite).

Usage:
    uv run python scripts/generate_plant_svg_icons.py --list-prompts
    uv run python scripts/generate_plant_svg_icons.py --plant-id 1 --dry-run
    uv run python scripts/generate_plant_svg_icons.py --plant-id 1 --prompt 3
    uv run python scripts/generate_plant_svg_icons.py --plant-id 1 --compare
    uv run python scripts/generate_plant_svg_icons.py --limit 20 --prompt 5
    uv run python scripts/generate_plant_svg_icons.py --model gemma3:4b --delay 0
"""
import argparse
import glob as _glob
import json
import os
import re
import sqlite3
import sys
import time
from xml.etree import ElementTree as ET

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH   = os.path.join(_REPO_ROOT, 'apps', 'api', 'instance', 'garden.db')
_SVG_DIR   = os.path.join(_REPO_ROOT, 'apps', 'api', 'static', 'plant_svg_icons')

# ─────────────────────────────────────────────────────────────────────────────
# File naming
# ─────────────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return s or 'plant'


def svg_filename(plant: dict, strategy_index: int | None = None) -> str:
    slug = slugify(plant['name'])
    base = f'{plant["id"]}_{slug}'
    if strategy_index is not None:
        return f'{base}_s{strategy_index}.svg'
    return f'{base}.svg'


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

_PLANT_COLS = (
    'id', 'name', 'scientific_name', 'type',
    'flower_color', 'foliage_color', 'fruit_color',
    'growth_habit', 'ligneous_type', 'average_height_cm',
    'thorny', 'tropical', 'indoor', 'attracts',
)


def load_plants(plant_id: int | None, limit: int | None) -> list[dict]:
    if not os.path.exists(_DB_PATH):
        sys.exit(f'ERROR: database not found at {_DB_PATH}')
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cols = ', '.join(_PLANT_COLS)
    if plant_id is not None:
        rows = cur.execute(f'SELECT {cols} FROM plant_library WHERE id = ?', (plant_id,)).fetchall()
    else:
        rows = cur.execute(f'SELECT {cols} FROM plant_library ORDER BY id').fetchall()
    conn.close()
    plants = [dict(r) for r in rows]
    return plants[:limit] if limit else plants


# ─────────────────────────────────────────────────────────────────────────────
# Prompt strategies
# ─────────────────────────────────────────────────────────────────────────────
# Each strategy is a dict:
#   name        – short label
#   description – one line shown in --list-prompts
#   system      – system message sent to Ollama
#   user        – callable(plant: dict) -> str
# ─────────────────────────────────────────────────────────────────────────────

_SYS_STRICT = """\
You are an SVG icon generator. Output ONLY raw SVG XML — nothing else.
No markdown fences, no explanation, no comments outside the SVG.
The response must start with <svg and end with </svg>.
Required attributes: xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100".
Forbidden: <text>, <image>, gradients, filters, clipPath, masks, scripts, external references.
Use only: circle, ellipse, rect, polygon, polyline, path, line, g.
Maximum 15 elements. Solid fills only."""

_SYS_FLAT = """\
You are a flat-design icon artist. Output ONLY raw SVG XML — no markdown, no explanation.
Start with <svg, end with </svg>.
Style: Google Material / flat design — bold solid colors, clean geometric shapes, no detail.
Required: xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100".
Forbidden: <text>, gradients, filters, shadows, <image>, scripts, external references.
Use at most 12 elements. Every shape must have a fill or stroke."""

_SYS_TERSE = "Output only valid SVG XML for a plant icon. No prose. Start with <svg, end with </svg>."

_SYS_CARTOON = """\
You are a cartoon sticker artist who draws plants as cute, expressive icons.
Output ONLY raw SVG XML. No markdown fences or explanation.
Start with <svg, end with </svg>.
Style: chunky outlines (stroke-width 3-5), bright saturated colors, slightly rounded shapes.
Required: xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100".
Forbidden: <text>, <image>, gradients, filters, scripts.
Maximum 15 elements."""

_SYS_EMOJI = """\
You are designing a plant emoji. Output ONLY raw SVG XML — no markdown, no explanation.
Start with <svg, end with </svg>.
Style: exactly like Apple/Google emoji — circular background, centered subject, bright colors.
Required: xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100".
Forbidden: <text>, <image>, gradients, filters, scripts.
Maximum 15 elements."""


def _color_hint(plant: dict) -> str:
    colors = [c for c in [plant.get('fruit_color'), plant.get('flower_color'), plant.get('foliage_color')] if c]
    return f'Colors: {", ".join(colors)}.' if colors else ''


def _trait_hint(plant: dict) -> str:
    traits = []
    if plant.get('thorny'):   traits.append('thorny')
    if plant.get('tropical'): traits.append('tropical')
    if plant.get('indoor'):   traits.append('indoor')
    return f'Traits: {", ".join(traits)}.' if traits else ''


_TOMATO_EXAMPLE = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="52" r="36" fill="#e53935"/>
  <ellipse cx="38" cy="28" rx="10" ry="6" fill="#43a047" transform="rotate(-30 38 28)"/>
  <ellipse cx="50" cy="22" rx="10" ry="6" fill="#43a047"/>
  <ellipse cx="62" cy="28" rx="10" ry="6" fill="#43a047" transform="rotate(30 62 28)"/>
  <rect x="47" y="20" width="6" height="10" fill="#795548"/>
  <circle cx="40" cy="48" r="5" fill="#ef9a9a" opacity="0.5"/>
</svg>"""

_CARROT_EXAMPLE = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,85 25,30 75,30" fill="#ff7043"/>
  <rect x="44" y="15" width="5" height="20" fill="#43a047" transform="rotate(-15 44 15)"/>
  <rect x="50" y="12" width="5" height="22" fill="#43a047"/>
  <rect x="56" y="15" width="5" height="20" fill="#43a047" transform="rotate(15 56 15)"/>
</svg>"""


STRATEGIES: list[dict] = [
    # ── 0 ────────────────────────────────────────────────────────────────────
    {
        'name': 'descriptive',
        'description': 'Detailed prose description of plant features (original baseline)',
        'system': _SYS_STRICT,
        'user': lambda p: '\n'.join(filter(None, [
            f'Draw an SVG icon for: {p["name"]}',
            f'Scientific name: {p["scientific_name"]}' if p.get('scientific_name') else '',
            {'vegetable':'Draw the recognizable edible part.','herb':'Draw a leafy aromatic sprig.',
             'fruit':'Draw the ripe fruit prominently.','flower':'Draw a cheerful flower with petals.'
             }.get((p.get('type') or '').lower(), f'Type: {p.get("type","plant")}'),
            _color_hint(p),
            _trait_hint(p),
            'Output ONLY the SVG XML.',
        ])),
    },
    # ── 1 ────────────────────────────────────────────────────────────────────
    {
        'name': 'terse',
        'description': 'Ultra-minimal: plant name only, no extra context',
        'system': _SYS_TERSE,
        'user': lambda p: f'Plant icon: {p["name"]}',
    },
    # ── 2 ────────────────────────────────────────────────────────────────────
    {
        'name': 'flat-icon',
        'description': 'Flat Material Design style — bold colors, clean geometry',
        'system': _SYS_FLAT,
        'user': lambda p: '\n'.join(filter(None, [
            f'Plant: {p["name"]}',
            _color_hint(p),
            'Draw as a flat Material Design plant icon.',
        ])),
    },
    # ── 3 ────────────────────────────────────────────────────────────────────
    {
        'name': 'cartoon',
        'description': 'Chunky cartoon sticker with bold outlines and saturated colors',
        'system': _SYS_CARTOON,
        'user': lambda p: '\n'.join(filter(None, [
            f'Draw a cute cartoon sticker of: {p["name"]}',
            _color_hint(p),
            _trait_hint(p),
        ])),
    },
    # ── 4 ────────────────────────────────────────────────────────────────────
    {
        'name': 'emoji',
        'description': 'Emoji-style: circular background, centered subject, Apple/Google look',
        'system': _SYS_EMOJI,
        'user': lambda p: '\n'.join(filter(None, [
            f'Create an emoji for: {p["name"]}',
            f'Colors: {_color_hint(p)}' if _color_hint(p) else '',
            'Circle background, centered plant, emoji style.',
        ])),
    },
    # ── 5 ────────────────────────────────────────────────────────────────────
    {
        'name': 'shape-recipe',
        'description': 'Prescribes exact SVG elements to use — forces structured output',
        'system': _SYS_STRICT,
        'user': lambda p: f'''\
Draw an SVG icon for "{p["name"]}" using ONLY these elements in this order:
1. One circle or rect as background
2. One or two large ellipses or polygons for the main body
3. One or two smaller shapes for leaf/stem/accent
4. One rect or path for stem/root if applicable
{_color_hint(p)}
Output ONLY the SVG XML.''',
    },
    # ── 6 ────────────────────────────────────────────────────────────────────
    {
        'name': 'template-fill',
        'description': 'Provide a complete SVG template; model adapts shapes and colors',
        'system': _SYS_STRICT,
        'user': lambda p: f'''\
Adapt this SVG template to represent "{p["name"]}" — change the shapes, \
sizes, and colors to match this plant. Keep the same structure.
{_color_hint(p)}

Template to adapt:
{_TOMATO_EXAMPLE}

Output ONLY the adapted SVG XML for {p["name"]}.''',
    },
    # ── 7 ────────────────────────────────────────────────────────────────────
    {
        'name': 'color-led',
        'description': 'Leads with dominant colors then asks for matching shapes',
        'system': _SYS_STRICT,
        'user': lambda p: '\n'.join(filter(None, [
            f'Plant: {p["name"]}',
            _color_hint(p) or 'Color: green',
            'Use these colors prominently. Build the icon shape around them.',
            f'Type: {p.get("type","plant")}',
            'Output ONLY the SVG XML.',
        ])),
    },
    # ── 8 ────────────────────────────────────────────────────────────────────
    {
        'name': 'constructive',
        'description': 'Step-by-step layering: background → main body → details → stem',
        'system': _SYS_STRICT,
        'user': lambda p: f'''\
Draw an SVG icon for "{p["name"]}" by layering shapes back-to-front:
Step 1 — background: a soft circle fill
Step 2 — main body: the most recognizable part of {p["name"]}
Step 3 — detail: one or two accent shapes (leaf vein, highlight, texture mark)
Step 4 — stem or root if the plant has one
{_color_hint(p)}
Output ONLY the complete SVG XML.''',
    },
    # ── 9 ────────────────────────────────────────────────────────────────────
    {
        'name': 'scene',
        'description': 'Scene framing: "looking down at a garden bed" perspective',
        'system': _SYS_STRICT,
        'user': lambda p: '\n'.join(filter(None, [
            f'Icon: a {p["name"]} as seen from slightly above in a garden.',
            _color_hint(p),
            _trait_hint(p),
            'Circular composition. Show the most identifiable feature of the plant.',
            'Output ONLY the SVG XML.',
        ])),
    },
    # ── 10 ───────────────────────────────────────────────────────────────────
    {
        'name': 'negative',
        'description': 'Heavy use of negative constraints — say what NOT to draw',
        'system': _SYS_STRICT,
        'user': lambda p: f'''\
Draw an SVG icon for "{p["name"]}".
DO NOT draw: text labels, realistic detail, thin lines, more than 12 shapes, gradients.
DO draw: bold solid shapes, the single most recognizable feature of {p["name"]}, \
a clear silhouette readable at 40px.
{_color_hint(p)}
Output ONLY the SVG XML.''',
    },
    # ── 11 ───────────────────────────────────────────────────────────────────
    {
        'name': 'carrot-adapt',
        'description': 'Provide a root-vegetable example and ask model to adapt it',
        'system': _SYS_STRICT,
        'user': lambda p: f'''\
Here is an SVG icon for a carrot:
{_CARROT_EXAMPLE}

Now create a similar icon for "{p["name"]}". \
Keep the same simplicity and cartoon style but draw the correct plant.
{_color_hint(p)}
Output ONLY the new SVG XML.''',
    },
    # ── 12 ───────────────────────────────────────────────────────────────────
    {
        'name': 'think-then-draw',
        'description': 'Ask model to name the key shapes first, then output the SVG',
        'system': _SYS_STRICT,
        'user': lambda p: f'''\
Plant: {p["name"]}
{_color_hint(p)}

First, on ONE line starting with "PLAN:", list the 3-5 SVG shapes you will use and their colors.
Then output the complete SVG XML starting on the next line.
The SVG must start with <svg and end with </svg>.''',
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Ollama API
# ─────────────────────────────────────────────────────────────────────────────

def call_ollama(strategy: dict, plant: dict, model: str, base_url: str, timeout: int = 90) -> str:
    payload = {
        'model': model,
        'stream': False,
        'messages': [
            {'role': 'system', 'content': strategy['system']},
            {'role': 'user',   'content': strategy['user'](plant)},
        ],
    }
    r = requests.post(f'{base_url}/api/chat', json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()['message']['content']


# ─────────────────────────────────────────────────────────────────────────────
# SVG extraction / validation
# ─────────────────────────────────────────────────────────────────────────────

def _validate_svg(text: str) -> bool:
    if '<svg' not in text.lower():
        return False
    try:
        root = ET.fromstring(text)
        return root.tag.lower().split('}')[-1] == 'svg'
    except ET.ParseError:
        return False


def extract_svg(raw: str) -> str | None:
    # Try to find <svg...>...</svg> directly
    m = re.search(r'(<svg[\s\S]*?</svg\s*>)', raw, re.IGNORECASE)
    if m:
        c = m.group(1).strip()
        if _validate_svg(c):
            return c
    # Strip markdown fences and retry
    stripped = re.sub(r'```(?:svg|xml)?\s*', '', raw, flags=re.IGNORECASE)
    stripped = re.sub(r'```', '', stripped).strip()
    m2 = re.search(r'(<svg[\s\S]*?</svg\s*>)', stripped, re.IGNORECASE)
    if m2:
        c = m2.group(1).strip()
        if _validate_svg(c):
            return c
    return None


_FALLBACK_SUFFIX = """

IMPORTANT: I need ONLY raw SVG XML. Use this exact structure (adapt shapes/colors):
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="50" r="45" fill="#e8f5e9"/>
  <ellipse cx="50" cy="55" rx="25" ry="30" fill="#4caf50"/>
  <rect x="47" y="75" width="6" height="15" fill="#795548"/>
</svg>"""


def generate_svg(plant: dict, strategy: dict, args) -> tuple[str | None, str]:
    """Returns (svg_content | None, status)."""
    if args.dry_run:
        print(f'\n=== DRY RUN: strategy "{strategy["name"]}" for {plant["name"]} ===')
        print(f'[system]\n{strategy["system"]}\n')
        print(f'[user]\n{strategy["user"](plant)}\n')
        return None, 'dry_run'

    for attempt in range(args.retries + 1):
        user_fn = strategy['user']
        if attempt > 0:
            # Wrap user function to append fallback suffix on retry
            original_fn = user_fn
            user_fn = lambda p, fn=original_fn: fn(p) + _FALLBACK_SUFFIX  # noqa: E731
        strat_retry = dict(strategy, user=user_fn)
        try:
            raw = call_ollama(strat_retry, plant, args.model, args.ollama_url)
        except requests.exceptions.RequestException as exc:
            return None, f'error:{exc}'

        svg = extract_svg(raw)
        if svg:
            return svg, 'ok'

        if attempt < args.retries:
            time.sleep(args.delay)

    return None, 'invalid'


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Generate SVG plant icons via Ollama/Gemma')
    p.add_argument('--list-prompts', action='store_true', help='List all prompt strategies and exit')
    p.add_argument('--prompt',    type=int,   default=0,    help='Prompt strategy index (default 0; see --list-prompts)')
    p.add_argument('--compare',   action='store_true',      help='Run ALL strategies on --plant-id, save as {id}_{slug}_s{N}.svg')
    p.add_argument('--limit',     type=int,   default=None, help='Stop after N plants')
    p.add_argument('--plant-id',  type=int,   default=None, dest='plant_id', help='Generate only one plant by ID')
    p.add_argument('--overwrite', action='store_true',      help='Regenerate even if SVG already exists')
    p.add_argument('--model',     type=str,   default='gemma4:e2b', help='Ollama model name')
    p.add_argument('--delay',     type=float, default=0.5,  help='Seconds between requests')
    p.add_argument('--ollama-url',type=str,   default='http://localhost:11434', dest='ollama_url')
    p.add_argument('--retries',   type=int,   default=2,    help='Max retries per plant on validation failure')
    p.add_argument('--dry-run',   action='store_true',      help='Print prompts, do not call Ollama')
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.list_prompts:
        print(f'{"#":<4} {"Name":<18} Description')
        print('-' * 72)
        for i, s in enumerate(STRATEGIES):
            print(f'{i:<4} {s["name"]:<18} {s["description"]}')
        return

    os.makedirs(_SVG_DIR, exist_ok=True)

    plants = load_plants(args.plant_id, args.limit)
    if not plants:
        sys.exit(f'No plants found (plant_id={args.plant_id})')

    # ── Compare mode: run every strategy on one plant ─────────────────────
    if args.compare:
        if not args.plant_id:
            sys.exit('--compare requires --plant-id')
        plant = plants[0]
        print(f'Comparing {len(STRATEGIES)} strategies for "{plant["name"]}" (id={plant["id"]})')
        for i, strategy in enumerate(STRATEGIES):
            fname = svg_filename(plant, strategy_index=i)
            out_path = os.path.join(_SVG_DIR, fname)
            print(f'  [{i:>2}] {strategy["name"]:<18} → {fname} ... ', end='', flush=True)
            if not args.overwrite and os.path.exists(out_path):
                print('skip (exists)')
                continue
            svg, status = generate_svg(plant, strategy, args)
            if status == 'ok':
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(svg)
                print(f'ok ({len(svg)} bytes)')
            elif status == 'dry_run':
                pass
            else:
                print(status)
            if not args.dry_run:
                time.sleep(args.delay)
        print(f'\nCompare outputs in: {_SVG_DIR}')
        return

    # ── Normal mode: run one strategy on N plants ─────────────────────────
    if args.prompt >= len(STRATEGIES):
        sys.exit(f'Invalid --prompt {args.prompt}. Max is {len(STRATEGIES) - 1}. Use --list-prompts.')
    strategy = STRATEGIES[args.prompt]
    print(f'Strategy: [{args.prompt}] {strategy["name"]} — {strategy["description"]}')

    if not args.overwrite:
        plants = [p for p in plants if not os.path.exists(os.path.join(_SVG_DIR, svg_filename(p)))]

    total = len(plants)
    print(f'Generating SVG icons for {total} plant(s) → {_SVG_DIR}')
    if args.dry_run:
        print('[DRY RUN — no files will be written]')

    n_ok = n_invalid = n_error = n_dry = 0
    failures: list[tuple[int, str, str]] = []

    for i, plant in enumerate(plants, 1):
        fname    = svg_filename(plant)
        out_path = os.path.join(_SVG_DIR, fname)
        label    = f'{plant["name"][:32]:<32}'
        print(f'  [{i:>5}/{total}] {label} → {fname} ... ', end='', flush=True)

        svg, status = generate_svg(plant, strategy, args)

        if status == 'ok':
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(svg)
            n_ok += 1
            print(f'ok ({len(svg)} bytes)')
        elif status == 'dry_run':
            n_dry += 1
        elif status == 'invalid':
            n_invalid += 1
            failures.append((plant['id'], plant['name'], 'invalid_svg'))
            print('INVALID SVG (gave up after retries)')
        else:
            n_error += 1
            failures.append((plant['id'], plant['name'], status))
            print(status)

        if not args.dry_run and i < total:
            time.sleep(args.delay)

    print(f'\nDone.  ok={n_ok}  invalid={n_invalid}  errors={n_error}  dry_run={n_dry}')
    if failures:
        print('\nFailed plants:')
        for pid, name, s in failures:
            print(f'  id={pid:>6}  {name}: {s}')


if __name__ == '__main__':
    main()
