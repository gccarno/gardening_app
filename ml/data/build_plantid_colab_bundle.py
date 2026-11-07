"""
Pack everything the plant-ID student needs to train and export *off* this
machine (Google Colab — see ml/notebooks/plantid_distill_colab.ipynb) into one
zip, so the remote side never touches the live DB or laptop paths.

Two steps, so the laptop never has to load a model:

  1. here (laptop): needs the DB and the cached BioCLIP library embeddings
     from ml/experiments/plantid_backbones.py — numpy only, no torch.
  2. --finish on Colab: runs BioCLIP's text tower on the GPU and writes the
     teacher prototypes training/export read (ml/features/plantid_data.py
     load_bundle).

Layout of plantid_colab_bundle.zip (step 1):
    meta.json              alpha (BioCLIP image/text blend), counts, git sha
    classes.json           [{species_key, scientific_name, plant_library_id, n_images}]
    image_protos.npy       BioCLIP image prototypes from library photos (float32)
    eval.csv               eval manifest with bundle-relative paths
    eval/<photo>.jpg       the 1,500 iNaturalist eval photos
    distill/library/*.jpg  pre-resized library photos (unlabelled for training)
    distill/inat/*.jpg     pre-resized broad iNaturalist photos
added by --finish:
    teacher_text.npy       BioCLIP text prototypes, for the KL term
    teacher_protos.npy     alpha * image + (1 - alpha) * text — the prototypes served

Run:
    uv run --no-sync python ml/data/build_plantid_colab_bundle.py           # laptop
    python ml/data/build_plantid_colab_bundle.py --finish /content/bundle   # Colab
"""
import argparse
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.evaluation.metrics_history import _git_sha  # noqa: E402
from ml.experiments.plantid_backbones import RESULTS_PATH, build_prototypes  # noqa: E402
from ml.features.plantid_data import CACHE_DIR, EVAL_CSV, eval_manifest, library_manifest  # noqa: E402
from ml.training.export_plantid_onnx import _representatives  # noqa: E402

DISTILL_DIR = _ROOT / 'ml' / 'data' / 'raw' / 'plantid_distill'
OUT = _ROOT / 'ml' / 'data' / 'raw' / 'plantid_bundle' / 'plantid_colab_bundle.zip'


def _npy_bytes(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, a.astype(np.float32))
    return buf.getvalue()


def _image_prototypes(library: list[dict], classes: list[str]) -> np.ndarray:
    """BioCLIP image prototypes straight from the bake-off's embedding cache (no model load)."""
    z = np.load(CACHE_DIR / 'bioclip_library.npz', allow_pickle=False)
    cache = dict(zip(z['paths'].tolist(), z['emb']))
    missing = [r for r in library if str(r['path']) not in cache]
    if missing:
        sys.exit(f'{len(missing)} library photos have no cached BioCLIP embedding — '
                 'run ml/experiments/plantid_backbones.py --backbones bioclip first')
    emb = np.stack([cache[str(r['path'])] for r in library]).astype(np.float32)
    ok = ~np.isnan(emb).any(axis=1)
    return build_prototypes(emb[ok], [r['species_key'] for r, g in zip(library, ok) if g], classes)


def finish(bundle_dir: Path):
    """Colab side: BioCLIP text prototypes on the GPU, blended into the served prototypes."""
    import torch

    from ml.training.train_plantid_student import build_teacher
    meta = json.loads((bundle_dir / 'meta.json').read_text(encoding='utf-8'))
    classes = [c['species_key'] for c in json.loads((bundle_dir / 'classes.json').read_text(encoding='utf-8'))]
    _, encode_text = build_teacher('cuda' if torch.cuda.is_available() else 'cpu')
    texts = [f'a photo of {c.capitalize()}.' for c in classes]
    with torch.no_grad():
        text = np.concatenate([encode_text(texts[i:i + 256]).cpu().numpy() for i in range(0, len(texts), 256)])
    img = np.load(bundle_dir / 'image_protos.npy')
    a = meta['alpha']
    protos = a * img + (1 - a) * text
    protos /= np.linalg.norm(protos, axis=1, keepdims=True)
    np.save(bundle_dir / 'teacher_text.npy', text.astype(np.float32))
    np.save(bundle_dir / 'teacher_protos.npy', protos.astype(np.float32))
    print(f'teacher prototypes: {protos.shape}, alpha={a}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--finish', type=Path, metavar='BUNDLE_DIR', help='Colab step 2 (needs a GPU ideally)')
    args = ap.parse_args()
    if args.finish:
        finish(args.finish)
        return

    from apps.backend.app.db.session import SessionLocal
    db = SessionLocal()
    try:
        library = library_manifest(db)
        from sqlalchemy import text
        sci = dict(db.execute(text(
            "SELECT id, scientific_name FROM plant_library WHERE coalesce(scientific_name, '') <> ''")).all())
    finally:
        db.close()

    classes = sorted({r['species_key'] for r in library})
    alpha = json.loads(RESULTS_PATH.read_text(encoding='utf-8'))['bioclip']['blend_alpha']
    image_protos = _image_prototypes(library, classes)

    reps = _representatives(library)
    n_images: dict[str, int] = {}
    for r in library:
        n_images[r['species_key']] = n_images.get(r['species_key'], 0) + 1
    class_rows = [{'species_key': c, 'scientific_name': sci.get(reps[c], c.capitalize()),
                   'plant_library_id': reps[c], 'n_images': n_images[c]} for c in classes]

    evals = eval_manifest()
    with EVAL_CSV.open(newline='', encoding='utf-8') as f:
        fields = csv.DictReader(f).fieldnames
    eval_csv = io.StringIO()
    writer = csv.DictWriter(eval_csv, fieldnames=fields)
    writer.writeheader()
    for r in evals:
        writer.writerow({**{k: r[k] for k in fields if k not in ('path', 'is_crop')},
                         'path': f'eval/{r["path"].name}', 'is_crop': int(r['is_crop'])})

    train = sorted(DISTILL_DIR.glob('*/*.jpg'))
    meta = {'alpha': alpha, 'n_classes': len(classes), 'n_eval': len(evals),
            'n_train': len(train), 'git_sha': _git_sha()}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # JPEGs are already compressed — store them; deflate only the small text/npy files.
    with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_STORED) as z:
        small = zipfile.ZIP_DEFLATED
        z.writestr('meta.json', json.dumps(meta, indent=2), compress_type=small)
        z.writestr('classes.json', json.dumps(class_rows), compress_type=small)
        z.writestr('image_protos.npy', _npy_bytes(image_protos), compress_type=small)
        z.writestr('eval.csv', eval_csv.getvalue(), compress_type=small)
        for r in evals:
            z.write(r['path'], f'eval/{r["path"].name}')
        for i, p in enumerate(train, 1):
            z.write(p, f'distill/{p.parent.name}/{p.name}')
            if i % 5000 == 0:
                print(f'  {i}/{len(train)} training photos')
    print(f'{OUT.relative_to(_ROOT)}: {OUT.stat().st_size / 1e9:.2f} GB — {json.dumps(meta)}')


if __name__ == '__main__':
    main()
