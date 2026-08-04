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
import os
import re
import sys

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


def add_chunks(db, chunks, metadatas, id_prefix):
    """Embed a list of text chunks and insert them with their metadata.

    `id_prefix` is no longer used for identity — the table has a serial primary
    key — but the parameter stays so callers are unchanged.
    """
    if not chunks:
        return 0

    from apps.backend.app.db.models import GuideChunk
    from apps.ml_service.app.embed_provider import embed

    batch_size = 100
    added = 0
    for start in range(0, len(chunks), batch_size):
        batch_chunks = chunks[start:start + batch_size]
        batch_meta   = metadatas[start:start + batch_size]
        try:
            vectors = embed(batch_chunks)
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
        except Exception as e:
            db.rollback()
            print(f'    add error: {e}')
    return added


# ── TAMU indexing ──────────────────────────────────────────────────────────────

def index_tamu_pdfs(collection):
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
        added = add_chunks(collection, chunks, metadatas, id_prefix)
        total_added += added
        print(f'  [{series}] {plant_name}: {len(chunks)} chunks added')

    return total_added


# ── B&D books indexing ─────────────────────────────────────────────────────────

def index_books(collection):
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
        added = add_chunks(collection, all_chunks, all_meta, f'book_{safe_fname}')
        total_added += added
        print(f'    {len(pages)} pages → {len(all_chunks)} chunks added')

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
    total_added = 0
    try:
        if args.source in ('tamu', 'all'):
            print('\n=== Indexing TAMU PDFs ===')
            total_added += index_tamu_pdfs(db)

        if args.source in ('books', 'all'):
            print('\n=== Indexing Local Gardening Books ===')
            total_added += index_books(db)

        from sqlalchemy import func, select
        total = db.scalar(select(func.count()).select_from(GuideChunk))
    finally:
        db.close()

    print(f'\nDone. Total chunks added: {total_added}')
    print(f'guide_chunk now has {total} rows')


if __name__ == '__main__':
    main()
