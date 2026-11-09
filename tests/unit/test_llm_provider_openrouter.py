"""
Unit tests for the OpenRouter provider in apps/ml_service/app/llm_provider.py.
"""
from unittest.mock import MagicMock, patch

import pytest

from apps.ml_service.app import llm_provider


def test_openrouter_default_model_is_nemotron():
    assert llm_provider._DEFAULTS['openrouter'] == 'nvidia/nemotron-3.5-lightning:free'


def test_openrouter_default_base_url():
    assert llm_provider.OPENROUTER_BASE_URL == 'https://openrouter.ai/api/v1'


def test_complete_dispatches_to_openrouter(monkeypatch):
    monkeypatch.setattr(llm_provider, 'PROVIDER', 'openrouter')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='hello'))
    ]
    with patch('openai.OpenAI', return_value=fake_client):
        reply = llm_provider.complete('system', 'user')

    assert reply == 'hello'
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs['model'] == 'nvidia/nemotron-3.5-lightning:free'


def test_openrouter_missing_key_raises_runtime_error(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    with pytest.raises(RuntimeError):
        llm_provider._openrouter('system', 'user')


def test_unknown_provider_raises_value_error(monkeypatch):
    monkeypatch.setattr(llm_provider, 'PROVIDER', 'not-a-real-provider')
    with pytest.raises(ValueError):
        llm_provider.complete('system', 'user')


def test_split_model_list():
    assert llm_provider.split_model_list('a, b ,c') == ('a', ['b', 'c'])
    assert llm_provider.split_model_list('solo') == ('solo', [])


def test_complete_sends_openrouter_fallbacks(monkeypatch):
    monkeypatch.setattr(llm_provider, 'PROVIDER', 'openrouter')
    monkeypatch.setattr(llm_provider, '_MODEL', 'a/one:free,b/two:free')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='hello'))
    ]
    with patch('openai.OpenAI', return_value=fake_client):
        llm_provider.complete('system', 'user')

    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs['model'] == 'a/one:free'
    assert kwargs['extra_body'] == {'models': ['a/one:free', 'b/two:free']}
