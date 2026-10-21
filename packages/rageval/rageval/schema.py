"""Data records and JSONL I/O. Everything on disk is JSONL of these dataclasses."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar('T')


def sha(obj: Any, n: int = 12) -> str:
    """Stable short hash of any JSON-serialisable value (or a str as-is)."""
    s = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:n]


@dataclass
class GoldenItem:
    id: str
    question: str
    reference_answer: str = ''
    must_include: list[str] = field(default_factory=list)
    # Stable ids of the chunks that answer the question (for the garden app,
    # md5(text) — the same key build_rag.py dedupes on, so re-indexing keeps them valid).
    relevant_sources: list[str] = field(default_factory=list)
    category: str = 'general'
    tags: list[str] = field(default_factory=list)
    answerable: bool = True
    meta: dict = field(default_factory=dict)       # app-specific expectations


@dataclass
class Context:
    text: str
    id: str | None = None
    source: str | None = None
    score: float | None = None


@dataclass
class Response:
    answer: str
    contexts: list[Context] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
    stage_latency_ms: dict[str, float] = field(default_factory=dict)
    error: str | None = None


@dataclass
class RunRecord:
    item_id: str
    question: str
    response: Response
    answer_hash: str = ''

    def __post_init__(self):
        if not self.answer_hash:
            self.answer_hash = answer_hash(self.response)


@dataclass
class Judgment:
    item_id: str
    answer_hash: str
    judge: str                    # model spec as configured (may include fallbacks)
    rubric_hash: str
    verdicts: dict[str, bool | None] = field(default_factory=dict)
    reasoning: str = ''
    served_model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class HumanLabel:
    item_id: str
    answer_hash: str
    verdicts: dict[str, bool | None]
    labeler: str = ''
    note: str = ''
    ts: str = ''
    # Snapshot of what was labelled, so labels outlive the (gitignored) run that
    # produced them and calibration can re-judge them under a new judge panel.
    record: dict = field(default_factory=dict)


def answer_hash(resp: Response) -> str:
    """Identity of an answer for judging: same answer + same contexts => same
    judgment, whichever run produced it."""
    return sha({'a': resp.answer, 'c': [c.text for c in resp.contexts]})


# ── (de)serialisation ────────────────────────────────────────────────────────

def to_dict(obj) -> dict:
    return asdict(obj)


def from_dict(cls: type[T], d: dict) -> T:
    names = {f.name for f in fields(cls)}
    kw = {k: v for k, v in d.items() if k in names}
    if cls is Response:
        kw['contexts'] = [from_dict(Context, c) for c in kw.get('contexts', [])]
    if cls is RunRecord:
        kw['response'] = from_dict(Response, kw['response'])
    return cls(**kw)


def read_jsonl(path: str | Path, cls: type[T] | None = None) -> list:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out.append(from_dict(cls, d) if cls else d)
    return out


def write_jsonl(path: str | Path, rows: Iterable) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r if isinstance(r, dict) else to_dict(r), ensure_ascii=False) + '\n')


def append_jsonl(path: str | Path, row) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row if isinstance(row, dict) else to_dict(row), ensure_ascii=False) + '\n')


def file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
