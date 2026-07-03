import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()  # session.py is imported before helpers.py loads .env

# Priority:
#   1. DATABASE_URL — full SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host/db
#      (used for Neon Postgres in the cloud deployment)
#   2. GARDEN_DB_PATH — path to a SQLite file
#   3. Legacy default: apps/api/instance/garden.db
_DEFAULT_DB = Path(__file__).parents[3] / 'api' / 'instance' / 'garden.db'
_DB_PATH = os.environ.get('GARDEN_DB_PATH') or str(_DEFAULT_DB)
DATABASE_URL = os.environ.get('DATABASE_URL') or f'sqlite:///{_DB_PATH}'

if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},  # required for SQLite
    )
else:
    # Neon's free tier suspends idle compute and drops connections;
    # pool_pre_ping transparently reconnects on the next request.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency that provides a DB session and ensures it's closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
