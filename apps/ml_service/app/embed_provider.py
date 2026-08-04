"""
Model-agnostic embedding provider for the growing-guides RAG.

Configure via .env:
    EMBED_PROVIDER=gemini    # gemini | openai | voyage
    EMBED_MODEL=gemini-embedding-001   # optional — provider default used if unset
    EMBED_DIMS=768                     # optional — provider default used if unset

Provider-specific keys:
    GEMINI_API_KEY=...
    OPENAI_API_KEY=sk-...
    VOYAGE_API_KEY=pa-...

Embeddings are always an HTTP call, never a local model. Loading a
sentence-transformers / ONNX model into the request process is what walked the
free Render instance into its 536 MB limit; see docs/rag.md.

EMBED_DIMS must match the `vector(N)` column width in the guide_chunk table.
Changing it means a new migration and a full re-index.
"""

import os

PROVIDER = os.environ.get('EMBED_PROVIDER', 'gemini').lower()
_MODEL   = os.environ.get('EMBED_MODEL') or None    # None → provider default below

_DEFAULTS = {
    'gemini': 'gemini-embedding-001',
    'openai': 'text-embedding-3-large',
    'voyage': 'voyage-3-large',
}

# Gemini and OpenAI support Matryoshka truncation, so 768 is a real choice
# rather than a lossy crop. Voyage emits 1024 and ignores the setting.
DIMS = int(os.environ.get('EMBED_DIMS', '768'))

# Query-time embeddings are a few dozen tokens; the index build is ~2.1M tokens
# across 5,544 chunks. Batches keep the backfill to a few hundred requests.
BATCH_SIZE = 100


def embed(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
    """
    Embed a list of texts. Returns one vector of length DIMS per input.

    `is_query` selects the asymmetric task type where the provider has one —
    retrieval models embed questions and documents differently, and using the
    document mode for a query measurably degrades recall.

    Raises
    ------
    RuntimeError  if the required API key is missing
    ValueError    if EMBED_PROVIDER is not recognised
    """
    if not texts:
        return []

    dispatch = {
        'gemini': _gemini,
        'openai': _openai,
        'voyage': _voyage,
    }
    fn = dispatch.get(PROVIDER)
    if fn is None:
        raise ValueError(
            f'Unknown EMBED_PROVIDER: {PROVIDER!r}. '
            f'Supported values: {list(dispatch)}'
        )

    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        vectors.extend(fn(texts[start:start + BATCH_SIZE], is_query))
    return vectors


def embed_one(text: str, *, is_query: bool = False) -> list[float]:
    """Embed a single text. Convenience wrapper used by the search path."""
    return embed([text], is_query=is_query)[0]


def _model(provider: str) -> str:
    return _MODEL or _DEFAULTS[provider]


def _key(name: str) -> str:
    value = os.environ.get(name, '')
    if not value:
        raise RuntimeError(
            f'Growing-guide search is not configured. '
            f'Add {name} to your .env file (see DEPLOYMENT.md).'
        )
    return value


def _gemini(texts: list[str], is_query: bool) -> list[list[float]]:
    from google import genai                      # pip install google-genai
    from google.genai import types

    client = genai.Client(api_key=_key('GEMINI_API_KEY'))
    resp = client.models.embed_content(
        model=_model('gemini'),
        contents=texts,
        config=types.EmbedContentConfig(
            task_type='RETRIEVAL_QUERY' if is_query else 'RETRIEVAL_DOCUMENT',
            output_dimensionality=DIMS,
        ),
    )
    return [list(e.values) for e in resp.embeddings]


def _openai(texts: list[str], is_query: bool) -> list[list[float]]:
    from openai import OpenAI                     # pip install openai

    # OpenAI's retrieval embeddings are symmetric — no query/document split.
    resp = OpenAI(api_key=_key('OPENAI_API_KEY')).embeddings.create(
        model=_model('openai'),
        input=texts,
        dimensions=DIMS,
    )
    return [d.embedding for d in resp.data]


def _voyage(texts: list[str], is_query: bool) -> list[list[float]]:
    import voyageai                               # pip install voyageai

    client = voyageai.Client(api_key=_key('VOYAGE_API_KEY'))
    resp = client.embed(
        texts,
        model=_model('voyage'),
        input_type='query' if is_query else 'document',
    )
    return resp.embeddings
