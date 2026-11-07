"""
Plant-ID Phase 1: compare frozen image backbones for nearest-prototype
species retrieval (see ml/docs/PLANT_ID_MODEL.md, stage 5/6).

For each backbone:
  1. embed every real library photo and the iNaturalist eval photos
     (cached incrementally under ml/data/raw/plantid_cache/),
  2. build one prototype per species = mean of its L2-normalised embeddings,
     optionally blended with a text prototype ("a photo of Genus species.")
     for CLIP-family models — text prototypes are precomputed offline, so the
     client still only runs the image tower,
  3. score eval photos by cosine similarity to every prototype.

The eval species are split 50/50 (seeded, by species). The calibration half
picks the image/text blend, fits the softmax temperature and the confidence
threshold that hands off to Claude; every reported number comes from the
other half.

Run (needs CUDA torch + open_clip/timm — setup in ml/docs/PLANT_ID_MODEL.md):
    uv run --no-sync python ml/experiments/plantid_backbones.py
    uv run --no-sync python ml/experiments/plantid_backbones.py --backbones mobileclip2_s0 dinov2_s
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.evaluation.plantid_metrics import (  # noqa: E402
    choose_threshold,
    expected_calibration_error,
    fit_temperature,
    softmax,
    topk_accuracy,
)
from ml.features.plantid_data import CACHE_DIR, eval_manifest, library_manifest  # noqa: E402

RESULTS_PATH = _ROOT / 'ml' / 'experiments' / 'results' / 'plantid_backbones.json'
TARGET_ACCURACY = 0.90     # local answers must be right this often, else defer to Claude
BLENDS = [0.0, 0.25, 0.5, 0.75, 1.0]   # weight on the image prototype (1.0 = image only)
SEED = 42

BACKBONES = {
    # Teacher / upper bound: trained on the TreeOfLife-10M taxonomy. Too big for the client.
    'bioclip':        {'kind': 'open_clip', 'name': 'hf-hub:imageomics/bioclip'},
    'mobileclip2_s0': {'kind': 'open_clip', 'name': 'MobileCLIP2-S0', 'pretrained': 'dfndr2b'},
    'mobileclip_s1':  {'kind': 'open_clip', 'name': 'MobileCLIP-S1', 'pretrained': 'datacompdr'},
    'dinov2_s':       {'kind': 'timm', 'name': 'vit_small_patch14_dinov2.lvd142m'},
}


class _ImageDataset:
    def __init__(self, paths, transform):
        self.paths, self.transform = paths, transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None   # some Wikimedia originals are huge
        try:
            img = Image.open(self.paths[i])
            img.draft('RGB', (512, 512))   # fast JPEG decode at reduced size
            return self.transform(img.convert('RGB')), True
        except Exception:
            # Same shape as a real sample; the False flag drops it downstream.
            return self.transform(Image.new('RGB', (64, 64))), False


def load_backbone(key: str):
    """Return (image_encoder, transform, text_encoder | None, image_tower_params)."""
    import torch
    spec = BACKBONES[key]
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if spec['kind'] == 'open_clip':
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            spec['name'], pretrained=spec.get('pretrained'))
        model = model.eval().to(device)
        tokenizer = open_clip.get_tokenizer(spec['name'])

        def encode_text(texts):
            return model.encode_text(tokenizer(texts).to(device))

        params = sum(p.numel() for p in model.visual.parameters())
        return model.encode_image, preprocess, encode_text, params
    import timm
    model = timm.create_model(spec['name'], pretrained=True, num_classes=0, img_size=224)
    model = model.eval().to(device)
    # The pretrained cfg says 518 px; pin it to the 224 the model was built at.
    cfg = timm.data.resolve_data_config({'input_size': (3, 224, 224)}, model=model)
    transform = timm.data.create_transform(**cfg)
    return model, transform, None, sum(p.numel() for p in model.parameters())


def embed_paths(encode, transform, paths: list[Path], cache_file: Path) -> np.ndarray:
    """L2-normalised embeddings for `paths`; only uncached paths are computed."""
    import torch
    cache: dict[str, np.ndarray] = {}
    if cache_file.exists():
        z = np.load(cache_file, allow_pickle=False)
        cache = dict(zip(z['paths'].tolist(), z['emb']))
    todo = [p for p in paths if str(p) not in cache]
    if todo:
        loader = torch.utils.data.DataLoader(
            _ImageDataset(todo, transform), batch_size=64, num_workers=4)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        done = 0
        with torch.no_grad(), torch.autocast(device, enabled=device == 'cuda'):
            for imgs, ok in loader:
                emb = encode(imgs.to(device)).float()
                emb = torch.nn.functional.normalize(emb, dim=-1).cpu().numpy()
                emb[~ok.numpy()] = np.nan    # unreadable file -> excluded downstream
                for p, e in zip(todo[done:done + len(emb)], emb):
                    cache[str(p)] = e.astype(np.float16)
                done += len(emb)
                print(f'    embedded {done}/{len(todo)}', end='\r')
        print()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache_file, paths=np.array(list(cache)), emb=np.stack(list(cache.values())))
    return np.stack([cache[str(p)] for p in paths]).astype(np.float32)


def _normalise(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def build_prototypes(emb: np.ndarray, keys: list[str], classes: list[str]) -> np.ndarray:
    index = {c: i for i, c in enumerate(classes)}
    sums = np.zeros((len(classes), emb.shape[1]), dtype=np.float64)
    for e, k in zip(emb, keys):
        sums[index[k]] += e
    # A class with no usable image would be 0/0 -> NaN, which survives even a
    # zero blend weight; leave it as a zero vector instead.
    with np.errstate(invalid='ignore'):
        return np.nan_to_num(_normalise(sums)).astype(np.float32)


def _cpu_latency_ms(encode, transform, n_runs: int = 10) -> float:
    """Batch-1 CPU latency — a rough proxy for the client, not a phone benchmark."""
    import copy
    from PIL import Image
    import torch
    owner = getattr(encode, '__self__', encode)
    cpu_model = copy.deepcopy(owner).cpu().float()
    fn = getattr(cpu_model, encode.__name__) if hasattr(encode, '__self__') else cpu_model
    x = transform(Image.new('RGB', (64, 64))).unsqueeze(0)
    with torch.no_grad():
        fn(x)
        t0 = time.perf_counter()
        for _ in range(n_runs):
            fn(x)
    return (time.perf_counter() - t0) / n_runs * 1000


def _score(logits, labels, crop, calib, test) -> dict:
    """Fit T and tau on the calibration half; report everything on the test half."""
    t = fit_temperature(logits[calib], labels[calib])
    probs_cal = softmax(logits[calib], t)
    conf_cal = probs_cal.max(axis=1)
    correct_cal = probs_cal.argmax(axis=1) == labels[calib]
    tau = choose_threshold(conf_cal, correct_cal, TARGET_ACCURACY)

    lt, yt = logits[test], labels[test]
    probs = softmax(lt, t)
    conf, correct = probs.max(axis=1), probs.argmax(axis=1) == yt
    raw = softmax(lt, 1.0)
    keep = conf >= tau if tau is not None else np.zeros(len(conf), dtype=bool)
    crop_t = crop[test]
    return {
        'top1': topk_accuracy(lt, yt, 1),
        'top5': topk_accuracy(lt, yt, 5),
        'top1_crop': topk_accuracy(lt[crop_t], yt[crop_t], 1) if crop_t.any() else None,
        'top5_crop': topk_accuracy(lt[crop_t], yt[crop_t], 5) if crop_t.any() else None,
        'temperature': t,
        'ece_raw': expected_calibration_error(raw.max(axis=1), raw.argmax(axis=1) == yt),
        'ece': expected_calibration_error(conf, correct),
        'tau': tau,
        'coverage_at_tau': float(keep.mean()),
        'selective_accuracy_at_tau': float(correct[keep].mean()) if keep.any() else None,
        'n_test': int(len(yt)),
    }


def _save_predictions(key, ev, logits, labels, test, classes, temperature):
    """Per-image test-half predictions — the hybrid local/Claude comparison reads these."""
    probs = softmax(logits[test], temperature)
    rows = [r for r, t in zip(ev, test) if t]
    path = RESULTS_PATH.parent / f'plantid_predictions_{key}.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['path', 'species_key', 'is_crop', 'pred', 'conf', 'correct'])
        for r, p, y in zip(rows, probs, labels[test]):
            writer.writerow([Path(r['path']).relative_to(_ROOT).as_posix(), r['species_key'],
                             int(r['is_crop']), classes[int(p.argmax())],
                             f'{p.max():.4f}', int(p.argmax() == y)])


def run_backbone(key: str, library: list[dict], evals: list[dict]) -> dict:
    import torch
    from PIL import Image
    print(f'\n== {key} ==')
    encode, transform, encode_text, params = load_backbone(key)
    lib_emb = embed_paths(encode, transform, [r['path'] for r in library],
                          CACHE_DIR / f'{key}_library.npz')
    ev_emb = embed_paths(encode, transform, [r['path'] for r in evals],
                         CACHE_DIR / f'{key}_eval.npz')

    lib_ok = ~np.isnan(lib_emb).any(axis=1)
    lib_keys = [r['species_key'] for r, ok in zip(library, lib_ok) if ok]
    classes = sorted(set(lib_keys))
    index = {c: i for i, c in enumerate(classes)}
    img_protos = build_prototypes(lib_emb[lib_ok], lib_keys, classes)

    ev_ok = np.array([not np.isnan(e).any() and r['species_key'] in index
                      for e, r in zip(ev_emb, evals)])
    ev = [r for r, ok in zip(evals, ev_ok) if ok]
    ev_emb = ev_emb[ev_ok]
    labels = np.array([index[r['species_key']] for r in ev])
    crop = np.array([r['is_crop'] for r in ev])

    species = sorted({r['species_key'] for r in ev})
    rng = np.random.default_rng(SEED)
    calib_species = set(rng.choice(species, size=len(species) // 2, replace=False))
    calib = np.array([r['species_key'] in calib_species for r in ev])
    test = ~calib

    text_protos = None
    if encode_text is not None:
        texts = [f'a photo of {c.capitalize()}.' for c in classes]
        chunks = []
        with torch.no_grad():
            for i in range(0, len(texts), 256):
                chunks.append(torch.nn.functional.normalize(
                    encode_text(texts[i:i + 256]).float(), dim=-1).cpu().numpy())
        text_protos = np.concatenate(chunks)

    blends = BLENDS if text_protos is not None else [1.0]
    best_alpha, best_top1, curves = 1.0, -1.0, {}
    for alpha in blends:
        protos = img_protos if text_protos is None else _normalise(
            alpha * img_protos + (1 - alpha) * text_protos)
        top1 = topk_accuracy(ev_emb[calib] @ protos.T, labels[calib], 1)
        curves[alpha] = top1
        if top1 > best_top1:
            best_alpha, best_top1 = alpha, top1
    protos = img_protos if text_protos is None else _normalise(
        best_alpha * img_protos + (1 - best_alpha) * text_protos)

    logits = ev_emb @ protos.T
    result = _score(logits, labels, crop, calib, test)
    _save_predictions(key, ev, logits, labels, test, classes, result['temperature'])
    if text_protos is not None:
        result['zero_shot_top1'] = topk_accuracy(ev_emb[test] @ text_protos.T, labels[test], 1)
    result['image_only_top1'] = topk_accuracy(ev_emb[test] @ img_protos.T, labels[test], 1)
    result.update({
        'backbone': key,
        'blend_alpha': best_alpha,
        'blend_calib_top1': {str(a): v for a, v in curves.items()},
        'n_classes': len(classes),
        'n_library_images': int(lib_ok.sum()),
        'embed_dim': int(img_protos.shape[1]),
        'image_tower_params_m': params / 1e6,
        'int8_size_mb_est': params / 1e6,
        'input_size': int(transform(Image.new('RGB', (64, 64))).shape[-1]),
        'cpu_latency_ms': _cpu_latency_ms(encode, transform),
    })
    del encode, encode_text
    torch.cuda.empty_cache()
    return result


def _fmt(v, pct=True):
    if v is None:
        return '—'
    return f'{v * 100:5.1f}' if pct else f'{v:6.1f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backbones', nargs='+', default=list(BACKBONES), choices=list(BACKBONES))
    args = ap.parse_args()

    from apps.backend.app.db.session import SessionLocal
    db = SessionLocal()
    try:
        library = library_manifest(db)
    finally:
        db.close()
    evals = eval_manifest()
    print(f'{len(library)} library photos, {len(evals)} eval photos '
          f'({len({r["species_key"] for r in evals})} species)')

    results = {}
    if RESULTS_PATH.exists():
        results = json.loads(RESULTS_PATH.read_text(encoding='utf-8'))
    for key in args.backbones:
        results[key] = run_backbone(key, library, evals)
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding='utf-8')

    print(f'\n{"backbone":<15} {"top1":>5} {"top5":>5} {"crop1":>5} {"ECEraw":>6} {"ECE":>5} '
          f'{"tau":>5} {"cover":>5} {"selacc":>6} {"alpha":>5} {"Mparams":>7} {"cpu ms":>6}')
    for key, r in results.items():
        print(f'{key:<15} {_fmt(r["top1"])} {_fmt(r["top5"])} {_fmt(r["top1_crop"])} '
              f'{_fmt(r["ece_raw"]):>6} {_fmt(r["ece"])} {_fmt(r["tau"])} '
              f'{_fmt(r["coverage_at_tau"])} {_fmt(r["selective_accuracy_at_tau"]):>6} '
              f'{r["blend_alpha"]:5.2f} {_fmt(r["image_tower_params_m"], False):>7} '
              f'{_fmt(r["cpu_latency_ms"], False)}')
    print(f'\nresults -> {RESULTS_PATH.relative_to(_ROOT)}')


if __name__ == '__main__':
    main()
