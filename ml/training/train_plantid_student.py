"""
Plant-ID: distil BioCLIP (teacher, 86M) into a client-sized student
(see ml/docs/PLANT_ID_MODEL.md, stage 5).

The student learns to put photos where BioCLIP would — in BioCLIP's 512-d
embedding space — so the offline prototypes (BioCLIP image means blended with
BioCLIP text embeddings of every species name) work unchanged for student
queries, including for species with only one or two library photos.

Loss, on the same augmented crop fed to both models:
    1 - cos(student, teacher)                         embedding regression
  + λ · KL(p_teacher || p_student) over species        what we actually serve:
        where p = softmax(emb · text_prototypesᵀ / κ)  the ranking over species

Data is unlabelled (ml/data/build_plantid_distill_set.py), so eval labels
can't leak. Model selection uses the eval set's *calibration* half only; the
test half is first touched by ml/training/export_plantid_onnx.py.

Run (needs the vision stack + CUDA torch):
    uv run --no-sync python ml/training/train_plantid_student.py --student mobileclip2_s0 --epochs 1 --max-images 8000 --tag pilot
    uv run --no-sync python ml/training/train_plantid_student.py --student mobileclip2_s0 --epochs 15 --tag v1

On Colab (no DB; see ml/notebooks/plantid_distill_colab.ipynb):
    python ml/training/train_plantid_student.py --bundle /content/bundle --out-dir /content/drive/MyDrive/plantid         --student mobileclip2_s0 --epochs 15 --workers 2 --tag v1 [--resume]
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.evaluation.metrics_history import append_run  # noqa: E402
from ml.evaluation.plantid_metrics import topk_accuracy  # noqa: E402
from ml.experiments.plantid_backbones import (  # noqa: E402
    BACKBONES, RESULTS_PATH, SEED, build_prototypes, embed_paths, load_backbone)
from ml.features.plantid_data import CACHE_DIR, eval_manifest, library_manifest, load_bundle  # noqa: E402
from ml.features.plantid_preprocess import load_and_preprocess  # noqa: E402

DISTILL_DIR = _ROOT / 'ml' / 'data' / 'raw' / 'plantid_distill'
INPUT_SIZE = 224      # BioCLIP's resolution; the student is trained and served at it
KAPPA = 0.01          # softmax temperature for the KL term (CLIP's logit scale ~100)
STUDENTS = ('mobileclip2_s0', 'dinov2_s')


class _AugDataset:
    """Unlabelled photo -> one augmented [0, 1] crop (normalisation lives in the models)."""

    def __init__(self, paths):
        from torchvision import transforms as T
        self.paths = paths
        self.tf = T.Compose([
            T.RandomResizedCrop(INPUT_SIZE, scale=(0.35, 1.0)),
            T.RandomHorizontalFlip(),
            T.ColorJitter(0.2, 0.2, 0.1),
            T.ToTensor(),
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        from PIL import Image
        try:
            return self.tf(Image.open(self.paths[i]).convert('RGB'))
        except Exception:
            # Rare unreadable file: substitute a neighbour rather than break the batch.
            return self[(i + 1) % len(self.paths)]


def _normaliser(mean, std):
    import torch

    class Normalise(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer('mean', torch.tensor(mean, dtype=torch.float32).view(1, 3, 1, 1))
            self.register_buffer('std', torch.tensor(std, dtype=torch.float32).view(1, 3, 1, 1))

        def forward(self, x):
            return (x - self.mean) / self.std
    return Normalise()


def build_teacher(device):
    """BioCLIP image tower on [0, 1] input -> L2-normalised 512-d, plus its text encoder."""
    import open_clip
    import torch
    model, _, preprocess = open_clip.create_model_and_transforms(BACKBONES['bioclip']['name'])
    model = model.eval().to(device)
    norm = next(t for t in preprocess.transforms if type(t).__name__ == 'Normalize')
    tokenizer = open_clip.get_tokenizer(BACKBONES['bioclip']['name'])
    pre = _normaliser(norm.mean, norm.std).to(device)

    def encode_image(x):
        return torch.nn.functional.normalize(model.encode_image(pre(x)).float(), dim=-1)

    def encode_text(texts):
        return torch.nn.functional.normalize(
            model.encode_text(tokenizer(texts).to(device)).float(), dim=-1)
    return encode_image, encode_text


def build_student(key: str, out_dim: int = 512):
    """Pretrained backbone + linear head into the teacher's space, on [0, 1] input."""
    import torch
    spec = BACKBONES[key]
    if spec['kind'] == 'open_clip':
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            spec['name'], pretrained=spec.get('pretrained'))
        backbone = model.visual
        norm = next(t for t in preprocess.transforms if type(t).__name__ == 'Normalize')
        mean, std = norm.mean, norm.std
    else:
        import timm
        backbone = timm.create_model(spec['name'], pretrained=True, num_classes=0, img_size=INPUT_SIZE)
        cfg = timm.data.resolve_data_config({'input_size': (3, INPUT_SIZE, INPUT_SIZE)}, model=backbone)
        mean, std = cfg['mean'], cfg['std']
    with torch.no_grad():
        feat_dim = backbone(torch.zeros(1, 3, INPUT_SIZE, INPUT_SIZE)).shape[-1]

    class Student(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.pre = _normaliser(mean, std)
            self.backbone = backbone
            self.head = torch.nn.Linear(feat_dim, out_dim)

        def forward(self, pixels):
            return torch.nn.functional.normalize(self.head(self.backbone(self.pre(pixels))), dim=-1)
    return Student()


def teacher_prototypes(library, encode_text, classes):
    """BioCLIP image prototypes (cached embeddings) blended with text prototypes."""
    import torch
    alpha = json.loads(RESULTS_PATH.read_text(encoding='utf-8'))['bioclip']['blend_alpha']
    enc, transform, _, _ = load_backbone('bioclip')
    emb = embed_paths(enc, transform, [r['path'] for r in library], CACHE_DIR / 'bioclip_library.npz')
    del enc
    ok = ~np.isnan(emb).any(axis=1)
    img = build_prototypes(emb[ok], [r['species_key'] for r, g in zip(library, ok) if g], classes)
    texts = [f'a photo of {c.capitalize()}.' for c in classes]
    with torch.no_grad():
        txt = np.concatenate([encode_text(texts[i:i + 256]).cpu().numpy()
                              for i in range(0, len(texts), 256)])
    p = alpha * img + (1 - alpha) * txt
    return (p / np.linalg.norm(p, axis=1, keepdims=True)).astype(np.float32), txt.astype(np.float32), alpha


def _save_atomic(obj, path: Path):
    """torch.save via a temp file + rename, so a sync job or a dropped session never sees half a file."""
    import torch
    tmp = path.with_name(path.name + '.tmp')
    torch.save(obj, tmp)
    tmp.replace(path)


def _eval_calib(student, device, ev_arrays, labels, protos) -> float:
    """Top-1 on the calibration half, student query vs teacher prototypes."""
    import torch
    student.eval()
    out = []
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
        for i in range(0, len(ev_arrays), 128):
            x = torch.from_numpy(np.stack(ev_arrays[i:i + 128])).to(device)
            out.append(student(x).float().cpu().numpy())
    student.train()
    return topk_accuracy(np.concatenate(out) @ protos.T, labels, 1)


def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument('--student', required=True, choices=STUDENTS)
    ap.add_argument('--epochs', type=int, default=15)
    ap.add_argument('--batch', type=int, default=64)
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--kl-weight', type=float, default=1.0)
    ap.add_argument('--max-images', type=int, default=0, help='subsample the training set (pilots)')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--bundle', type=Path, help='train from a Colab bundle instead of the DB + local caches')
    ap.add_argument('--out-dir', type=Path, default=CACHE_DIR, help='where checkpoints go')
    ap.add_argument('--resume', action='store_true', help='continue from <out-dir>/..._last.pt')
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--workers', type=int, default=6)
    args = ap.parse_args()
    torch.manual_seed(SEED)
    device = args.device

    bundle = load_bundle(args.bundle) if args.bundle else None
    if bundle:
        paths = bundle['train_paths']
    else:
        paths = sorted((DISTILL_DIR / 'library').glob('*.jpg')) + sorted((DISTILL_DIR / 'inat').glob('*.jpg'))
    if args.max_images:
        rng = np.random.default_rng(SEED)
        paths = [paths[i] for i in rng.choice(len(paths), min(args.max_images, len(paths)), replace=False)]
    print(f'{len(paths)} training photos')

    teacher, encode_text = build_teacher(device)
    if bundle:
        classes = bundle['class_keys']
        protos, text_protos, alpha = bundle['teacher_protos'], bundle['teacher_text'], bundle['alpha']
        all_evals = bundle['evals']
    else:
        from apps.backend.app.db.session import SessionLocal
        db = SessionLocal()
        try:
            library = library_manifest(db)
        finally:
            db.close()
        classes = sorted({r['species_key'] for r in library})
        protos, text_protos, alpha = teacher_prototypes(library, encode_text, classes)
        all_evals = eval_manifest()
    index = {c: i for i, c in enumerate(classes)}
    text_t = torch.from_numpy(text_protos).to(device)

    # Calibration half of the eval set, preprocessed exactly as clients will.
    evals = [r for r in all_evals if r['species_key'] in index]
    species = sorted({r['species_key'] for r in evals})
    calib_species = set(np.random.default_rng(SEED).choice(species, size=len(species) // 2, replace=False))
    calib = [r for r in evals if r['species_key'] in calib_species]
    arrays = [(load_and_preprocess(r['path'], INPUT_SIZE), index[r['species_key']]) for r in calib]
    arrays = [(a, y) for a, y in arrays if a is not None]
    ev_arrays, ev_labels = [a for a, _ in arrays], np.array([y for _, y in arrays])

    student = build_student(args.student).to(device)
    loader = torch.utils.data.DataLoader(
        _AugDataset(paths), batch_size=args.batch, shuffle=True, num_workers=args.workers,
        persistent_workers=args.workers > 0, drop_last=True, pin_memory=True)
    head_params = list(student.head.parameters())
    opt = torch.optim.AdamW([
        {'params': student.backbone.parameters(), 'lr': args.lr},
        {'params': head_params, 'lr': args.lr * 10},
    ], weight_decay=0.05)
    total = args.epochs * len(loader)
    warmup = min(500, total // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: (s + 1) / warmup if s < warmup else 0.5 * (1 + math.cos(math.pi * (s - warmup) / max(1, total - warmup))))
    scaler = torch.amp.GradScaler()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = args.out_dir / f'student_{args.student}_{args.tag}.pt'          # best epoch
    last = args.out_dir / f'student_{args.student}_{args.tag}_last.pt'     # resume point
    history, step, start = [], 0, 1
    if args.resume and last.exists():
        state = torch.load(last, map_location=device)
        student.load_state_dict(state['state_dict'])
        opt.load_state_dict(state['optimizer'])
        sched.load_state_dict(state['scheduler'])
        scaler.load_state_dict(state['scaler'])
        history, step, best, start = state['history'], state['step'], state['best'], state['epoch'] + 1
        print(f'resumed after epoch {state["epoch"]} (best calib top-1 {best:.3f})')
    else:
        best = _eval_calib(student, device, ev_arrays, ev_labels, protos)
        print(f'epoch 0: calib top-1 {best:.3f} (untrained head)  |  teacher alpha={alpha}')
    for epoch in range(start, args.epochs + 1):
        t0, running = time.time(), {'cos': 0.0, 'kl': 0.0}
        for x in loader:
            x = x.to(device, non_blocking=True)
            with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
                t = teacher(x)
            with torch.autocast('cuda', dtype=torch.float16):
                s = student(x)
            s, t = s.float(), t.float()
            l_cos = (1 - (s * t).sum(-1)).mean()
            log_ps = torch.log_softmax(s @ text_t.T / KAPPA, dim=-1)
            log_pt = torch.log_softmax(t @ text_t.T / KAPPA, dim=-1)
            l_kl = torch.nn.functional.kl_div(log_ps, log_pt, log_target=True, reduction='batchmean')
            loss = l_cos + args.kl_weight * l_kl
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            step += 1
            running['cos'] += l_cos.item()
            running['kl'] += l_kl.item()
            if step % 100 == 0:
                print(f'  step {step}/{total}  cos {l_cos.item():.4f}  kl {l_kl.item():.3f}', end='\r')
        n = len(loader)
        top1 = _eval_calib(student, device, ev_arrays, ev_labels, protos)
        row = {'epoch': epoch, 'cos_loss': running['cos'] / n, 'kl_loss': running['kl'] / n,
               'calib_top1': top1, 'minutes': (time.time() - t0) / 60}
        history.append(row)
        print(f'\nepoch {epoch}: cos {row["cos_loss"]:.4f}  kl {row["kl_loss"]:.3f}  '
              f'calib top-1 {top1:.3f}  ({row["minutes"]:.1f} min)')
        if top1 > best:
            best = top1
            _save_atomic({'student': args.student, 'state_dict': student.state_dict(),
                          'epoch': epoch, 'calib_top1': top1, 'input_size': INPUT_SIZE}, ckpt)
        # Every epoch, so a dropped Colab session loses at most one.
        _save_atomic({'state_dict': student.state_dict(), 'optimizer': opt.state_dict(),
                      'scheduler': sched.state_dict(), 'scaler': scaler.state_dict(),
                      'epoch': epoch, 'step': step, 'best': best, 'history': history}, last)

    print(f'best calib top-1 {best:.3f} -> {ckpt}')
    append_run('plantid_student', {'best_calib_top1': best},
               {'student': args.student, 'tag': args.tag, 'epochs': args.epochs,
                'n_train': len(paths), 'kl_weight': args.kl_weight, 'lr': args.lr, 'history': history})


if __name__ == '__main__':
    main()
