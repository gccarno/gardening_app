"""
Load a plant-ID model version's species prototypes into Postgres
(plant_image_prototype), which POST /api/identify/embedding ranks against.

The prototypes are produced by ml/training/export_plantid_onnx.py; this only
moves them into the database. Replaces any existing rows for the version in
one transaction, so the endpoint never sees a half-loaded version. Other
versions are left alone — a client still shipping v1 keeps working while v2
rolls out.

Usage (from the repo root):
    uv run --no-sync alembic upgrade head   # once
    uv run --no-sync python scripts/build_plantid_prototypes.py --version v1
    uv run --no-sync python scripts/build_plantid_prototypes.py --version v1 --stats
"""
import argparse
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features.plantid_data import CACHE_DIR  # noqa: E402

BATCH = 500


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--stats', action='store_true', help='show row counts per version and exit')
    args = ap.parse_args()

    from sqlalchemy import func
    from apps.backend.app.db.models import PlantImagePrototype, PlantLibrary
    from apps.backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        if args.stats:
            for version, n in (db.query(PlantImagePrototype.model_version, func.count())
                               .group_by(PlantImagePrototype.model_version)):
                print(f'{version}: {n} species')
            return

        if not (_ROOT / 'ml' / 'models' / f'plantid_{args.version}.json').exists():
            sys.exit(f'ml/models/plantid_{args.version}.json missing — the endpoint would 409; '
                     'export the version first')
        z = np.load(CACHE_DIR / f'plantid_{args.version}_prototypes.npz', allow_pickle=False)
        known_ids = {i for (i,) in db.query(PlantLibrary.id)}
        rows = [
            PlantImagePrototype(
                model_version=args.version,
                species_key=str(key),
                scientific_name=str(sci),
                plant_library_id=int(lib_id) if int(lib_id) in known_ids else None,
                n_images=int(n),
                embedding=emb.tolist(),
            )
            for key, sci, lib_id, n, emb in zip(z['species_key'], z['scientific_name'],
                                                 z['plant_library_id'], z['n_images'], z['emb'])
        ]
        deleted = (db.query(PlantImagePrototype)
                   .filter(PlantImagePrototype.model_version == args.version)
                   .delete(synchronize_session=False))
        for i in range(0, len(rows), BATCH):
            db.add_all(rows[i:i + BATCH])
            db.flush()
            print(f'  {min(i + BATCH, len(rows))}/{len(rows)}', end='\r')
        db.commit()
        print(f'\n{args.version}: replaced {deleted} rows with {len(rows)} species prototypes')
    finally:
        db.close()


if __name__ == '__main__':
    main()
