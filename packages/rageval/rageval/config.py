"""Per-app eval config (``rageval.yaml``). Relative paths resolve against the
config file's directory, so the same config works from any working directory."""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CRITERIA = ['faithful', 'correct', 'complete', 'relevant', 'appropriate_refusal']


@dataclass
class Config:
    root: Path
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> Config:
        p = Path(path).resolve()
        raw = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
        cfg = cls(root=p.parent, raw=raw)
        if raw.get('dotenv'):
            load_env_file(cfg.path(raw['dotenv']))
        for extra in raw.get('pythonpath', []):
            sp = str(cfg.path(extra))
            if sp not in sys.path:
                sys.path.insert(0, sp)
        return cfg

    def path(self, rel: str | Path) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p).resolve()

    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.raw
        for part in dotted.split('.'):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    # Convenience accessors
    @property
    def name(self) -> str:
        return self.raw.get('name', self.root.name)

    @property
    def golden_path(self) -> Path:
        return self.path(self.raw.get('golden', 'golden.jsonl'))

    @property
    def labels_path(self) -> Path:
        return self.path(self.raw.get('labels', 'labels.jsonl'))

    @property
    def runs_dir(self) -> Path:
        return self.path(self.raw.get('runs_dir', 'runs'))

    @property
    def baselines_dir(self) -> Path:
        return self.path(self.raw.get('baselines_dir', 'baselines'))

    @property
    def cache_dir(self) -> Path:
        return self.path(self.get('openrouter.cache_dir', '.rageval_cache'))

    @property
    def calibration_path(self) -> Path:
        return self.path(self.raw.get('calibration', 'calibration.json'))

    @property
    def criteria(self) -> list[str]:
        return self.get('judges.criteria', DEFAULT_CRITERIA)

    @property
    def panel(self) -> list[str]:
        return self.get('judges.panel', [])


def load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE loader (no python-dotenv dependency). Existing
    environment variables win, matching python-dotenv's default."""
    import os
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.removeprefix('export ').partition('=')
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        else:
            val = val.split(' #', 1)[0].strip()
        os.environ.setdefault(key.strip(), val)


def load_target(spec: str) -> Any:
    """'package.module:attr' -> the attribute."""
    mod, _, attr = spec.partition(':')
    if not attr:
        raise ValueError(f'target must look like "module:attr", got {spec!r}')
    return getattr(importlib.import_module(mod), attr)


def build_adapter(cfg: Config, name: str | None = None):
    adapters = cfg.raw.get('adapters') or {}
    name = name or cfg.raw.get('default_adapter') or next(iter(adapters), None)
    if name not in adapters:
        raise KeyError(f'adapter {name!r} not in config (have: {list(adapters)})')
    spec = adapters[name]
    obj = load_target(spec['target'])(**(spec.get('params') or {}))
    obj.name = name
    return obj


def load_scorers(cfg: Config) -> list:
    return [load_target(s) for s in cfg.raw.get('scorers', [])]


def make_client(cfg: Config):
    from rageval.llm.openrouter import OpenRouterClient
    o = cfg.raw.get('openrouter') or {}
    return OpenRouterClient(
        rpm=o.get('rpm', 20),
        daily_limit=o.get('daily_limit'),
        budget_path=cfg.cache_dir / 'budget.json',
        free_only=o.get('free_only', False),
        timeout=o.get('timeout', 120),
    )
