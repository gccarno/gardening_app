"""
Plant-ID: export the chosen backbone's image tower to ONNX, quantise it, and
produce everything a model version needs (see ml/docs/PLANT_ID_MODEL.md,
stage 7):

  ml/models/plantid_<version>.onnx      image tower, int8, normalisation baked in
  ml/models/plantid_<version>.json      serving config: input size, temperature,
                                        tau, metrics — read by server and clients
  ml/data/raw/plantid_cache/plantid_<version>_prototypes.npz
                                        per-species prototypes, loaded into
                                        Postgres by scripts/build_plantid_prototypes.py

Prototypes and calibration come from the *exported* model run on the
client-reference preprocessing (ml/features/plantid_preprocess.py), never
from torch — so the server's probabilities describe what clients embed.

Parity gate: the int8 ONNX pipeline must agree with the fp32 torch pipeline
on >= PARITY_MIN of eval top-1 predictions, or nothing is written.

Run:
    # a distilled student (the shipping path — see ml/training/train_plantid_student.py)
    uv run --no-sync python ml/training/export_plantid_onnx.py         --student-ckpt ml/data/raw/plantid_cache/student_mobileclip2_s0_v1.pt --version v1
    # on Colab, from a bundle (no DB; writes everything to --out-dir)
    python ml/training/export_plantid_onnx.py --student-ckpt <ckpt> --bundle /content/bundle         --out-dir /content/drive/MyDrive/plantid --version v1
    # or an off-the-shelf backbone from the bake-off
    uv run --no-sync python ml/training/export_plantid_onnx.py --backbone mobileclip2_s0 --version v0
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.evaluation.metrics_history import append_run  # noqa: E402
from ml.evaluation.plantid_metrics import (  # noqa: E402
    choose_threshold,
    expected_calibration_error,
    fit_temperature,
    softmax,
    topk_accuracy,
)
from ml.experiments.plantid_backbones import (  # noqa: E402
    BACKBONES,
    RESULTS_PATH,
    SEED,
    TARGET_ACCURACY,
    build_prototypes,
    embed_paths,
    load_backbone,
)
from ml.features.plantid_data import CACHE_DIR, eval_manifest, library_manifest, load_bundle  # noqa: E402
from ml.features.plantid_preprocess import load_and_preprocess  # noqa: E402

MODELS_DIR = _ROOT / 'ml' / 'models'
PARITY_MIN = 0.97
N_CALIBRATION_IMAGES = 256   # static-quantisation activation ranges


def _tower(key: str):
    """(nn.Module: [0,1] NCHW -> L2-normalised embedding, input_size, text encoder)."""
    import torch
    import timm.utils.model as tum

    spec = BACKBONES[key]
    if spec['kind'] == 'open_clip':
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            spec['name'], pretrained=spec.get('pretrained'))
        model.eval()
        visual = model.visual
        norm = next(t for t in preprocess.transforms if type(t).__name__ == 'Normalize')
        crop = next(t for t in preprocess.transforms if type(t).__name__ == 'CenterCrop')
        mean, std, size = norm.mean, norm.std, crop.size[0]
    else:
        import timm
        visual = timm.create_model(spec['name'], pretrained=True, num_classes=0, img_size=224).eval()
        cfg = timm.data.resolve_data_config({'input_size': (3, 224, 224)}, model=visual)
        mean, std, size, model = cfg['mean'], cfg['std'], 224, None
    # MobileCLIP's MobileOne/FastViT blocks fold their train-time branches into
    # single convs — same function, far fewer ops for the client.
    visual = tum.reparameterize_model(visual)

    class Tower(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.visual = visual
            self.register_buffer('mean', torch.tensor(mean, dtype=torch.float32).view(1, 3, 1, 1))
            self.register_buffer('std', torch.tensor(std, dtype=torch.float32).view(1, 3, 1, 1))

        def forward(self, pixels):
            return torch.nn.functional.normalize(self.visual((pixels - self.mean) / self.std), dim=-1)

    encode_text = None
    if model is not None:
        tokenizer = open_clip.get_tokenizer(spec['name'])

        def encode_text(texts):
            return model.encode_text(tokenizer(texts))
    return Tower().eval(), size, encode_text


def _student_tower(ckpt_path: Path):
    """(distilled student on [0,1] NCHW -> L2-normalised BioCLIP-space embedding, input_size, key)."""
    import timm.utils.model as tum
    import torch

    from ml.training.train_plantid_student import build_student
    ckpt = torch.load(ckpt_path, map_location='cpu')
    student = build_student(ckpt['student'])
    student.load_state_dict(ckpt['state_dict'])
    student.backbone = tum.reparameterize_model(student.backbone)
    return student.eval(), ckpt['input_size'], ckpt['student']


def _export(tower, size: int, fp32_path: Path):
    import torch
    dummy = torch.rand(1, 3, size, size)
    torch.onnx.export(tower, dummy, str(fp32_path), input_names=['pixels'],
                      output_names=['embedding'], opset_version=17, dynamo=False,
                      dynamic_axes={'pixels': {0: 'batch'}, 'embedding': {0: 'batch'}})


def _quantize(fp32_path: Path, out_path: Path, calib_paths: list[Path], size: int):
    from onnxruntime.quantization import (
        CalibrationDataReader, QuantFormat, QuantType, quantize_static)
    from onnxruntime.quantization.shape_inference import quant_pre_process

    class Reader(CalibrationDataReader):
        def __init__(self):
            arrays = (load_and_preprocess(p, size) for p in calib_paths)
            self.it = iter([{'pixels': a[None]} for a in arrays if a is not None])

        def get_next(self):
            return next(self.it, None)

    pre = fp32_path.with_suffix('.pre.onnx')
    quant_pre_process(str(fp32_path), str(pre))
    quantize_static(str(pre), str(out_path), Reader(), quant_format=QuantFormat.QDQ,
                    per_channel=True, weight_type=QuantType.QInt8,
                    activation_type=QuantType.QUInt8)
    pre.unlink()


def _onnx_embed(model_path: Path, paths: list[Path], size: int, cache_file: Path) -> np.ndarray:
    """Embeddings through the exported model + reference preprocessing.

    Cached per path; files that can't be decoded come back as NaN rows.
    """
    from concurrent.futures import ThreadPoolExecutor

    import onnxruntime as ort
    cache: dict[str, np.ndarray] = {}
    if cache_file.exists():
        z = np.load(cache_file, allow_pickle=False)
        cache = dict(zip(z['paths'].tolist(), z['emb']))
    todo = [p for p in paths if str(p) not in cache]
    if todo:
        sess = ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])
        with ThreadPoolExecutor(8) as pool:
            for i in range(0, len(todo), 64):
                chunk = todo[i:i + 64]
                arrays = list(pool.map(lambda p: load_and_preprocess(p, size), chunk))
                good = [(p, a) for p, a in zip(chunk, arrays) if a is not None]
                if good:
                    out = sess.run(None, {'pixels': np.stack([a for _, a in good])})[0]
                    for (p, _), e in zip(good, out):
                        cache[str(p)] = e.astype(np.float16)
                print(f'    onnx-embedded {i + len(chunk)}/{len(todo)}', end='\r')
        print()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache_file, paths=np.array(list(cache)), emb=np.stack(list(cache.values())))
    dim = next(iter(cache.values())).shape[0]
    missing = np.full(dim, np.nan, dtype=np.float16)
    return np.stack([cache.get(str(p), missing) for p in paths]).astype(np.float32)


def _text_prototypes(encode_text, classes: list[str]) -> np.ndarray:
    import torch
    texts = [f'a photo of {c.capitalize()}.' for c in classes]
    chunks = []
    with torch.no_grad():
        for i in range(0, len(texts), 256):
            chunks.append(torch.nn.functional.normalize(
                encode_text(texts[i:i + 256]).float(), dim=-1).numpy())
    return np.concatenate(chunks)


def _blend(img_protos, text_protos, alpha):
    if text_protos is None or alpha >= 1.0:
        return img_protos
    p = alpha * img_protos + (1 - alpha) * text_protos
    return (p / np.linalg.norm(p, axis=1, keepdims=True)).astype(np.float32)


def _representatives(library: list[dict]) -> dict[str, int]:
    """species_key -> the library row with the most real photos (ties: lowest id)."""
    counts: dict[tuple[str, int], int] = {}
    for r in library:
        k = (r['species_key'], r['plant_library_id'])
        counts[k] = counts.get(k, 0) + 1
    best: dict[str, tuple[int, int]] = {}
    for (key, lib_id), n in counts.items():
        if key not in best or (n, -lib_id) > (best[key][0], -best[key][1]):
            best[key] = (n, lib_id)
    return {k: lib_id for k, (_, lib_id) in best.items()}


def _split(ev: list[dict]) -> np.ndarray:
    """Calibration mask — the same seeded by-species split as the bake-off."""
    species = sorted({r['species_key'] for r in ev})
    calib_species = set(np.random.default_rng(SEED).choice(species, size=len(species) // 2, replace=False))
    return np.array([r['species_key'] in calib_species for r in ev])


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--backbone', choices=list(BACKBONES), help='an off-the-shelf bake-off backbone')
    src.add_argument('--student-ckpt', type=Path, help='a distilled student checkpoint')
    ap.add_argument('--version', required=True, help='e.g. v1 — becomes the model_version')
    ap.add_argument('--bundle', type=Path, help='a Colab bundle (student only): no DB, no library pass')
    ap.add_argument('--out-dir', type=Path, help='write all outputs here instead of ml/models + cache')
    args = ap.parse_args()
    if args.bundle and not args.student_ckpt:
        ap.error('--bundle needs --student-ckpt')
    version = args.version
    models_dir = args.out_dir or MODELS_DIR
    cache_dir = args.out_dir or CACHE_DIR

    bundle = load_bundle(args.bundle) if args.bundle else None
    if bundle:
        alpha, library, evals = bundle['alpha'], None, bundle['evals']
        calib_pool = [p for p in bundle['train_paths'] if p.parent.name == 'library']
    else:
        # A student lives in BioCLIP's space, so it is served against BioCLIP's prototypes.
        proto_source = 'bioclip' if args.student_ckpt else args.backbone
        alpha = json.loads(RESULTS_PATH.read_text(encoding='utf-8'))[proto_source]['blend_alpha']
        from apps.backend.app.db.session import SessionLocal
        db = SessionLocal()
        try:
            library = library_manifest(db)
        finally:
            db.close()
        evals = eval_manifest()
        calib_pool = [r['path'] for r in library]

    # 1. export + quantise
    if args.student_ckpt:
        tower, size, student_key = _student_tower(args.student_ckpt)
        model_name = f'student:{student_key}'
    else:
        tower, size, encode_text = _tower(args.backbone)
        model_name = args.backbone
    cache_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    fp32_path = cache_dir / f'plantid_{version}_fp32.onnx'
    onnx_path = models_dir / f'plantid_{version}.onnx'
    print(f'exporting {model_name} @ {size}px')
    _export(tower, size, fp32_path)
    rng = np.random.default_rng(SEED)
    calib_imgs = [calib_pool[i] for i in rng.choice(len(calib_pool), N_CALIBRATION_IMAGES, replace=False)]
    print('quantising (static int8, QDQ)')
    _quantize(fp32_path, onnx_path, calib_imgs, size)

    # 2. embed through the exported model
    ev_emb = _onnx_embed(onnx_path, [r['path'] for r in evals], size,
                         cache_dir / f'plantid_{version}_eval.npz')
    if bundle:
        # Classes and the teacher's prototypes come pre-built; no library pass needed.
        classes, protos = bundle['class_keys'], bundle['teacher_protos']
    else:
        lib_emb = _onnx_embed(onnx_path, [r['path'] for r in library], size,
                              cache_dir / f'plantid_{version}_library.npz')
        lib_ok = ~np.isnan(lib_emb).any(axis=1)
        lib_rows = [r for r, ok in zip(library, lib_ok) if ok]
        lib_keys = [r['species_key'] for r in lib_rows]
        classes = sorted(set(lib_keys))
    index = {c: i for i, c in enumerate(classes)}
    if args.student_ckpt and not bundle:
        from ml.training.train_plantid_student import build_teacher, teacher_prototypes
        _, teacher_text = build_teacher('cuda')
        protos, _, _ = teacher_prototypes(library, teacher_text, classes)
    elif not args.student_ckpt:
        text_protos = _text_prototypes(encode_text, classes) if encode_text and alpha < 1.0 else None
        protos = _blend(build_prototypes(lib_emb[lib_ok], lib_keys, classes), text_protos, alpha)

    ev_ok = np.array([not np.isnan(e).any() and r['species_key'] in index
                      for e, r in zip(ev_emb, evals)])
    ev = [r for r, ok in zip(evals, ev_ok) if ok]
    ev_emb = ev_emb[ev_ok]
    labels = np.array([index[r['species_key']] for r in ev])
    cultivated = np.array([r['is_crop'] for r in ev])
    calib = _split(ev)
    test = ~calib

    # 3. parity: exported int8 pipeline vs fp32 torch pipeline
    if args.student_ckpt:
        # Same preprocessing and prototypes on both sides: this isolates quantisation.
        import torch
        arrays = [load_and_preprocess(r['path'], size) for r in ev]
        with torch.no_grad():
            torch_ev = np.concatenate([tower(torch.from_numpy(np.stack(arrays[i:i + 64]))).numpy()
                                       for i in range(0, len(arrays), 64)])
        torch_protos = protos
    else:
        enc, transform, _, _ = load_backbone(args.backbone)
        torch_ev = embed_paths(enc, transform, [r['path'] for r in ev],
                               cache_dir / f'{args.backbone}_eval.npz')
        torch_lib = embed_paths(enc, transform, [r['path'] for r in lib_rows],
                                cache_dir / f'{args.backbone}_library.npz')
        torch_ok = ~np.isnan(torch_lib).any(axis=1)
        torch_protos = _blend(build_prototypes(torch_lib[torch_ok],
                                               [k for k, ok in zip(lib_keys, torch_ok) if ok], classes),
                              text_protos, alpha)
    agree = float(((ev_emb @ protos.T).argmax(1) == (torch_ev @ torch_protos.T).argmax(1)).mean())
    emb_cos = float(np.nanmean((ev_emb * torch_ev).sum(1)))
    print(f'parity: top-1 agreement {agree:.3f}, mean embedding cosine {emb_cos:.4f}')
    if agree < PARITY_MIN:
        onnx_path.unlink()
        sys.exit(f'parity gate FAILED ({agree:.3f} < {PARITY_MIN}) — nothing written')

    # 4. calibrate on one half, report on the other
    logits = ev_emb @ protos.T
    t = fit_temperature(logits[calib], labels[calib])
    p_cal = softmax(logits[calib], t)
    tau = choose_threshold(p_cal.max(1), p_cal.argmax(1) == labels[calib], TARGET_ACCURACY)
    p = softmax(logits[test], t)
    conf, correct = p.max(1), p.argmax(1) == labels[test]
    keep = conf >= tau if tau is not None else np.zeros(len(conf), dtype=bool)
    ct = cultivated[test]
    metrics = {
        'top1': topk_accuracy(logits[test], labels[test], 1),
        'top5': topk_accuracy(logits[test], labels[test], 5),
        'top1_cultivated': topk_accuracy(logits[test][ct], labels[test][ct], 1) if ct.any() else None,
        'ece': expected_calibration_error(conf, correct),
        'coverage_at_tau': float(keep.mean()),
        'selective_accuracy_at_tau': float(correct[keep].mean()) if keep.any() else None,
        'parity_top1_agreement': agree,
        'parity_embedding_cosine': emb_cos,
        'n_test': int(test.sum()),
    }
    print(json.dumps(metrics, indent=2))

    # 5. write the version
    if bundle:
        info = {c['species_key']: c for c in bundle['classes']}
        reps = {k: c['plant_library_id'] for k, c in info.items()}
        display = {k: c['scientific_name'] for k, c in info.items()}
        n_images = {k: c['n_images'] for k, c in info.items()}
    else:
        reps = _representatives(lib_rows)
        display = {}
        for r in ev:
            display.setdefault(r['species_key'], r['scientific_name'])
        n_images = {c: 0 for c in classes}
        for k in lib_keys:
            n_images[k] += 1
    np.savez(cache_dir / f'plantid_{version}_prototypes.npz',
             species_key=np.array(classes),
             scientific_name=np.array([display.get(c, c.capitalize()) for c in classes]),
             plant_library_id=np.array([reps[c] for c in classes]),
             n_images=np.array([n_images[c] for c in classes]),
             emb=protos.astype(np.float32))
    config = {
        'model_version': version,
        'backbone': model_name,
        'embed_dim': int(protos.shape[1]),
        'input_size': size,
        'preprocess': 'center-square crop, bilinear resize, RGB/255, NCHW float32',
        'temperature': t,
        'tau': tau,
        'target_accuracy': TARGET_ACCURACY,
        'blend_alpha': alpha,
        'n_species': len(classes),
        'onnx_bytes': onnx_path.stat().st_size,
        'metrics': metrics,
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    (models_dir / f'plantid_{version}.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    append_run('plantid', metrics, {'model_version': version, 'backbone': model_name,
                                    'temperature': t, 'tau': tau})
    print(f'wrote {onnx_path} ({onnx_path.stat().st_size / 1e6:.1f} MB), '
          f'config and prototypes')


if __name__ == '__main__':
    main()
