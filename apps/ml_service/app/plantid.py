"""
On-device plant ID — server half. The client (web / Android) runs the ONNX
image tower and sends the embedding; the server ranks it against per-species
prototypes in Postgres (see PlantImagePrototype) and turns cosine similarities
into calibrated probabilities. No model is loaded here: the per-version config
is a small JSON file committed next to the ONNX artifact.

See ml/docs/PLANT_ID_MODEL.md.
"""
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

_MODELS_DIR = Path(__file__).resolve().parents[3] / 'ml' / 'models'
_VERSION_RE = re.compile(r'^[a-z0-9_]{1,40}$')


@lru_cache(maxsize=8)
def load_config(model_version: str) -> dict | None:
    """ml/models/plantid_<version>.json, or None if that version isn't deployed."""
    if not _VERSION_RE.match(model_version):
        return None
    path = _MODELS_DIR / f'plantid_{model_version}.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def probabilities(sims: list[float], max_sim: float, sum_exp: float, temperature: float) -> list[float]:
    """Softmax probabilities for `sims`, given the full-class normaliser.

    sum_exp = sum over ALL prototypes of exp((sim - max_sim) / T), computed in
    SQL — a top-k-only softmax would overstate confidence.
    """
    return [math.exp((s - max_sim) / temperature) / sum_exp for s in sims]


def model_path(model_version: str) -> Path | None:
    """The ONNX file for a deployed version, or None."""
    if load_config(model_version) is None:
        return None
    path = _MODELS_DIR / f'plantid_{model_version}.onnx'
    return path if path.exists() else None


def current_version() -> str | None:
    """PLANTID_MODEL_VERSION if set (pins a rollback), else the newest deployed config."""
    pinned = os.environ.get('PLANTID_MODEL_VERSION')
    if pinned:
        return pinned if load_config(pinned) else None
    configs = [load_config(p.stem.removeprefix('plantid_')) for p in _MODELS_DIR.glob('plantid_*.json')]
    configs = [c for c in configs if c and model_path(c['model_version'])]
    return max(configs, key=lambda c: c.get('created', ''))['model_version'] if configs else None


def public_config(model_version: str) -> dict:
    """What a client needs to run the model — no eval internals."""
    c = load_config(model_version)
    return {k: c[k] for k in ('model_version', 'input_size', 'embed_dim', 'preprocess')}
