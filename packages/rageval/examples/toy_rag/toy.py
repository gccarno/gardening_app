"""
A deliberately tiny RAG system: keyword-overlap retrieval over a folder of
markdown paragraphs, and a "generator" that returns the best passage's most
relevant sentence. No LLM, no network.

It exists to show rageval is not tied to the garden app (nothing here knows
about gardens), and to give the package an end-to-end test fixture.

``degrade=True`` makes it answer from the *worst* passage instead — a stand-in
for a bad prompt or model change, so tests can check the regression gate fires.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rageval.schema import Context, GoldenItem, Response

DOCS = Path(__file__).parent / 'docs'
_WORD = re.compile(r'[a-z0-9]+')


def _words(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if len(w) > 2}


def chunk_id(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


class ToyRAG:
    def __init__(self, docs: str | None = None, k: int = 2, degrade: bool = False):
        self.name = 'toy'
        self.k = k
        self.degrade = degrade
        self.chunks = []
        for f in sorted(Path(docs or DOCS).glob('*.md')):
            for para in f.read_text(encoding='utf-8').split('\n\n'):
                para = para.strip()
                if para and not para.startswith('#'):
                    self.chunks.append({'id': chunk_id(para), 'text': para, 'source': f.name})

    def describe(self) -> dict:
        return {'retriever': 'keyword-overlap', 'k': self.k, 'degrade': self.degrade}

    def iter_chunks(self):
        return iter(self.chunks)

    def answer(self, item: GoldenItem) -> Response:
        q = _words(item.question)
        scored = sorted(self.chunks, key=lambda c: len(q & _words(c['text'])), reverse=True)
        top = scored[: self.k]
        if not top or not q & _words(top[0]['text']):
            return Response(answer="I don't know - the documents don't cover that.",
                            contexts=[Context(text=c['text'], id=c['id'], source=c['source']) for c in top])
        src = scored[-1] if self.degrade else top[0]
        sentences = re.split(r'(?<=\.)\s+', src['text'])
        best = max(sentences, key=lambda s: len(q & _words(s)))
        return Response(
            answer=best,
            contexts=[Context(text=c['text'], id=c['id'], source=c['source'], score=float(len(q & _words(c['text']))))
                      for c in top],
            model='toy-extractive',
            prompt_tokens=len(item.question.split()) + sum(len(c['text'].split()) for c in top),
            completion_tokens=len(best.split()),
            cost_usd=0.0,
        )
