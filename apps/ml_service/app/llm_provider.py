"""
Model-agnostic LLM provider for the garden assistant chat.

Configure via .env:
    LLM_PROVIDER=anthropic   # anthropic | openai | ollama | huggingface
    LLM_MODEL=claude-haiku-4-5-20251001   # optional — provider default used if unset

Provider-specific keys:
    ANTHROPIC_API_KEY=sk-ant-...
    OPENAI_API_KEY=sk-...
    OLLAMA_BASE_URL=http://localhost:11434   # optional, this is the default
    HF_TOKEN=hf_...                         # optional for public HF models
"""

import os

PROVIDER   = os.environ.get('LLM_PROVIDER', 'anthropic').lower()
_MODEL     = os.environ.get('LLM_MODEL') or None   # None → provider default below
CHAT_MODEL = os.environ.get('CHAT_MODEL', 'claude-sonnet-4-6')

_DEFAULTS = {
    'anthropic':   'claude-haiku-4-5-20251001',
    'openai':      'gpt-4o-mini',
    'ollama':      'llama3.1',
    'huggingface': 'mistralai/Mistral-7B-Instruct-v0.2',
}


def complete(system: str, user: str) -> str:
    """
    Send a system + user message to the configured LLM and return the reply.

    Raises
    ------
    RuntimeError  if a required API key is missing
    ValueError    if LLM_PROVIDER is not recognised
    """
    dispatch = {
        'anthropic':   _anthropic,
        'openai':      _openai,
        'ollama':      _ollama,
        'huggingface': _huggingface,
    }
    fn = dispatch.get(PROVIDER)
    if fn is None:
        raise ValueError(
            f'Unknown LLM_PROVIDER: {PROVIDER!r}. '
            f'Supported values: {list(dispatch)}'
        )
    return fn(system, user)


def _model(provider: str) -> str:
    return _MODEL or _DEFAULTS[provider]


def _anthropic(system: str, user: str) -> str:
    import anthropic
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        raise RuntimeError(
            'The garden assistant is not configured. '
            'Add ANTHROPIC_API_KEY to your .env file.'
        )
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=_model('anthropic'),
        max_tokens=512,
        system=system,
        messages=[{'role': 'user', 'content': user}],
    )
    return resp.content[0].text


def _openai(system: str, user: str) -> str:
    from openai import OpenAI   # pip install openai
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        raise RuntimeError(
            'The garden assistant is not configured. '
            'Add OPENAI_API_KEY to your .env file.'
        )
    resp = OpenAI(api_key=key).chat.completions.create(
        model=_model('openai'),
        max_tokens=512,
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
        ],
    )
    return resp.choices[0].message.content


def _ollama(system: str, user: str) -> str:
    import requests   # already a project dependency
    base = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    resp = requests.post(
        f'{base}/api/chat',
        json={
            'model':   _model('ollama'),
            'stream':  False,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': user},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()['message']['content']


def _huggingface(system: str, user: str) -> str:
    from huggingface_hub import InferenceClient   # pip install huggingface-hub
    token = os.environ.get('HF_TOKEN') or None
    client = InferenceClient(model=_model('huggingface'), token=token)
    resp = client.chat_completion(
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
        ],
        max_tokens=512,
    )
    return resp.choices[0].message.content
