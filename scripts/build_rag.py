"""
Build the growing-guides vector index from gardening guides and books.

Sources indexed:
  1. TAMU Easy Gardening PDFs (~27 plants) — scripts/tamu_pdfs/easy_*.pdf
  2. TAMU Commercial Crop Guide PDFs (~40 plants) — scripts/tamu_pdfs/commercial_*.pdf
  3. Local Black & Decker gardening books — BOOKS_DIR (see below)

The resulting chunks are used by the chat tool `search_growing_guides` to answer
unstructured questions ("What pests affect tomatoes?", "How do I fertilize
peppers?") with passages from authoritative gardening sources.

Stored in Postgres (the `guide_chunk` table) with pgvector embeddings. This
replaced a ChromaDB store at apps/api/instance/rag_db/, which was gitignored —
so it never reached Render — and which pulled onnxruntime plus a 79 MB embedding
model into the request process when opened. Embeddings are now an API call; see
apps/ml_service/app/embed_provider.py.

Usage (from the repo root):
    uv run python scripts/build_rag.py                 # index all sources
    uv run python scripts/build_rag.py --source tamu   # TAMU PDFs only
    uv run python scripts/build_rag.py --source books  # local books only
    uv run python scripts/build_rag.py --rebuild       # wipe and rebuild
    uv run python scripts/build_rag.py --stats         # show index stats

Requirements:
    pdfplumber + the embedding provider's SDK (both in pyproject.toml)
    Run `uv run alembic upgrade head` first to create the table.
    Run tamu_sync.py --download-only first to populate scripts/tamu_pdfs/
"""
import argparse
import hashlib
import os
import random
import re
import sys
import time
from collections import deque

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The `apps.*` imports below resolve against the repo root. The chat tool
# imports this module with scripts/ on sys.path, where that is not guaranteed.
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

PDF_DIR   = os.path.join(os.path.dirname(__file__), 'tamu_pdfs')
BOOKS_DIR = r'C:\Users\gccar\Documents\books\gardening_books'

# Map filename substrings → region label for B&D books
_REGION_MAP = {
    'northeast':       'Northeast',
    'northwestcoast':  'Northwest',
    'mid-atlantic':    'Mid-Atlantic',
    'midatlantic':     'Mid-Atlantic',
    'uppermidwest':    'Upper Midwest',
    'lowermidwest':    'Lower Midwest',
    'lowersouth':      'Lower South',
    'westernplains':   'Western Plains',
    'lawn':            'General',
    'greenhouse':      'General',
    'landscape':       'General',
}

CHUNK_SIZE      = 1500   # characters per chunk
CHUNK_OVERLAP   = 150    # overlap between consecutive chunks


# ── PDF text extraction ────────────────────────────────────────────────────────

def extract_pdf_pages(pdf_path):
    """Extract text per page from a PDF. Returns list of (page_num, text) tuples."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError('pdfplumber required: uv add pdfplumber')

    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                t = page.extract_text()
                if t and t.strip():
                    pages.append((i, t))
    except Exception as e:
        print(f'  PDF read error {pdf_path}: {e}')
    return pages


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks


# ── Region detection ───────────────────────────────────────────────────────────

def detect_region(filename):
    """Infer region label from a B&D book filename."""
    fname_lower = filename.lower()
    for key, region in _REGION_MAP.items():
        if key in fname_lower:
            return region
    return 'General'


# ── Rate limiting & resume (Gemini free tier: 100 RPM / 30k TPM / 1K RPD) ──────
#
# add_chunks() used to send a flat batch of 100 chunks per request — at
# ~375 tokens/chunk that's ~37.5k tokens, already over the 30k TPM ceiling
# before any pacing existed, and the 429 that followed was swallowed, silently
# dropping the batch. RatePacer keeps requests under budget so 429s shouldn't
# happen on the happy path; the retry loop in add_chunks is the safety net.

GEMINI_TPM_LIMIT = 30_000
GEMINI_RPM_LIMIT = 100
TOKEN_BUDGET_PER_REQUEST = 15_000   # half the TPM ceiling, for smooth pacing


def _estimate_tokens(text):
    """Conservative token estimate (~4 chars/token) — no tokenizer round trip."""
    return len(text) // 4


def _batch_by_tokens(chunks, metadatas, max_tokens=TOKEN_BUDGET_PER_REQUEST, max_items=100):
    """Group chunks into (chunks, metadatas) batches within a token budget.

    A single chunk larger than max_tokens still gets its own batch rather than
    being dropped.
    """
    batch_chunks, batch_meta, batch_tokens = [], [], 0
    for chunk, meta in zip(chunks, metadatas):
        tokens = _estimate_tokens(chunk)
        if batch_chunks and (batch_tokens + tokens > max_tokens or len(batch_chunks) >= max_items):
            yield batch_chunks, batch_meta
            batch_chunks, batch_meta, batch_tokens = [], [], 0
        batch_chunks.append(chunk)
        batch_meta.append(meta)
        batch_tokens += tokens
    if batch_chunks:
        yield batch_chunks, batch_meta


def _text_hash(text):
    """md5 hex digest, matching Postgres md5(text) for the same string."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _filter_new(chunks, metadatas, existing_hashes):
    """Drop chunks whose content hash is already indexed. Returns (chunks, metadatas, skipped)."""
    new_chunks, new_meta, skipped = [], [], 0
    for chunk, meta in zip(chunks, metadatas):
        if _text_hash(chunk) in existing_hashes:
            skipped += 1
        else:
            new_chunks.append(chunk)
            new_meta.append(meta)
    return new_chunks, new_meta, skipped


def _load_existing_hashes(db):
    """Content hashes already in guide_chunk, for resume-without-a-state-file."""
    from sqlalchemy import func, select
    from apps.backend.app.db.models import GuideChunk

    rows = db.execute(select(func.md5(GuideChunk.text))).scalars().all()
    return set(rows)


def _is_rate_limit_error(exc):
    """True for a Gemini 429 RESOURCE_EXHAUSTED, by duck-typed error shape."""
    if getattr(exc, 'code', None) == 429 or getattr(exc, 'status_code', None) == 429:
        return True
    return 'RESOURCE_EXHAUSTED' in str(exc)


def _parse_retry_delay(exc):
    """Seconds to wait per the API's RetryInfo detail, or None if absent.

    Free-tier 429s (see module docstring's error message) typically carry only
    a Help link, no RetryInfo — callers must fall back to their own backoff.
    """
    details = getattr(exc, 'details', None)
    if not isinstance(details, dict):
        return None
    error = details.get('error', details)
    for d in error.get('details') or []:
        if isinstance(d, dict) and str(d.get('@type', '')).endswith('RetryInfo'):
            delay = d.get('retryDelay')
            if isinstance(delay, str) and delay.endswith('s'):
                try:
                    return float(delay[:-1])
                except ValueError:
                    return None
    return None


class RatePacer:
    """Client-side limiter so requests stay under Gemini's free-tier RPM/TPM.

    Tracks (timestamp, tokens) for requests in the trailing 60s window and
    sleeps just long enough for the oldest entry to age out when a new
    request would exceed either budget.
    """

    def __init__(self, max_tokens_per_min=GEMINI_TPM_LIMIT, max_requests_per_min=GEMINI_RPM_LIMIT,
                 clock=time.monotonic, sleep=time.sleep):
        self.max_tokens_per_min = max_tokens_per_min
        self.max_requests_per_min = max_requests_per_min
        self._clock = clock
        self._sleep = sleep
        self._window = deque()   # (timestamp, tokens)

    def wait_for_slot(self, tokens):
        while True:
            now = self._clock()
            while self._window and now - self._window[0][0] >= 60:
                self._window.popleft()

            window_tokens = sum(t for _, t in self._window)
            over_tokens = window_tokens + tokens > self.max_tokens_per_min
            over_requests = len(self._window) + 1 > self.max_requests_per_min
            if not (over_tokens or over_requests):
                break

            wait = 60 - (now - self._window[0][0])
            self._sleep(max(wait, 0))

        self._window.append((self._clock(), tokens))


class RateLimitBudgetExceeded(Exception):
    """Raised when --max-wait is exhausted waiting on repeated 429s.

    Already-committed chunks are safe (add_chunks commits per batch) and their
    hashes are already in guide_chunk, so re-running the same command resumes
    from where this stopped.
    """


class IndexConfig:
    """Bundles the rate-limit/resume state threaded through one indexing run."""

    def __init__(self, existing_hashes, max_wait=1800, wait_forever=False):
        self.pacer = RatePacer()
        self.existing_hashes = existing_hashes
        self.max_wait = max_wait
        self.wait_forever = wait_forever
        self.waited_total = 0.0


# ── Postgres helpers ───────────────────────────────────────────────────────────

def get_collection(rebuild=False):
    """Open a DB session for indexing, optionally clearing existing chunks.

    Kept under the original name so index_tamu_pdfs / index_books read the same
    as before; the "collection" is now the guide_chunk table.
    """
    from apps.backend.app.db.session import SessionLocal
    from apps.backend.app.db.models import GuideChunk

    db = SessionLocal()
    if rebuild:
        deleted = db.query(GuideChunk).delete()
        db.commit()
        print(f'Deleted {deleted} existing chunks')
    return db


def add_chunks(db, chunks, metadatas, id_prefix, cfg):
    """Embed a list of text chunks and insert them with their metadata.

    `id_prefix` is no longer used for identity — the table has a serial primary
    key — but the parameter stays so callers are unchanged.

    Chunks already present (by content hash, via `cfg.existing_hashes`) are
    skipped before they cost a token. Each token-budgeted batch is paced by
    `cfg.pacer` and committed immediately on success, so a restart after a
    kill or an exhausted --max-wait only re-embeds what never landed.

    Returns (added, skipped).
    """
    if not chunks:
        return 0, 0

    from apps.backend.app.db.models import GuideChunk
    from apps.ml_service.app.embed_provider import embed

    chunks, metadatas, skipped = _filter_new(chunks, metadatas, cfg.existing_hashes)
    if not chunks:
        return 0, skipped

    added = 0
    for batch_chunks, batch_meta in _batch_by_tokens(chunks, metadatas):
        cfg.pacer.wait_for_slot(sum(_estimate_tokens(c) for c in batch_chunks))

        attempt = 0
        while True:
            attempt += 1
            try:
                vectors = embed(batch_chunks)
                break
            except Exception as e:
                if _is_rate_limit_error(e):
                    delay = _parse_retry_delay(e)
                    if delay is None:
                        delay = min(300, 5 * 2 ** (attempt - 1))
                        delay += random.uniform(0, delay * 0.2)
                    if not cfg.wait_forever and cfg.waited_total + delay > cfg.max_wait:
                        raise RateLimitBudgetExceeded(
                            f'Exhausted --max-wait ({cfg.max_wait}s) waiting on rate limits '
                            f'after {added} chunks added in this call. guide_chunk keeps what '
                            f'committed — just re-run the same command to resume, or pass '
                            f'--wait-forever for an unattended run.'
                        ) from e
                    print(f'    rate limited (attempt {attempt}), waiting {delay:.0f}s...')
                    time.sleep(delay)
                    cfg.waited_total += delay
                    continue

                if attempt >= 3:
                    raise
                delay = 2 * attempt
                print(f'    embed error (attempt {attempt}), retrying in {delay}s: {e}')
                time.sleep(delay)

        db.add_all([
            GuideChunk(
                text=chunk,
                source=meta.get('source', ''),
                plant_name=meta.get('plant_name', ''),
                region=meta.get('region', ''),
                # TAMU guides carry no page number; books do.
                page=meta.get('page') or None,
                embedding=vector,
            )
            for chunk, meta, vector in zip(batch_chunks, batch_meta, vectors)
        ])
        db.commit()
        added += len(batch_chunks)
        cfg.existing_hashes.update(_text_hash(c) for c in batch_chunks)

    return added, skipped


# ── TAMU indexing ──────────────────────────────────────────────────────────────

def index_tamu_pdfs(collection, cfg):
    """Index all downloaded TAMU PDFs (small guides — treated as single document)."""
    if not os.path.isdir(PDF_DIR):
        print(f'TAMU PDF dir not found: {PDF_DIR}')
        print('Run: python scripts/tamu_sync.py --download-only')
        return 0

    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]
    if not pdf_files:
        print(f'No PDFs in {PDF_DIR} — run tamu_sync.py --download-only first')
        return 0

    total_added = 0
    for fname in sorted(pdf_files):
        pdf_path = os.path.join(PDF_DIR, fname)

        # Derive plant name and series from filename (e.g. easy_tomato.pdf)
        m = re.match(r'(easy|commercial)_(.+)\.pdf', fname)
        if m:
            series     = m.group(1)
            plant_name = m.group(2).replace('_', ' ').title()
        else:
            series     = 'tamu'
            plant_name = fname.replace('.pdf', '').replace('_', ' ').title()

        pages = extract_pdf_pages(pdf_path)
        if not pages:
            continue

        # For small TAMU guides, concatenate all pages then chunk
        full_text = '\n\n'.join(text for _, text in pages)
        chunks = chunk_text(full_text)

        metadatas = [
            {
                'source':     f'TAMU {series.title()} Gardening Guide',
                'plant_name': plant_name,
                'series':     series,
                'region':     'Texas (applicable broadly)',
                'filename':   fname,
            }
            for _ in chunks
        ]

        id_prefix = f'tamu_{series}_{re.sub(r"[^a-z0-9]", "_", plant_name.lower())}'
        added, skipped = add_chunks(collection, chunks, metadatas, id_prefix, cfg)
        total_added += added
        skip_note = f', {skipped} already indexed' if skipped else ''
        print(f'  [{series}] {plant_name}: {added} chunks added{skip_note}')

    return total_added


# ── B&D books indexing ─────────────────────────────────────────────────────────

def index_books(collection, cfg):
    """Index local Black & Decker gardening books (large — chunked per page)."""
    if not os.path.isdir(BOOKS_DIR):
        print(f'Books directory not found: {BOOKS_DIR}')
        return 0

    pdf_files = [f for f in os.listdir(BOOKS_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f'No PDFs found in {BOOKS_DIR}')
        return 0

    total_added = 0
    for fname in sorted(pdf_files):
        pdf_path = os.path.join(BOOKS_DIR, fname)
        region   = detect_region(fname)

        # Title: strip "blackanddecker" prefix and clean up
        title = fname.replace('.pdf', '')
        title = re.sub(r'^blackanddecker', '', title, flags=re.IGNORECASE)
        title = re.sub(r'thecompleteguide(to)?', '', title, flags=re.IGNORECASE)
        title = re.sub(r'[a-z](?=[A-Z])', lambda m: m.group() + ' ', title)
        title = title.strip().title()

        print(f'  [{region}] {title}')
        pages = extract_pdf_pages(pdf_path)
        if not pages:
            print(f'    no text extracted')
            continue

        # For large books: chunk each page's text individually
        all_chunks = []
        all_meta   = []
        for page_num, page_text in pages:
            page_chunks = chunk_text(page_text)
            for chunk in page_chunks:
                all_chunks.append(chunk)
                all_meta.append({
                    'source':    f'Black & Decker Complete Guide ({region})',
                    'region':    region,
                    'book':      title,
                    'page':      page_num,
                    'filename':  fname,
                    'plant_name': '',   # books cover many plants; no single plant name
                })

        safe_fname = re.sub(r'[^a-z0-9]', '_', fname.lower().replace('.pdf', ''))
        added, skipped = add_chunks(collection, all_chunks, all_meta, f'book_{safe_fname}', cfg)
        total_added += added
        skip_note = f', {skipped} already indexed' if skipped else ''
        print(f'    {len(pages)} pages → {added} chunks added{skip_note}')

    return total_added


# ── Search helper (used by chat tool) ─────────────────────────────────────────

def search_guides(query, plant_name=None, n_results=3, region_filter=None):
    """
    Search the growing guides. Returns list of result dicts.

    Called by the chat tool `search_growing_guides` at runtime. Embeds the query
    via an API call, then runs one pgvector nearest-neighbour query — nothing is
    loaded into the process, which is what makes this survive a 512 MB instance.

    Returns [] gracefully if the table is empty or the embedding call fails, so
    a retrieval outage degrades the answer rather than breaking the chat turn.
    """
    from sqlalchemy import select

    from apps.backend.app.db.session import SessionLocal
    from apps.backend.app.db.models import GuideChunk
    from apps.ml_service.app.embed_provider import embed_one

    try:
        vector = embed_one(query, is_query=True)
    except Exception:
        return []

    # `<=>` is pgvector's cosine distance; 1 - distance gives back the cosine
    # similarity the old Chroma path reported, so scores stay comparable.
    distance = GuideChunk.embedding.cosine_distance(vector).label('distance')

    stmt = select(GuideChunk, distance).order_by(distance).limit(n_results)
    if region_filter:
        stmt = stmt.where(GuideChunk.region == region_filter)

    try:
        with SessionLocal() as db:
            rows = db.execute(stmt).all()
    except Exception:
        return []

    return [
        {
            'text':   chunk.text,
            'source': chunk.source or '',
            'plant':  chunk.plant_name or '',
            'region': chunk.region or '',
            'page':   chunk.page or '',
            'score':  round(1 - float(dist), 3),   # cosine similarity
        }
        for chunk, dist in rows
    ]


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Build RAG index from gardening guides')
    p.add_argument('--source',  choices=['tamu', 'books', 'all'], default='all',
                   help='Which sources to index (default: all)')
    p.add_argument('--rebuild', action='store_true',
                   help='Wipe existing collection before indexing')
    p.add_argument('--stats',   action='store_true',
                   help='Show collection stats and exit')
    p.add_argument('--max-wait', type=float, default=1800,
                   help='Max total seconds to wait out rate limits before exiting (default: 1800)')
    p.add_argument('--wait-forever', action='store_true',
                   help='Ignore --max-wait and keep retrying rate limits indefinitely')
    return p.parse_args()


def main():
    args = parse_args()

    from apps.backend.app.db.models import GuideChunk
    from apps.ml_service.app.embed_provider import DIMS, PROVIDER, _model

    if args.stats:
        from sqlalchemy import func, select
        from apps.backend.app.db.session import SessionLocal
        try:
            with SessionLocal() as db:
                total = db.scalar(select(func.count()).select_from(GuideChunk))
                by_source = db.execute(
                    select(GuideChunk.source, func.count())
                    .group_by(GuideChunk.source)
                    .order_by(func.count().desc())
                ).all()
            print(f'Chunks: {total}')
            for source, count in by_source:
                print(f'  {count:>6}  {source or "(no source)"}')
        except Exception as e:
            print(f'Error reading guide_chunk: {e}')
        return

    print(f'Embedding with {PROVIDER}/{_model(PROVIDER)} at {DIMS} dims')

    db = get_collection(rebuild=args.rebuild)
    existing_hashes = _load_existing_hashes(db)
    if existing_hashes:
        print(f'{len(existing_hashes)} chunks already indexed — will be skipped')
    cfg = IndexConfig(existing_hashes, max_wait=args.max_wait, wait_forever=args.wait_forever)

    resume_cmd = ' '.join(sys.argv)
    total_added = 0
    try:
        if args.source in ('tamu', 'all'):
            print('\n=== Indexing TAMU PDFs ===')
            total_added += index_tamu_pdfs(db, cfg)

        if args.source in ('books', 'all'):
            print('\n=== Indexing Local Gardening Books ===')
            total_added += index_books(db, cfg)

        from sqlalchemy import func, select
        total = db.scalar(select(func.count()).select_from(GuideChunk))
    except (RateLimitBudgetExceeded, KeyboardInterrupt) as e:
        print(f'\nStopped after adding {total_added} chunks this run: {e}')
        print(f'Already-indexed chunks are skipped automatically — resume with:\n  {resume_cmd}')
        sys.exit(1)
    finally:
        db.close()

    print(f'\nDone. Total chunks added: {total_added}')
    print(f'guide_chunk now has {total} rows')


if __name__ == '__main__':
    main()
