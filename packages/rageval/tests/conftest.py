import re
import shutil
import sys
from pathlib import Path

import pytest
from rageval.llm.openrouter import Completion
from rageval.metrics import REFUSAL_RE, fact_covered

TOY = Path(__file__).resolve().parents[1] / 'examples' / 'toy_rag'
_WORD = re.compile(r'[a-z0-9]+')


def _section(prompt: str, name: str) -> str:
    m = re.search(rf'(?:^|\n){name}:\n(.*?)(?:\n\n[A-Z][A-Z -]+:\n|\Z)', prompt, re.DOTALL)
    return m.group(1) if m else ''


def _words(s):
    return {w for w in _WORD.findall(s.lower()) if len(w) > 3}


class FakeJudgeClient:
    """Stands in for OpenRouterClient. Judges with simple lexical rules, so
    verdicts are deterministic; 'noisy' judges flip `correct` on some items to
    create realistic disagreement."""

    def __init__(self, noisy=('judge-c:free',)):
        self.calls = 0
        self.noisy = set(noisy)

    def complete_json(self, system, user, model, **kw):
        self.calls += 1
        answer = _section(user, 'ANSWER')
        ref = _section(user, 'REFERENCE ANSWER')
        ctx = _section(user, 'RETRIEVED CONTEXT')
        facts = [f[2:] for f in _section(user, 'MUST-INCLUDE FACTS').splitlines() if f.startswith('- ')]
        aw = _words(answer)
        v = {
            'faithful': bool(aw) and len(aw & _words(ctx)) / len(aw) >= 0.8,
            'correct': bool(ref) and len(_words(ref) & aw) / max(len(_words(ref)), 1) >= 0.5,
            'complete': all(fact_covered(f, answer) for f in facts),
            'relevant': True,
            'appropriate_refusal': bool(REFUSAL_RE.search(answer)),
        }
        if model in self.noisy and len(answer) % 3 == 0:
            v['correct'] = not v['correct']
        data = {'reasoning': 'fake', 'verdicts': {k: 'yes' if x else 'no' for k, x in v.items()}}
        return data, Completion(text='{}', model=model, prompt_tokens=100, completion_tokens=20,
                                cost_usd=0.0, latency_ms=5.0)


@pytest.fixture
def toy_cfg(tmp_path):
    """A private copy of the toy example so runs/caches land in tmp."""
    dest = tmp_path / 'toy'
    shutil.copytree(TOY, dest, ignore=shutil.ignore_patterns('runs', 'baselines', '.rageval_cache',
                                                             'labels.jsonl', '__pycache__'))
    from rageval.config import Config
    cfg = Config.load(dest / 'rageval.yaml')
    yield cfg
    sys.modules.pop('toy', None)


@pytest.fixture
def fake_client():
    return FakeJudgeClient()
