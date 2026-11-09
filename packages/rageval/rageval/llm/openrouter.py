"""
OpenRouter client shared by the judges, the synthetic-question generator and the
``rageval or`` CLI helpers.

Python port of the behaviour in kitchen_design's ``src/lib/llm/openai-compatible.ts``
plus what an eval run needs on the free tier:

* ``model`` may be a comma-separated list: the first is the model, the rest go
  in OpenRouter's ``models`` field and are tried when it is rate-limited or down.
  ``models`` carries the whole ordered list, primary first — sending only the
  fallbacks (as kitchen_design does) silently disables fallback.
* 429/502/503/504 are retried, honouring ``Retry-After`` (capped).
* ``usage: {include: true}`` is always sent, so every call reports tokens and
  cost, and the model/provider that actually served it is recorded — a
  fallback can switch models silently, and that must show up in the run.
* A client-side pacer keeps under the per-minute limit, and a file-backed daily
  counter stops the run cleanly (``BudgetExhausted``) before the free-tier daily
  cap does it for us. Callers cache results, so the next invocation resumes.
* ``free_only`` refuses any model id without a ``:free`` suffix.

Uses ``requests`` rather than the OpenAI SDK: fewer dependencies and trivial to
mock in tests. The API key is never logged.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1'
RETRY_STATUS = {429, 502, 503, 504}
MAX_RETRY_WAIT_S = 60
FREE_TIER_RPM = 20


class OpenRouterError(RuntimeError):
    """The request failed (transport, non-2xx, error body, or empty content)."""


class BudgetExhausted(RuntimeError):
    """The daily request budget is spent, or OpenRouter says the free-tier
    daily cap is. Not retried: everything done so far is cached, so re-running
    the same command later resumes."""


class NotFreeModel(ValueError):
    """free_only is on and a paid model id was requested."""


@dataclass
class Completion:
    text: str
    model: str                       # the model that actually answered
    provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: float = 0.0
    raw: dict = field(default_factory=dict, repr=False)


def split_models(spec: str) -> tuple[str, list[str]]:
    """"a, b ,c" -> ("a", ["b", "c"])."""
    models = [m.strip() for m in spec.split(',') if m.strip()]
    if not models:
        raise ValueError('empty model spec')
    return models[0], models[1:]


def is_free(model_id: str) -> bool:
    return model_id.endswith(':free')


def parse_json_reply(text: str) -> Any:
    """Parse a model's JSON reply: strips ``` fences, and failing that takes the
    outermost {...} block (small models like to wrap JSON in prose)."""
    s = text.strip()
    m = re.match(r'^```(?:json)?\s*\n?([\s\S]*?)\n?```\s*$', s)
    if m:
        s = m.group(1)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find('{'), s.rfind('}')
        if start != -1 and end > start:
            return json.loads(s[start:end + 1])
        raise


class RatePacer:
    """Requests-per-minute limiter over a trailing 60 s window (same idea as
    scripts/build_rag.py's RatePacer, minus the token budget)."""

    def __init__(self, rpm: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.rpm = rpm
        self._clock = clock
        self._sleep = sleep
        self._window: deque[float] = deque()

    def wait(self) -> None:
        if self.rpm <= 0:
            return
        while True:
            now = self._clock()
            while self._window and now - self._window[0] >= 60:
                self._window.popleft()
            if len(self._window) < self.rpm:
                break
            self._sleep(max(60 - (now - self._window[0]), 0))
        self._window.append(self._clock())


class DailyBudget:
    """Persistent per-day request counter. ``limit=None`` means unlimited (the
    count is still kept, for reporting)."""

    def __init__(self, path: str | Path | None, limit: int | None,
                 today: Callable[[], date] = date.today):
        self.path = Path(path) if path else None
        self.limit = limit
        self._today = today
        self._mem: dict[str, int] = {}

    def _load(self) -> dict[str, int]:
        if self.path and self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (OSError, json.JSONDecodeError):
                return {}
        return dict(self._mem)

    def _save(self, data: dict[str, int]) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data))
        else:
            self._mem = data

    def used_today(self) -> int:
        return self._load().get(self._today().isoformat(), 0)

    def remaining(self) -> int | None:
        return None if self.limit is None else max(self.limit - self.used_today(), 0)

    def consume(self) -> None:
        data = self._load()
        key = self._today().isoformat()
        if self.limit is not None and data.get(key, 0) >= self.limit:
            raise BudgetExhausted(
                f'daily request budget of {self.limit} used up; re-run tomorrow to resume')
        data = {key: data.get(key, 0) + 1}     # keep only today
        self._save(data)


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        rpm: int = FREE_TIER_RPM,
        daily_limit: int | None = None,
        budget_path: str | Path | None = None,
        free_only: bool = False,
        timeout: float = 120,
        max_retries: int = 3,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get('OPENROUTER_API_KEY', '')
        self.base_url = (base_url or os.environ.get('OPENROUTER_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')
        self.free_only = free_only
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self._sleep = sleep
        self._clock = clock
        self.pacer = RatePacer(rpm, clock=clock, sleep=sleep)
        self.budget = DailyBudget(budget_path, daily_limit)

    # ── HTTP ────────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise OpenRouterError('OPENROUTER_API_KEY is not set (add it to .env)')
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-Title': 'rageval',
        }

    def _get(self, path: str) -> dict:
        try:
            r = self.session.get(f'{self.base_url}{path}', headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise OpenRouterError(f'GET {path} failed: {exc}') from exc
        if not r.ok:
            raise OpenRouterError(f'GET {path} -> {r.status_code}: {r.text[:300]}')
        return r.json()

    @staticmethod
    def _is_daily_cap(resp: requests.Response) -> bool:
        body = (resp.text or '').lower()
        return 'per-day' in body or 'per day' in body

    def _retry_wait(self, resp: requests.Response, attempt: int) -> float:
        try:
            return min(float(resp.headers.get('retry-after')), MAX_RETRY_WAIT_S)
        except (TypeError, ValueError):
            return min(2 ** (attempt + 1), MAX_RETRY_WAIT_S)

    # ── Chat ────────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict | None = None,
    ) -> Completion:
        primary, fallbacks = split_models(model)
        if self.free_only:
            paid = [m for m in [primary, *fallbacks] if not is_free(m)]
            if paid:
                raise NotFreeModel(f'free_only is on but these are not :free models: {paid}')

        body: dict[str, Any] = {'model': primary, 'messages': messages, 'usage': {'include': True}}
        if fallbacks:
            # The full ordered list, primary included: with only the fallbacks in
            # `models`, OpenRouter never falls back (verified live 2026-10-18).
            body['models'] = [primary, *fallbacks]
        if json_mode:
            body['response_format'] = {'type': 'json_object'}
        if temperature is not None:
            body['temperature'] = temperature
        if max_tokens is not None:
            body['max_tokens'] = max_tokens
        if extra:
            body.update(extra)

        headers = self._headers()
        for attempt in range(self.max_retries + 1):
            self.budget.consume()
            self.pacer.wait()
            t0 = self._clock()
            try:
                resp = self.session.post(f'{self.base_url}/chat/completions',
                                         headers=headers, json=body, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self._sleep(min(2 ** (attempt + 1), MAX_RETRY_WAIT_S))
                    continue
                raise OpenRouterError(f'request failed: {exc}') from exc
            latency_ms = (self._clock() - t0) * 1000

            if resp.status_code == 429 and self._is_daily_cap(resp):
                raise BudgetExhausted(f'OpenRouter daily cap reached: {resp.text[:200]}')
            if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                self._sleep(self._retry_wait(resp, attempt))
                continue
            if not resp.ok:
                raise OpenRouterError(f'{resp.status_code}: {resp.text[:500]}')
            return self._parse(resp, primary, latency_ms)
        raise OpenRouterError('retries exhausted')   # pragma: no cover - loop always returns/raises

    @staticmethod
    def _parse(resp: requests.Response, requested: str, latency_ms: float) -> Completion:
        try:
            data = resp.json()
        except ValueError as exc:
            raise OpenRouterError(f'response was not JSON: {resp.text[:200]}') from exc
        if data.get('error'):
            raise OpenRouterError(f'error body: {json.dumps(data["error"])[:300]}')
        choices = data.get('choices') or []
        text = (choices[0].get('message') or {}).get('content') if choices else None
        if not text:
            raise OpenRouterError('response had no choices or empty content')
        usage = data.get('usage') or {}
        return Completion(
            text=text,
            model=data.get('model') or requested,
            provider=data.get('provider'),
            prompt_tokens=usage.get('prompt_tokens'),
            completion_tokens=usage.get('completion_tokens'),
            cost_usd=usage.get('cost'),
            latency_ms=latency_ms,
            raw=data,
        )

    def complete(self, system: str, user: str, model: str, **kw) -> Completion:
        return self.chat([{'role': 'system', 'content': system},
                          {'role': 'user', 'content': user}], model, **kw)

    def complete_json(self, system: str, user: str, model: str, **kw) -> tuple[Any, Completion]:
        """JSON completion. Raises ``OpenRouterError`` if the reply isn't JSON."""
        c = self.complete(system, user, model, json_mode=True, **kw)
        try:
            return parse_json_reply(c.text), c
        except json.JSONDecodeError as exc:
            raise OpenRouterError(f'{c.model} returned non-JSON: {c.text[:200]}') from exc

    # ── Account / catalogue ────────────────────────────────────────────────

    def key_info(self) -> dict:
        """GET /key: usage, limit, is_free_tier, rate_limit for this key."""
        return self._get('/key').get('data', {})

    def models(self, cache_path: str | Path | None = None, max_age_s: int = 86400) -> list[dict]:
        """The model catalogue (pricing, context length, supported parameters),
        cached on disk for a day: it is large and changes slowly."""
        if cache_path:
            p = Path(cache_path)
            if p.exists() and time.time() - p.stat().st_mtime < max_age_s:
                return json.loads(p.read_text())
        data = self._get('/models').get('data', [])
        if cache_path:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data))
        return data


def price_of(models: list[dict], model_id: str) -> tuple[float, float] | None:
    """(USD per prompt token, USD per completion token) from the catalogue."""
    for m in models:
        if m.get('id') == model_id:
            p = m.get('pricing') or {}
            try:
                return float(p.get('prompt', 0)), float(p.get('completion', 0))
            except (TypeError, ValueError):
                return None
    return None
