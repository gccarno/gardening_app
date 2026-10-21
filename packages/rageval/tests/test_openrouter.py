"""OpenRouter client with a fake HTTP session — no network."""
from datetime import date

import pytest
from rageval.llm.openrouter import (
    BudgetExhausted,
    DailyBudget,
    NotFreeModel,
    OpenRouterClient,
    OpenRouterError,
    RatePacer,
    parse_json_reply,
    price_of,
    split_models,
)


class FakeResp:
    def __init__(self, status=200, body=None, headers=None, text=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.text = text if text is not None else ('' if body is None else str(body))

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._body is None:
            raise ValueError('no json')
        return self._body


def ok_body(content='hi', model='m:free'):
    return {'model': model, 'provider': 'P',
            'choices': [{'message': {'content': content}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'cost': 0}}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []

    def post(self, url, headers, json, timeout):
        self.posts.append(json)
        return self.responses.pop(0)

    def get(self, url, headers, timeout):
        return self.responses.pop(0)


def client(responses, **kw):
    sleeps = []
    c = OpenRouterClient(api_key='k', session=FakeSession(responses), rpm=0,
                         sleep=sleeps.append, **kw)
    return c, sleeps


def test_split_models():
    assert split_models('a, b ,c') == ('a', ['b', 'c'])
    with pytest.raises(ValueError):
        split_models(' , ')


def test_fallbacks_sent_as_models_and_usage_included():
    c, _ = client([FakeResp(body=ok_body(model='b:free'))])
    out = c.complete('sys', 'u', 'a:free,b:free')
    sent = c.session.posts[0]
    assert sent['model'] == 'a:free' and sent['models'] == ['a:free', 'b:free']
    assert sent['usage'] == {'include': True}
    assert out.model == 'b:free'          # the fallback that actually answered
    assert (out.prompt_tokens, out.completion_tokens, out.cost_usd) == (10, 3, 0)


def test_retry_after_honoured_then_succeeds():
    c, sleeps = client([FakeResp(429, text='slow down', headers={'retry-after': '7'}),
                        FakeResp(body=ok_body())])
    assert c.complete('s', 'u', 'm:free').text == 'hi'
    assert sleeps == [7.0]


def test_retry_after_capped():
    c, sleeps = client([FakeResp(503, text='x', headers={'retry-after': '9999'}),
                        FakeResp(body=ok_body())])
    c.complete('s', 'u', 'm:free')
    assert sleeps == [60]


def test_daily_cap_429_is_not_retried():
    c, sleeps = client([FakeResp(429, text='Rate limit exceeded: free-models-per-day')])
    with pytest.raises(BudgetExhausted):
        c.complete('s', 'u', 'm:free')
    assert sleeps == []


def test_gives_up_after_max_retries():
    c, _ = client([FakeResp(502, text='bad')] * 3, max_retries=2)
    with pytest.raises(OpenRouterError):
        c.complete('s', 'u', 'm:free')


def test_error_body_and_empty_content_raise():
    c, _ = client([FakeResp(body={'error': {'message': 'nope'}})])
    with pytest.raises(OpenRouterError):
        c.complete('s', 'u', 'm:free')
    c, _ = client([FakeResp(body=ok_body(content=''))])
    with pytest.raises(OpenRouterError):
        c.complete('s', 'u', 'm:free')


def test_free_only_refuses_paid_models():
    c, _ = client([], free_only=True)
    with pytest.raises(NotFreeModel):
        c.complete('s', 'u', 'a:free,anthropic/claude-sonnet')


def test_complete_json_strips_fences_and_prose():
    c, _ = client([FakeResp(body=ok_body(content='```json\n{"a": 1}\n```'))])
    assert c.complete_json('s', 'u', 'm:free')[0] == {'a': 1}
    assert parse_json_reply('Sure! {"b": 2} hope that helps') == {'b': 2}


def test_daily_budget_persists_and_stops(tmp_path):
    p = tmp_path / 'budget.json'
    b = DailyBudget(p, limit=2, today=lambda: date(2026, 10, 18))
    b.consume()
    b.consume()
    with pytest.raises(BudgetExhausted):
        DailyBudget(p, limit=2, today=lambda: date(2026, 10, 18)).consume()
    # a new day resets it
    DailyBudget(p, limit=2, today=lambda: date(2026, 10, 19)).consume()


def test_budget_counts_retries():
    c, _ = client([FakeResp(502, text='x'), FakeResp(body=ok_body())], daily_limit=1)
    with pytest.raises(BudgetExhausted):
        c.complete('s', 'u', 'm:free')


def test_rate_pacer_sleeps_when_window_full():
    t = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += s

    pacer = RatePacer(2, clock=lambda: t[0], sleep=sleep)
    pacer.wait()
    pacer.wait()
    pacer.wait()
    assert slept == [60]


def test_price_of():
    cat = [{'id': 'x', 'pricing': {'prompt': '0.000001', 'completion': '0.000002'}}]
    assert price_of(cat, 'x') == (1e-6, 2e-6)
    assert price_of(cat, 'y') is None
