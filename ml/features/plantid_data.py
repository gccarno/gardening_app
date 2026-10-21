"""
Shared data access for the plant-ID model: the library photo manifest, the
eval-set manifest, and the label key both use.

Labels are species (normalised scientific name), never library rows — see
ml/docs/PLANT_ID_MODEL.md. AI-generated library images are excluded
everywhere: they are what a diffusion model thinks a plant looks like, not
evidence of what it does look like.
"""
import csv
import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
# Overridable so a git worktree can read the (gitignored, 5.6 GB) photo tree
# of the main checkout instead of needing its own copy.
LIBRARY_IMG_DIR = Path(os.environ.get('PLANTID_LIBRARY_IMG_DIR',
                                      _ROOT / 'apps' / 'api' / 'static' / 'plant_images'))
EVAL_CSV = _ROOT / 'ml' / 'data' / 'processed' / 'plantid_eval.csv'
CACHE_DIR = _ROOT / 'ml' / 'data' / 'raw' / 'plantid_cache'


def species_key(scientific_name: str) -> str:
    """Normalised scientific name — the label unit shared by eval, prototypes and serving.

    Library names carry cultivar noise that no photo can resolve:
    'Solanum lycopersicum (Brandywine)', "Capsicum annuum 'Jalapeno'". Those
    are stripped, as are rank markers ('var.', 'subsp.'), so cultivars pool
    into their taxon. Trinomials are kept — cabbage and kale look different.
    Synonyms (Lycopersicum esculentum) are NOT merged; see the model card.
    """
    name = re.sub(r'\(.*?\)', ' ', scientific_name)
    name = re.sub(r"['\"‘’“”].*?['\"‘’“”]", ' ', name)
    name = re.sub(r'\b(var|subsp|ssp|cv|f)\.\s*', ' ', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip().lower()


def library_manifest(db) -> list[dict]:
    """Every real library photo that exists locally: {species_key, path, plant_library_id}."""
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT i.filename, i.plant_library_id, p.scientific_name
        FROM plant_library_image i
        JOIN plant_library p ON p.id = i.plant_library_id
        WHERE i.source <> 'ai-generated' AND coalesce(p.scientific_name, '') <> ''
        ORDER BY i.id
    """)).all()
    out = []
    for filename, lib_id, sci in rows:
        path = LIBRARY_IMG_DIR / filename
        if path.exists():
            out.append({'species_key': species_key(sci), 'path': path, 'plant_library_id': lib_id})
    return out


def eval_manifest() -> list[dict]:
    """Rows of the committed iNaturalist eval CSV, with absolute paths."""
    with EVAL_CSV.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r['path'] = _ROOT / r['path']
        r['is_crop'] = r.get('is_crop') == '1'
    return [r for r in rows if r['path'].exists()]
