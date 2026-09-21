"""
Unit tests for the shared OpenAI-compatible agentic loop
(apps/ml_service/app/chat_tools.py: _run_openai_compatible_loop), used by
both the Hetzner and OpenRouter providers.

The OpenAI SDK client is faked rather than mocked with MagicMock so that
request kwargs and response shapes stay honest to what chat_tools.py
actually reads off them (msg.tool_calls, msg.model_extra, etc).
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai
import pytest

from apps.ml_service.app import chat_tools


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _response(content, tool_calls=None, model_extra=None):
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
        model_extra=model_extra or {},
    )
    choice = SimpleNamespace(
        message=message,
        finish_reason='tool_calls' if tool_calls else 'stop',
    )
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    return SimpleNamespace(choices=[choice], usage=usage)


class _FakeClient:
    """Records every chat.completions.create() call and returns scripted responses."""

    def __init__(self, calls, responses, *, api_key=None, base_url=None):
        self._calls = calls
        self._responses = responses
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # `messages` is the same list object across every round (the loop
        # mutates it in place), so snapshot a shallow copy per call or every
        # recorded call would show the final round's full history.
        snapshot = dict(kwargs)
        if 'messages' in snapshot:
            snapshot['messages'] = list(snapshot['messages'])
        self._calls.append(snapshot)
        return self._responses.pop(0)


@pytest.fixture
def fake_openai(monkeypatch):
    calls, responses = [], []
    monkeypatch.setattr(
        openai, 'OpenAI',
        lambda **kw: _FakeClient(calls, responses, **kw),
    )
    return calls, responses


def test_openrouter_sends_reasoning_and_higher_max_tokens(fake_openai, monkeypatch):
    calls, responses = fake_openai
    responses.append(_response('All done'))
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock())
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    reply = chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='openrouter', base_url='https://openrouter.ai/api/v1',
        key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        max_tokens=4096, reasoning=True, max_rounds=5,
    )

    assert reply == 'All done'
    assert len(calls) == 1
    assert calls[0]['max_tokens'] == 4096
    assert calls[0]['extra_body'] == {'reasoning': {'enabled': True}}


def test_hetzner_does_not_send_reasoning(fake_openai, monkeypatch):
    calls, responses = fake_openai
    responses.append(_response('Done'))
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock())
    monkeypatch.setenv('HETZNER_API_KEY', 'test-key')

    chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='hetzner', base_url='https://inference.hetzner.com/api/v1',
        key_env='HETZNER_API_KEY', model='Qwen3.8-27B',
        max_tokens=1024, reasoning=False, max_rounds=5,
    )

    assert calls[0]['max_tokens'] == 1024
    assert 'extra_body' not in calls[0]


def test_tool_call_id_roundtrips_to_tool_result(fake_openai, monkeypatch):
    calls, responses = fake_openai
    tc = _tool_call('call_1', 'get_garden_plan', {})
    responses.append(_response(None, tool_calls=[tc]))
    responses.append(_response('Here is your plan'))
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock(return_value={'ok': True}))
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    reply = chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'what is my plan'}], None, None,
        provider='openrouter', base_url='https://openrouter.ai/api/v1',
        key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        max_tokens=4096, reasoning=True, max_rounds=5,
    )

    assert reply == 'Here is your plan'
    second_call_messages = calls[1]['messages']
    tool_msgs = [m for m in second_call_messages if m['role'] == 'tool']
    assert tool_msgs and tool_msgs[-1]['tool_call_id'] == 'call_1'


def test_reasoning_details_roundtrip_unmodified(fake_openai, monkeypatch):
    calls, responses = fake_openai
    tc = _tool_call('call_1', 'get_garden_plan', {})
    reasoning_details = [{'type': 'reasoning.text', 'text': 'thinking...', 'id': 'r1'}]
    responses.append(_response('', tool_calls=[tc],
                                model_extra={'reasoning_details': reasoning_details}))
    responses.append(_response('Final answer'))
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock(return_value={'ok': True}))
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='openrouter', base_url='https://openrouter.ai/api/v1',
        key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        max_tokens=4096, reasoning=True, max_rounds=5,
    )

    second_call_messages = calls[1]['messages']
    assistant_msgs = [m for m in second_call_messages if m['role'] == 'assistant']
    # Passed through unmodified -- same object, not a re-serialized copy.
    assert assistant_msgs[-1]['reasoning_details'] is reasoning_details


def test_hetzner_never_carries_reasoning_details(fake_openai, monkeypatch):
    """reasoning=False must never attach reasoning_details, even if the SDK
    parsed an (unexpected) extra field with that name onto the message."""
    calls, responses = fake_openai
    tc = _tool_call('call_1', 'get_garden_plan', {})
    responses.append(_response(None, tool_calls=[tc],
                                model_extra={'reasoning_details': ['unexpected']}))
    responses.append(_response('Done'))
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock(return_value={'ok': True}))
    monkeypatch.setenv('HETZNER_API_KEY', 'test-key')

    chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='hetzner', base_url='https://inference.hetzner.com/api/v1',
        key_env='HETZNER_API_KEY', model='Qwen3.8-27B',
        max_tokens=1024, reasoning=False, max_rounds=5,
    )

    second_call_messages = calls[1]['messages']
    assistant_msgs = [m for m in second_call_messages if m['role'] == 'assistant']
    assert 'reasoning_details' not in assistant_msgs[-1]


def _status_error(status_code, retry_after=None):
    headers = {'retry-after': str(retry_after)} if retry_after is not None else {}
    req = httpx.Request('POST', 'https://openrouter.ai/api/v1/chat/completions')
    resp = httpx.Response(status_code, request=req, headers=headers)
    return openai.APIStatusError('error', response=resp, body=None)


@pytest.mark.parametrize('status_code', [429, 502, 503, 504])
def test_retryable_status_is_retried_once(fake_openai, monkeypatch, status_code):
    calls, responses = fake_openai
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock())
    monkeypatch.setattr(chat_tools.time, 'sleep', MagicMock())
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    attempt = {'n': 0}
    real_create = _FakeClient._create

    def flaky_create(self, **kwargs):
        attempt['n'] += 1
        if attempt['n'] == 1:
            calls.append(kwargs)
            raise _status_error(status_code)
        return real_create(self, **kwargs)

    monkeypatch.setattr(_FakeClient, '_create', flaky_create)
    responses.append(_response('recovered'))

    reply = chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='openrouter', base_url='https://openrouter.ai/api/v1',
        key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        max_tokens=4096, reasoning=True, max_rounds=5,
    )

    assert reply == 'recovered'
    assert attempt['n'] == 2


def test_retry_honours_retry_after_header(fake_openai, monkeypatch):
    calls, responses = fake_openai
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock())
    sleep_mock = MagicMock()
    monkeypatch.setattr(chat_tools.time, 'sleep', sleep_mock)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    attempt = {'n': 0}
    real_create = _FakeClient._create

    def flaky_create(self, **kwargs):
        attempt['n'] += 1
        if attempt['n'] == 1:
            raise _status_error(429, retry_after=7)
        return real_create(self, **kwargs)

    monkeypatch.setattr(_FakeClient, '_create', flaky_create)
    responses.append(_response('recovered'))

    chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='openrouter', base_url='https://openrouter.ai/api/v1',
        key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        max_tokens=4096, reasoning=True, max_rounds=5,
    )

    sleep_mock.assert_called_once_with(7.0)


def test_missing_key_raises_runtime_error(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    with pytest.raises(RuntimeError):
        chat_tools._run_openai_compatible_loop(
            'system', [], None, None,
            provider='openrouter', base_url='https://openrouter.ai/api/v1',
            key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        )


def test_loop_exhaustion_returns_friendly_message(fake_openai, monkeypatch):
    calls, responses = fake_openai
    tc = _tool_call('call_1', 'get_garden_plan', {})
    # Every round keeps calling a tool, so the loop never returns early.
    for _ in range(3):
        responses.append(_response(None, tool_calls=[tc]))
    monkeypatch.setattr(chat_tools, 'execute_tool', MagicMock(return_value={'ok': True}))
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    reply = chat_tools._run_openai_compatible_loop(
        'system', [{'role': 'user', 'content': 'hi'}], None, None,
        provider='openrouter', base_url='https://openrouter.ai/api/v1',
        key_env='OPENROUTER_API_KEY', model='nvidia/nemotron-3.5-lightning:free',
        max_tokens=4096, reasoning=True, max_rounds=3,
    )

    assert reply == 'I ran into a loop. Please try rephrasing your question.'
