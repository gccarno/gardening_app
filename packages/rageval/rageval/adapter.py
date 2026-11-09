"""
The seam between rageval and the system under test.

An adapter turns a golden item into a ``Response``. ``describe()`` returns what
identifies the system under test (model, prompt hash, retriever params): it goes
into every run's manifest so a comparison knows what changed.

Optional: ``iter_chunks()`` yields ``{'id', 'text', 'source'}`` dicts from the
app's corpus, which ``rageval synth`` samples to generate golden candidates.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any, Protocol, runtime_checkable

import requests

from rageval.schema import Context, GoldenItem, Response


@runtime_checkable
class RAGAdapter(Protocol):
    name: str

    def describe(self) -> dict: ...

    def answer(self, item: GoldenItem) -> Response: ...


class CallableAdapter:
    """Wrap ``fn(question) -> str | Response``."""

    def __init__(self, fn: Callable[[str], Any], description: dict | None = None,
                 chunks: Callable[[], Iterable[dict]] | None = None):
        self.name = getattr(fn, '__name__', 'callable')
        self.fn = fn
        self._description = description or {}
        self._chunks = chunks

    def describe(self) -> dict:
        return dict(self._description)

    def answer(self, item: GoldenItem) -> Response:
        out = self.fn(item.question)
        return out if isinstance(out, Response) else Response(answer=str(out))

    def iter_chunks(self) -> Iterable[dict]:
        if self._chunks is None:
            raise NotImplementedError('this adapter has no corpus to sample')
        return self._chunks()


class HttpAdapter:
    """POST ``{question_field: question}`` to any endpoint.

    ``answer_field`` / ``contexts_field`` are dotted paths into the JSON reply;
    each context may be a string or an object with ``text_key``/``id_key``/
    ``source_key``. Extra request fields go in ``body``; headers in ``headers``
    (values starting with ``$`` are read from the environment).
    """

    def __init__(self, url: str, question_field: str = 'question', answer_field: str = 'answer',
                 contexts_field: str | None = None, text_key: str = 'text', id_key: str = 'id',
                 source_key: str = 'source', body: dict | None = None,
                 headers: dict | None = None, timeout: float = 120):
        self.name = 'http'
        self.url = url
        self.question_field = question_field
        self.answer_field = answer_field
        self.contexts_field = contexts_field
        self.keys = (text_key, id_key, source_key)
        self.body = body or {}
        self.headers = headers or {}
        self.timeout = timeout

    def describe(self) -> dict:
        return {'url': self.url, 'body': self.body}

    @staticmethod
    def _dig(data: Any, dotted: str) -> Any:
        for part in dotted.split('.'):
            data = data.get(part) if isinstance(data, dict) else None
        return data

    def answer(self, item: GoldenItem) -> Response:
        import os
        headers = {k: os.environ.get(v[1:], '') if str(v).startswith('$') else v
                   for k, v in self.headers.items()}
        t0 = time.perf_counter()
        r = requests.post(self.url, json={**self.body, self.question_field: item.question},
                          headers=headers, timeout=self.timeout)
        latency = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        data = r.json()
        text_key, id_key, source_key = self.keys
        contexts = []
        for c in (self._dig(data, self.contexts_field) or []) if self.contexts_field else []:
            if isinstance(c, str):
                contexts.append(Context(text=c))
            else:
                contexts.append(Context(text=str(c.get(text_key, '')), id=c.get(id_key),
                                        source=c.get(source_key)))
        return Response(answer=str(self._dig(data, self.answer_field) or ''),
                        contexts=contexts, latency_ms=latency)
