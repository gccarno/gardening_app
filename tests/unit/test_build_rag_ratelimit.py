"""Rate-limit backoff and resumability helpers in scripts/build_rag.py.

These target the pure pieces added to survive Gemini free-tier limits
(100 RPM, 30k TPM, 1K RPD): token-budget batching, a client-side pacer,
429 backoff, and content-hash resume. No network or DB calls.
"""
from types import SimpleNamespace

from scripts.build_rag import (
    _estimate_tokens,
    _batch_by_tokens,
    _text_hash,
    _filter_new,
    _is_rate_limit_error,
    _parse_retry_delay,
    RatePacer,
)


# ── _estimate_tokens ────────────────────────────────────────────────────────

def test_estimate_tokens_uses_four_chars_per_token():
    assert _estimate_tokens('a' * 400) == 100


def test_estimate_tokens_empty_string():
    assert _estimate_tokens('') == 0


# ── _batch_by_tokens ────────────────────────────────────────────────────────

def test_batch_by_tokens_splits_on_token_budget():
    # Each chunk ~250 tokens (1000 chars). Budget 600 tokens -> 2 per batch.
    chunks = ['x' * 1000 for _ in range(5)]
    metas = [{'i': i} for i in range(5)]

    batches = list(_batch_by_tokens(chunks, metas, max_tokens=600, max_items=100))

    assert [len(b[0]) for b in batches] == [2, 2, 1]


def test_batch_by_tokens_splits_on_item_count():
    chunks = ['short'] * 5
    metas = [{'i': i} for i in range(5)]

    batches = list(_batch_by_tokens(chunks, metas, max_tokens=1_000_000, max_items=2))

    assert [len(b[0]) for b in batches] == [2, 2, 1]


def test_batch_by_tokens_never_drops_a_chunk():
    chunks = [f'chunk-{i}' * (i + 1) for i in range(37)]
    metas = [{'i': i} for i in range(37)]

    batches = list(_batch_by_tokens(chunks, metas, max_tokens=50, max_items=7))

    seen = [c for batch_chunks, _ in batches for c in batch_chunks]
    assert seen == chunks


def test_batch_by_tokens_oversized_single_chunk_gets_its_own_batch():
    chunks = ['y' * 10_000, 'small']
    metas = [{'i': 0}, {'i': 1}]

    batches = list(_batch_by_tokens(chunks, metas, max_tokens=100, max_items=100))

    assert [len(b[0]) for b in batches] == [1, 1]
    assert batches[0][0] == ['y' * 10_000]


def test_batch_by_tokens_pairs_chunks_with_their_metadata():
    chunks = ['a' * 100, 'b' * 100]
    metas = [{'plant_name': 'Tomato'}, {'plant_name': 'Pepper'}]

    (batch_chunks, batch_meta), = _batch_by_tokens(chunks, metas, max_tokens=1_000_000, max_items=100)

    assert batch_chunks == chunks
    assert batch_meta == metas


# ── _text_hash / _filter_new ────────────────────────────────────────────────

def test_text_hash_matches_postgres_md5():
    # Postgres md5('hello') = '5d41402abc4b2a76b9719d911017c592'
    assert _text_hash('hello') == '5d41402abc4b2a76b9719d911017c592'


def test_filter_new_skips_chunks_with_known_hash():
    chunks = ['already indexed', 'brand new']
    metas = [{'i': 0}, {'i': 1}]
    existing = {_text_hash('already indexed')}

    new_chunks, new_metas, skipped = _filter_new(chunks, metas, existing)

    assert new_chunks == ['brand new']
    assert new_metas == [{'i': 1}]
    assert skipped == 1


def test_filter_new_keeps_everything_when_no_overlap():
    chunks = ['a', 'b']
    metas = [{'i': 0}, {'i': 1}]

    new_chunks, new_metas, skipped = _filter_new(chunks, metas, set())

    assert new_chunks == chunks
    assert new_metas == metas
    assert skipped == 0


# ── _is_rate_limit_error / _parse_retry_delay ───────────────────────────────

def test_is_rate_limit_error_true_for_429_code():
    exc = SimpleNamespace(code=429, details={})
    assert _is_rate_limit_error(exc) is True


def test_is_rate_limit_error_false_for_other_errors():
    exc = SimpleNamespace(code=500, details={})
    assert _is_rate_limit_error(exc) is False


def test_parse_retry_delay_reads_retry_info_seconds():
    exc = SimpleNamespace(details={
        'error': {
            'code': 429,
            'details': [
                {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '20s'},
            ],
        },
    })
    assert _parse_retry_delay(exc) == 20.0


def test_parse_retry_delay_returns_none_when_absent():
    # This is the exact shape of the 429 the user hit: a Help link, no RetryInfo.
    exc = SimpleNamespace(details={
        'error': {
            'code': 429,
            'message': 'You exceeded your current quota...',
            'status': 'RESOURCE_EXHAUSTED',
            'details': [
                {'@type': 'type.googleapis.com/google.rpc.Help', 'links': []},
            ],
        },
    })
    assert _parse_retry_delay(exc) is None


# ── RatePacer ────────────────────────────────────────────────────────────────

class FakeClock:
    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t

    def sleep(self, seconds):
        assert seconds >= 0
        self.t += seconds


def test_rate_pacer_no_sleep_when_under_budget():
    fc = FakeClock()
    pacer = RatePacer(max_tokens_per_min=1000, max_requests_per_min=10,
                       clock=fc.time, sleep=fc.sleep)

    pacer.wait_for_slot(100)

    assert fc.t == 0


def test_rate_pacer_sleeps_until_token_window_frees_up():
    fc = FakeClock()
    pacer = RatePacer(max_tokens_per_min=100, max_requests_per_min=100,
                       clock=fc.time, sleep=fc.sleep)

    pacer.wait_for_slot(60)   # t=0, uses 60/100 tokens
    pacer.wait_for_slot(60)   # needs the first 60 to age out of the 60s window

    assert fc.t == 60


def test_rate_pacer_sleeps_until_request_window_frees_up():
    fc = FakeClock()
    pacer = RatePacer(max_tokens_per_min=1_000_000, max_requests_per_min=2,
                       clock=fc.time, sleep=fc.sleep)

    pacer.wait_for_slot(1)
    pacer.wait_for_slot(1)
    pacer.wait_for_slot(1)   # 3rd request in the same window must wait

    assert fc.t == 60
