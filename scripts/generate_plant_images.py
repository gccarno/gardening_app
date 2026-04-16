"""
Generate plant icons — supports two backends:

  --backend ollama     (default) calls Ollama /api/generate
                       NOTE: Ollama image generation is macOS-only; fails on Windows/Linux.
  --backend diffusers  calls HuggingFace diffusers directly on your local GPU.
                       Requires: pip install torch --index-url https://download.pytorch.org/whl/cu121
                                 uv sync --extra imggen   (or pip install diffusers transformers accelerate safetensors)

Saves PNGs to apps/api/static/plant_ai_images/
Logs every attempt to plant_ai_images/experiments.jsonl for experiment tracking.

Usage:
    uv run python scripts/generate_plant_images.py --list-prompts
    uv run python scripts/generate_plant_images.py --plant-id 1 --dry-run
    uv run python scripts/generate_plant_images.py --plant-id 1 --compare
    uv run python scripts/generate_plant_images.py --plant-id 1 --prompt 3
    uv run python scripts/generate_plant_images.py --limit 20
    uv run python scripts/generate_plant_images.py --report

    # Ollama (macOS only):
    uv run python scripts/generate_plant_images.py --model x/flux2-klein:4b --plant-id 1 --compare

    # HuggingFace diffusers (Windows/Linux, local GPU):
    uv run python scripts/generate_plant_images.py --backend diffusers --hf-model sd-turbo --plant-id 1 --compare
    uv run python scripts/generate_plant_images.py --backend diffusers --hf-model sdxl-turbo --plant-id 1
    uv run python scripts/generate_plant_images.py --backend diffusers --hf-model sdxl-lightning --plant-id 1
    uv run python scripts/generate_plant_images.py --backend diffusers --hf-model flux-schnell --cpu-offload --plant-id 1
    uv run python scripts/generate_plant_images.py --backend diffusers --hf-model flux-schnell-gguf --cpu-offload --plant-id 1

HF model presets (--hf-model):
    sd-turbo          stabilityai/sd-turbo              ~2-3 GB VRAM, 512px, 1-4 steps  ← fastest
    sdxl-turbo        stabilityai/sdxl-turbo            ~6 GB VRAM, 512px, 1-4 steps
    sdxl-lightning    ByteDance/SDXL-Lightning           ~6 GB VRAM, 1024px, 4 steps
    flux-schnell      black-forest-labs/FLUX.1-schnell   ~6 GB w/ --cpu-offload, 1024px  ← best quality, slow
    flux-schnell-gguf gpustack/FLUX.1-schnell-GGUF Q4_0 ~5-6 GB w/ --cpu-offload, 1024px ← best balance

First-time Ollama setup (macOS only):
    ollama pull x/z-image-turbo
    ollama pull x/flux2-klein:4b
"""
import argparse
import base64
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import logging
import requests
from dotenv import load_dotenv

load_dotenv()  # picks up HF_TOKEN and other secrets from .env

_REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH    = os.path.join(_REPO_ROOT, 'apps', 'api', 'instance', 'garden.db')
_OUT_DIR    = os.path.join(_REPO_ROOT, 'apps', 'api', 'static', 'plant_ai_images')
_LOG_PATH   = os.path.join(_OUT_DIR, 'experiments.jsonl')
_RUN_LOG    = os.path.join(_REPO_ROOT, 'logs', 'plant_image_gen.log')

# Add backend to path for SessionLocal / PlantLibraryImage imports
sys.path.insert(0, os.path.join(_REPO_ROOT, 'apps', 'backend'))

logger = logging.getLogger('imggen')


def setup_logging(log_file: str = _RUN_LOG) -> None:
    """Configure logger to write to both console and a persistent log file."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    fmt = logging.Formatter('%(asctime)s  %(levelname)-8s  %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    logger.setLevel(logging.DEBUG)

    # File handler — append so nightly runs accumulate in one file
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler — INFO and above only
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)


# ─────────────────────────────────────────────────────────────────────────────
# DB registration
# ─────────────────────────────────────────────────────────────────────────────

import hashlib
import re as _re

# Matches normal-mode output: {id}_{slug}.png  (NOT compare-mode {id}_{slug}_s{N}.png)
_NORMAL_PNG_RE = _re.compile(r'^(\d+)_[a-z0-9_]+(?<!_s\d)\.png$')


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def register_image_in_db(plant_id: int, filename: str, file_path: str, model_label: str) -> str:
    """
    Insert a row into plant_library_image for an AI-generated PNG.
    Returns 'inserted' | 'duplicate' | 'error:<msg>'
    Skips compare-mode files (name ends in _sN.png).
    """
    if not _NORMAL_PNG_RE.match(filename):
        return 'skip'  # compare-mode file — not a canonical library image

    try:
        from app.db.session import SessionLocal
        from app.db.models import PlantLibraryImage
    except ImportError as e:
        return f'error:import:{e}'

    file_hash = _sha256(file_path)
    db = SessionLocal()
    try:
        exists = db.query(PlantLibraryImage).filter_by(file_hash=file_hash).first()
        if exists:
            return 'duplicate'

        img = PlantLibraryImage(
            plant_library_id = plant_id,
            filename         = f'plant_ai_images/{filename}',
            source           = 'ai-generated',
            source_url       = None,
            attribution      = f'AI generated — {model_label}',
            file_hash        = file_hash,
            is_primary       = False,
        )
        db.add(img)
        db.commit()
        return 'inserted'
    except Exception as e:
        db.rollback()
        return f'error:{e}'
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Naming helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')
    return s or 'plant'


def png_filename(plant: dict, strategy_index: int | None = None) -> str:
    base = f'{plant["id"]}_{slugify(plant["name"])}'
    return f'{base}_s{strategy_index}.png' if strategy_index is not None else f'{base}.png'


# ─────────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────────

_PLANT_COLS = (
    'id', 'name', 'scientific_name', 'type',
    'flower_color', 'foliage_color', 'fruit_color',
    'growth_habit', 'ligneous_type', 'average_height_cm',
    'thorny', 'tropical', 'indoor', 'attracts',
)


def load_plants(
    plant_id: int | None,
    limit: int | None,
    id_from: int | None = None,
    id_to: int | None = None,
) -> list[dict]:
    if not os.path.exists(_DB_PATH):
        sys.exit(f'ERROR: database not found at {_DB_PATH}')
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cols = ', '.join(_PLANT_COLS)
    if plant_id is not None:
        rows = cur.execute(f'SELECT {cols} FROM plant_library WHERE id = ?', (plant_id,)).fetchall()
    elif id_from is not None or id_to is not None:
        lo = id_from or 1
        hi = id_to or 999_999
        rows = cur.execute(
            f'SELECT {cols} FROM plant_library WHERE id >= ? AND id <= ? ORDER BY id',
            (lo, hi),
        ).fetchall()
    else:
        rows = cur.execute(f'SELECT {cols} FROM plant_library ORDER BY id').fetchall()
    conn.close()
    plants = [dict(r) for r in rows]
    return plants[:limit] if limit else plants


# ─────────────────────────────────────────────────────────────────────────────
# Prompt strategies
# ─────────────────────────────────────────────────────────────────────────────

_NEG_STANDARD = 'text, watermark, logo, signature, blurry, low quality, ugly, deformed'
_NEG_TIGHT    = 'text, watermark, background clutter, landscape, multiple plants, blurry, low quality'
_NEG_PHOTO    = 'cartoon, illustration, drawing, painting, sketch, text, watermark'


def _colors(p: dict) -> str:
    parts = [c for c in [p.get('fruit_color'), p.get('flower_color'), p.get('foliage_color')] if c]
    return ', '.join(parts) if parts else 'green'


def _traits(p: dict) -> str:
    t = []
    if p.get('thorny'):   t.append('thorny with spines')
    if p.get('tropical'): t.append('tropical lush')
    if p.get('indoor'):   t.append('houseplant')
    return ', '.join(t)


def _type_word(p: dict) -> str:
    return (p.get('type') or 'plant').lower()


STRATEGIES: list[dict] = [
    {
        'name': 'simple',
        'description': 'Cute cartoon icon, flat design, white background — clean and minimal',
        'prompt': lambda p: f'cute cartoon icon of {p["name"]}, flat design, simple, white background, plant illustration, colorful',
        'negative': _NEG_STANDARD,
    },
    {
        'name': 'emoji-sticker',
        'description': 'Round emoji-style sticker with thick white border',
        'prompt': lambda p: f'round emoji sticker of {p["name"]}, circular design, thick white border, cute, simple, bright colors, plant emoji',
        'negative': _NEG_STANDARD,
    },
    {
        'name': 'flat-vector',
        'description': 'Flat Material Design vector icon with dominant plant color',
        'prompt': lambda p: f'flat vector icon of {p["name"]}, material design style, {_colors(p)} color palette, clean geometric shapes, white background, minimal',
        'negative': _NEG_STANDARD,
    },
    {
        'name': 'pixel-art',
        'description': '16-bit pixel art game sprite',
        'prompt': lambda p: f'pixel art icon of {p["name"]}, 16-bit retro game sprite style, simple pixel grid, bright limited color palette, white background',
        'negative': 'photo-realistic, blurry, soft edges, gradient, text, watermark',
    },
    {
        'name': 'watercolor',
        'description': 'Light watercolor sketch, playful and soft',
        'prompt': lambda p: f'watercolor illustration of {p["name"]}, light soft colors, loose brushwork, playful botanical sketch, white background, artistic',
        'negative': 'photo, realistic, digital art, harsh lines, text, watermark',
    },
    {
        'name': 'botanical',
        'description': 'Vintage botanical woodcut / engraving line art',
        'prompt': lambda p: f'vintage botanical illustration of {p["name"]}, woodcut engraving style, detailed line art, scientific botanical drawing, cream paper background',
        'negative': 'color photo, digital art, cartoon, text, watermark, blurry',
    },
    {
        'name': 'seed-packet',
        'description': 'Charming vintage seed packet label art',
        'prompt': lambda p: f'vintage seed packet label art of {p["name"]}, charming retro illustration, hand-drawn style, colorful, ornate border, nostalgic',
        'negative': 'photo, modern design, text, blurry, watermark',
    },
    {
        'name': 'folk-art',
        'description': 'Bold folk art with simple shapes and bright saturated colors',
        'prompt': lambda p: f'folk art illustration of {p["name"]}, simple bold shapes, bright saturated colors, naive art style, decorative, white background',
        'negative': _NEG_STANDARD,
    },
    {
        'name': 'with-features',
        'description': 'Uses DB fields: type, colors, traits for a detailed tailored prompt',
        'prompt': lambda p: (
            f'illustration of {p["name"]}, {_type_word(p)}, '
            f'{_colors(p)} colors, '
            + (f'{_traits(p)}, ' if _traits(p) else '')
            + 'cute garden icon, white background, clear subject'
        ),
        'negative': _NEG_STANDARD,
    },
    {
        'name': 'tight-crop',
        'description': 'Tightly framed single subject, no background clutter',
        'prompt': lambda p: f'{p["name"]} only, centered, tightly cropped, single plant subject, clean white background, detailed illustration, high contrast',
        'negative': _NEG_TIGHT,
    },
    {
        'name': 'negative-heavy',
        'description': 'Simple prompt with an aggressive negative to eliminate clutter',
        'prompt': lambda p: f'cute icon of {p["name"]}, simple illustration',
        'negative': 'text, people, animals, complex background, photo-realism, blurry, low quality, ugly, extra plants, landscape, outdoor scene, watermark, signature',
    },
    {
        'name': 'studio-shot',
        'description': 'Clean product / studio photo style, top-down on white',
        'prompt': lambda p: f'professional studio photograph of fresh {p["name"]}, top-down view, white background, clean product photography, sharp focus, isolated',
        'negative': _NEG_PHOTO,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Ollama image generation API
# ─────────────────────────────────────────────────────────────────────────────

def call_generate(
    prompt: str,
    negative_prompt: str,
    model: str,
    base_url: str,
    width: int,
    height: int,
    steps: int,
    timeout: int = 300,
) -> bytes:
    """Call /api/generate. Returns raw PNG bytes."""
    payload: dict = {
        'model':  model,
        'prompt': prompt,
        'stream': False,
        'width':  width,
        'height': height,
        'steps':  steps,
    }
    if negative_prompt:
        payload['negative_prompt'] = negative_prompt

    r = requests.post(f'{base_url}/api/generate', json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    if 'image' not in data:
        raise ValueError(f'No "image" key in response. Keys: {list(data.keys())}')

    return base64.b64decode(data['image'])


# ─────────────────────────────────────────────────────────────────────────────
# HuggingFace diffusers backend
# ─────────────────────────────────────────────────────────────────────────────

# Map short preset names → HuggingFace model IDs
_HF_PRESETS: dict[str, str] = {
    'sd-turbo':          'stabilityai/sd-turbo',
    'sdxl-turbo':        'stabilityai/sdxl-turbo',
    'sdxl-lightning':    'ByteDance/SDXL-Lightning',
    'flux-schnell':      'black-forest-labs/FLUX.1-schnell',
    'flux-schnell-gguf': 'gpustack/FLUX.1-schnell-GGUF',
}

# SDXL-Lightning base model (needed alongside the LoRA UNet)
_SDXL_LIGHTNING_BASE = 'stabilityai/stable-diffusion-xl-base-1.0'

# Cached pipelines keyed by resolved HF model ID
_PIPE_CACHE: dict[str, object] = {}


def _resolve_hf_model(hf_model: str) -> str:
    """Expand preset shorthand to full HF model ID."""
    return _HF_PRESETS.get(hf_model, hf_model)


def _load_diffusers_pipeline(hf_model_id: str, cpu_offload: bool) -> object:
    """Load (and cache) a diffusers pipeline for the given model ID."""
    if hf_model_id in _PIPE_CACHE:
        return _PIPE_CACHE[hf_model_id]

    try:
        import torch
        from diffusers import (
            AutoPipelineForText2Image,
            FluxPipeline,
            StableDiffusionXLPipeline,
            UNet2DConditionModel,
            EulerDiscreteScheduler,
        )
    except ImportError as exc:
        sys.exit(
            f'ERROR: diffusers backend requires extra packages.\n'
            f'  pip install torch --index-url https://download.pytorch.org/whl/cu121\n'
            f'  uv sync --extra imggen\n'
            f'Original error: {exc}'
        )

    if not torch.cuda.is_available():
        print('WARNING: CUDA not available — diffusers will run on CPU (very slow).')

    print(f'  [diffusers] loading model: {hf_model_id} ...', flush=True)

    # ── FLUX.1-schnell GGUF (Q4 quantized) ───────────────────────────────────
    if hf_model_id == 'gpustack/FLUX.1-schnell-GGUF':
        try:
            from diffusers import FluxTransformer2DModel, GGUFQuantizationConfig
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            sys.exit(f'ERROR: FLUX GGUF requires gguf package: pip install gguf\nOriginal error: {exc}')

        gguf_path = hf_hub_download(
            repo_id='gpustack/FLUX.1-schnell-GGUF',
            filename='FLUX.1-schnell-Q4_0.gguf',
        )
        transformer = FluxTransformer2DModel.from_single_file(
            gguf_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        )
        pipe = FluxPipeline.from_pretrained(
            'black-forest-labs/FLUX.1-schnell',
            transformer=transformer,
            torch_dtype=torch.bfloat16,
        )

    # ── FLUX.1-schnell (full fp16 with CPU offload) ───────────────────────────
    elif 'FLUX.1-schnell' in hf_model_id or hf_model_id == 'black-forest-labs/FLUX.1-schnell':
        pipe = FluxPipeline.from_pretrained(hf_model_id, torch_dtype=torch.bfloat16)

    # ── SDXL-Lightning (UNet swap + LoRA) ─────────────────────────────────────
    elif 'SDXL-Lightning' in hf_model_id or hf_model_id == 'ByteDance/SDXL-Lightning':
        try:
            from safetensors.torch import load_file
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            sys.exit(f'ERROR: SDXL-Lightning requires safetensors: pip install safetensors huggingface-hub\nOriginal: {exc}')

        unet = UNet2DConditionModel.from_config(
            _SDXL_LIGHTNING_BASE, subfolder='unet'
        ).to('cuda', dtype=torch.float16)
        ckpt_path = hf_hub_download(
            repo_id='ByteDance/SDXL-Lightning',
            filename='sdxl_lightning_4step_unet.safetensors',
        )
        unet.load_state_dict(load_file(ckpt_path, device='cuda'))
        pipe = StableDiffusionXLPipeline.from_pretrained(
            _SDXL_LIGHTNING_BASE, unet=unet, torch_dtype=torch.float16, variant='fp16'
        ).to('cuda')
        pipe.scheduler = EulerDiscreteScheduler.from_config(
            pipe.scheduler.config, timestep_spacing='trailing'
        )
        pipe.enable_attention_slicing()
        _PIPE_CACHE[hf_model_id] = pipe
        return pipe  # already on device, skip the offload/to block below

    # ── SD-Turbo / SDXL-Turbo / generic AutoPipeline ─────────────────────────
    else:
        dtype = torch.float16
        pipe = AutoPipelineForText2Image.from_pretrained(
            hf_model_id, torch_dtype=dtype, variant='fp16'
        )

    # Apply offload or move to GPU
    if cpu_offload:
        pipe.enable_model_cpu_offload()
    else:
        pipe = pipe.to('cuda')
        if hasattr(pipe, 'enable_attention_slicing'):
            pipe.enable_attention_slicing()

    _PIPE_CACHE[hf_model_id] = pipe
    return pipe


def call_generate_diffusers(
    prompt: str,
    hf_model: str,
    cpu_offload: bool,
    width: int,
    height: int,
    steps: int,
) -> bytes:
    """Generate image via HuggingFace diffusers. Returns raw PNG bytes."""
    import io
    import torch

    model_id = _resolve_hf_model(hf_model)
    pipe = _load_diffusers_pipeline(model_id, cpu_offload)

    is_flux = 'FLUX' in model_id or 'flux' in model_id
    is_sdxl_lightning = 'SDXL-Lightning' in model_id
    is_turbo = 'turbo' in model_id.lower()

    kwargs: dict = {'prompt': prompt, 'width': width, 'height': height}

    if is_flux:
        kwargs['num_inference_steps'] = steps
        kwargs['max_sequence_length'] = 256
        kwargs['guidance_scale'] = 0.0
    elif is_sdxl_lightning:
        kwargs['num_inference_steps'] = steps
        kwargs['guidance_scale'] = 0.0
    elif is_turbo:
        kwargs['num_inference_steps'] = steps
        kwargs['guidance_scale'] = 0.0
    else:
        kwargs['num_inference_steps'] = steps

    with torch.inference_mode():
        result = pipe(**kwargs)

    image = result.images[0]
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Experiment logging
# ─────────────────────────────────────────────────────────────────────────────

def log_experiment(entry: dict) -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def build_log_entry(
    run_id: str,
    plant: dict,
    strategy: dict,
    strategy_idx: int,
    args,
    status: str,
    duration_ms: int,
    filename: str = '',
    file_size: int = 0,
    error: str = '',
    prompt: str = '',
    negative: str = '',
) -> dict:
    # Record whichever model identifier is active
    if getattr(args, 'backend', 'ollama') == 'diffusers':
        model_logged = f'diffusers:{_resolve_hf_model(args.hf_model)}'
    else:
        model_logged = args.model

    entry: dict = {
        'run_id':        run_id,
        'ts':            datetime.now(timezone.utc).isoformat(),
        'plant_id':      plant['id'],
        'plant_name':    plant['name'],
        'strategy':      strategy_idx,
        'strategy_name': strategy['name'],
        'model':         model_logged,
        'backend':       getattr(args, 'backend', 'ollama'),
        'prompt':        prompt,
        'negative_prompt': negative,
        'width':         args.width,
        'height':        args.height,
        'steps':         args.steps,
        'duration_ms':   duration_ms,
        'file_size':     file_size,
        'status':        status,
        'filename':      filename,
    }
    if error:
        entry['error'] = error
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# Per-plant generation
# ─────────────────────────────────────────────────────────────────────────────

def run_strategy(
    plant: dict,
    strategy: dict,
    strategy_idx: int,
    run_id: str,
    args,
    out_filename: str,
) -> str:
    """
    Generate image for plant using strategy.
    Returns status string: 'ok' | 'error:...' | 'dry_run'
    Logs to experiments.jsonl.
    """
    prompt   = strategy['prompt'](plant)
    negative = args.negative or strategy.get('negative', '')

    if args.dry_run:
        backend_info = f'backend={args.backend}'
        if args.backend == 'diffusers':
            backend_info += f' hf-model={args.hf_model}'
        print(f'\n  [dry-run] strategy="{strategy["name"]}" {backend_info} prompt="{prompt[:80]}..."')
        log_experiment(build_log_entry(
            run_id, plant, strategy, strategy_idx, args,
            status='dry_run', duration_ms=0, prompt=prompt, negative=negative,
        ))
        return 'dry_run'

    out_path = os.path.join(_OUT_DIR, out_filename)
    t0 = time.time()
    try:
        if args.backend == 'diffusers':
            png_bytes = call_generate_diffusers(
                prompt, args.hf_model, args.cpu_offload,
                args.width, args.height, args.steps,
            )
        else:
            png_bytes = call_generate(
                prompt, negative, args.model, args.ollama_url,
                args.width, args.height, args.steps,
            )
    except (requests.exceptions.RequestException, Exception) as exc:
        duration_ms = int((time.time() - t0) * 1000)
        err = str(exc)
        log_experiment(build_log_entry(
            run_id, plant, strategy, strategy_idx, args,
            status='error', duration_ms=duration_ms, error=err, prompt=prompt, negative=negative,
        ))
        return f'error:{err}'

    duration_ms = int((time.time() - t0) * 1000)

    with open(out_path, 'wb') as f:
        f.write(png_bytes)
    file_size = len(png_bytes)

    log_experiment(build_log_entry(
        run_id, plant, strategy, strategy_idx, args,
        status='ok', duration_ms=duration_ms,
        filename=out_filename, file_size=file_size,
        prompt=prompt, negative=negative,
    ))

    # Register in PlantLibraryImage unless opted out
    if not getattr(args, 'no_db_register', False):
        model_label = (
            f'diffusers/{_resolve_hf_model(args.hf_model)}' if args.backend == 'diffusers'
            else f'ollama/{args.model}'
        )
        db_status = register_image_in_db(plant['id'], out_filename, out_path, model_label)
        if db_status not in ('inserted', 'duplicate', 'skip'):
            logger.warning('DB register failed for %s: %s', out_filename, db_status)

    return 'ok'


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def _register_existing_pngs(args) -> None:
    """Scan output dir, register every normal-mode PNG that isn't in the DB yet."""
    if not os.path.isdir(_OUT_DIR):
        print(f'Output dir not found: {_OUT_DIR}')
        return

    model_label = (
        f'diffusers/{_resolve_hf_model(args.hf_model)}' if args.backend == 'diffusers'
        else f'ollama/{args.model}'
    )

    pngs = sorted(f for f in os.listdir(_OUT_DIR) if f.endswith('.png'))
    n_inserted = n_duplicate = n_skip = n_error = 0

    for fname in pngs:
        m = _NORMAL_PNG_RE.match(fname)
        if not m:
            n_skip += 1
            continue
        plant_id = int(m.group(1))
        fpath = os.path.join(_OUT_DIR, fname)
        status = register_image_in_db(plant_id, fname, fpath, model_label)
        if status == 'inserted':
            n_inserted += 1
        elif status == 'duplicate':
            n_duplicate += 1
        elif status == 'skip':
            n_skip += 1
        else:
            n_error += 1
            logger.warning('register_existing: %s → %s', fname, status)

    logger.info(
        'register_existing: inserted=%d  duplicate=%d  skip=%d  errors=%d  total=%d',
        n_inserted, n_duplicate, n_skip, n_error, len(pngs),
    )
    print(f'Done.  inserted={n_inserted}  duplicate={n_duplicate}  '
          f'skip(compare-mode)={n_skip}  errors={n_error}')


def print_report() -> None:
    if not os.path.exists(_LOG_PATH):
        print(f'No experiment log found at {_LOG_PATH}')
        return

    from collections import defaultdict

    rows: list[dict] = []
    with open(_LOG_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not rows:
        print('Log is empty.')
        return

    # Group by (strategy_name, model)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get('status') == 'dry_run':
            continue
        key = (r.get('strategy_name', '?'), r.get('model', '?'))
        groups[key].append(r)

    print(f'\n{"Strategy":<20} {"Model":<26} {"N":>5} {"Avg ms":>8} {"Avg KB":>8} {"Errors":>7}')
    print('-' * 78)
    for (strat, model), entries in sorted(groups.items()):
        ok      = [e for e in entries if e['status'] == 'ok']
        errors  = len([e for e in entries if e['status'] == 'error'])
        avg_ms  = int(sum(e['duration_ms'] for e in ok) / len(ok)) if ok else 0
        avg_kb  = sum(e['file_size'] for e in ok) / len(ok) / 1024 if ok else 0
        print(f'{strat:<20} {model:<26} {len(entries):>5} {avg_ms:>8} {avg_kb:>7.1f}K {errors:>7}')

    print(f'\nTotal entries: {len(rows)}  (log: {_LOG_PATH})')


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    presets = ', '.join(_HF_PRESETS.keys())
    p = argparse.ArgumentParser(
        description='Generate plant icons via Ollama (macOS) or HuggingFace diffusers (local GPU)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('--list-prompts',      action='store_true', help='List all prompt strategies and exit')
    p.add_argument('--report',            action='store_true', help='Print experiment summary from log and exit')
    p.add_argument('--register-existing', action='store_true', dest='register_existing',
                   help='Scan output dir and register all existing PNGs in the DB, then exit')
    p.add_argument('--no-db-register',    action='store_true', dest='no_db_register',
                   help='Skip PlantLibraryImage DB registration after generation')
    p.add_argument('--prompt',    type=int,   default=0,   help='Prompt strategy index (see --list-prompts)')
    p.add_argument('--compare',   action='store_true',     help='Run ALL strategies on --plant-id')
    p.add_argument('--limit',    type=int, default=None, help='Stop after N plants')
    p.add_argument('--plant-id', type=int, default=None, dest='plant_id',
                   help='Generate for a single plant ID')
    p.add_argument('--id-from',  type=int, default=None, dest='id_from',
                   help='Start of plant ID range (inclusive)')
    p.add_argument('--id-to',    type=int, default=None, dest='id_to',
                   help='End of plant ID range (inclusive)')
    p.add_argument('--overwrite', action='store_true',     help='Regenerate even if file exists')
    p.add_argument('--width',     type=int,   default=512)
    p.add_argument('--height',    type=int,   default=512)
    p.add_argument('--steps',     type=int,   default=4,   help='Inference steps (default 4 works for all backends)')
    p.add_argument('--negative',  type=str,   default='',  help='Override negative prompt (Ollama only)')
    p.add_argument('--delay',      type=float, default=0.5, help='Seconds between requests')
    p.add_argument('--time-limit', type=int,   default=0,   dest='time_limit',
                   help='Stop after N minutes (0 = no limit). Finishes current image before stopping.')
    p.add_argument('--dry-run',    action='store_true')

    # ── Ollama backend (original, macOS-only) ────────────────────────────────
    ollama = p.add_argument_group('Ollama backend (--backend ollama, macOS only)')
    ollama.add_argument('--model',      type=str, default='x/z-image-turbo',
                        help='Ollama model name')
    ollama.add_argument('--ollama-url', type=str, default='http://localhost:11434',
                        dest='ollama_url')

    # ── HuggingFace diffusers backend ────────────────────────────────────────
    hf = p.add_argument_group('HuggingFace diffusers backend (--backend diffusers)')
    hf.add_argument('--backend',    type=str, default='ollama', choices=['ollama', 'diffusers'],
                    help='Image generation backend (default: ollama)')
    hf.add_argument('--hf-model',   type=str, default='sd-turbo', dest='hf_model',
                    help=f'Model preset or full HF repo ID. Presets: {presets}')
    hf.add_argument('--cpu-offload', action='store_true', dest='cpu_offload',
                    help='Enable model CPU offload (needed for FLUX on 6 GB VRAM)')

    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    setup_logging()

    if args.list_prompts:
        print(f'{"#":<4} {"Name":<20} {"Neg prompt snippet":<30} Description')
        print('-' * 90)
        for i, s in enumerate(STRATEGIES):
            neg_snip = (s.get('negative', '') or '')[:28]
            print(f'{i:<4} {s["name"]:<20} {neg_snip:<30} {s["description"]}')
        return

    if args.report:
        print_report()
        return

    if args.register_existing:
        _register_existing_pngs(args)
        return

    os.makedirs(_OUT_DIR, exist_ok=True)

    plants = load_plants(args.plant_id, args.limit, args.id_from, args.id_to)
    if not plants:
        logger.info('No plants found matching filters — nothing to do.')
        sys.exit(0)

    run_id = secrets.token_hex(2)  # 4-char hex shared across this run
    run_wall_start = time.time()
    time_limit_secs = args.time_limit * 60 if args.time_limit else None

    # ── Compare mode ──────────────────────────────────────────────────────────
    if args.compare:
        if not args.plant_id:
            sys.exit('--compare requires --plant-id')
        plant = plants[0]
        print(f'run_id={run_id}  Comparing {len(STRATEGIES)} strategies for '
              f'"{plant["name"]}" (id={plant["id"]})  model={args.model}')
        if args.dry_run:
            print('[DRY RUN]')

        for idx, strategy in enumerate(STRATEGIES):
            fname    = png_filename(plant, strategy_index=idx)
            out_path = os.path.join(_OUT_DIR, fname)
            label    = f'[{idx:>2}] {strategy["name"]:<20}'
            print(f'  {label} → {fname} ... ', end='', flush=True)

            if not args.overwrite and not args.dry_run and os.path.exists(out_path):
                print('skip (exists)')
                continue

            t0     = time.time()
            status = run_strategy(plant, strategy, idx, run_id, args, fname)
            elapsed = time.time() - t0

            if status == 'ok':
                size_kb = os.path.getsize(out_path) / 1024
                print(f'ok  {elapsed:.1f}s  {size_kb:.1f}KB')
            elif status == 'dry_run':
                pass
            else:
                print(status)

            if not args.dry_run and idx < len(STRATEGIES) - 1:
                time.sleep(args.delay)

        print(f'\nOutputs in: {_OUT_DIR}')
        print(f'Log:        {_LOG_PATH}')
        return

    # ── Normal mode ───────────────────────────────────────────────────────────
    if args.prompt >= len(STRATEGIES):
        sys.exit(f'Invalid --prompt {args.prompt}. Max={len(STRATEGIES)-1}. Use --list-prompts.')
    strategy = STRATEGIES[args.prompt]

    if not args.overwrite:
        plants = [p for p in plants if not os.path.exists(os.path.join(_OUT_DIR, png_filename(p)))]

    total = len(plants)
    if total == 0:
        logger.info(
            'run_id=%s  All plants in range already have images — nothing to do.', run_id
        )
        return

    backend_label = (
        f'diffusers:{_resolve_hf_model(args.hf_model)}' if args.backend == 'diffusers'
        else f'ollama:{args.model}'
    )
    limit_label = f'{args.time_limit}min' if time_limit_secs else 'no limit'
    logger.info(
        'run_id=%s  START  strategy=[%d]"%s"  backend=%s  plants=%d  time_limit=%s',
        run_id, args.prompt, strategy["name"], backend_label, total, limit_label,
    )
    print(f'run_id={run_id}  Strategy [{args.prompt}] "{strategy["name"]}"  '
          f'backend={backend_label}  plants={total}')
    if args.dry_run:
        print('[DRY RUN]')

    n_ok = n_error = n_skip = n_timeout = 0

    for i, plant in enumerate(plants, 1):
        # ── Time limit check ─────────────────────────────────────────────────
        if time_limit_secs and (time.time() - run_wall_start) >= time_limit_secs:
            elapsed_min = (time.time() - run_wall_start) / 60
            logger.info(
                'run_id=%s  TIME LIMIT reached after %.1f min — stopping.'
                '  ok=%d  errors=%d  remaining=%d',
                run_id, elapsed_min, n_ok, n_error, total - i + 1,
            )
            n_timeout = total - i + 1
            break

        fname    = png_filename(plant)
        label    = f'{plant["name"][:30]:<30}'
        print(f'  [{i:>5}/{total}] {label} → {fname} ... ', end='', flush=True)

        t0     = time.time()
        status = run_strategy(plant, strategy, args.prompt, run_id, args, fname)
        elapsed = time.time() - t0

        if status == 'ok':
            size_kb = os.path.getsize(os.path.join(_OUT_DIR, fname)) / 1024
            n_ok += 1
            print(f'ok  {elapsed:.1f}s  {size_kb:.1f}KB')
        elif status == 'dry_run':
            n_skip += 1
        else:
            n_error += 1
            logger.warning('run_id=%s  ERROR plant_id=%d "%s": %s',
                           run_id, plant['id'], plant['name'], status)
            print(status)

        if not args.dry_run and i < total:
            time.sleep(args.delay)

    wall_elapsed = time.time() - run_wall_start
    logger.info(
        'run_id=%s  END  ok=%d  errors=%d  dry_run=%d  timed_out=%d  elapsed=%.1fs',
        run_id, n_ok, n_error, n_skip, n_timeout, wall_elapsed,
    )
    print(f'\nDone.  ok={n_ok}  errors={n_error}  dry_run={n_skip}'
          + (f'  timed_out={n_timeout}' if n_timeout else ''))
    print(f'Log: {_LOG_PATH}')
    print(f'Run log: {_RUN_LOG}')


if __name__ == '__main__':
    main()
