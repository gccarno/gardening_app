import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Default: apps/api/instance/garden.db (legacy location, kept during transition).
# Set GARDEN_DB_PATH env var to override (e.g. when moving the DB after Flask is removed).
_DEFAULT_DB = Path(__file__).parents[3] / 'api' / 'instance' / 'garden.db'
_DB_PATH = os.environ.get('GARDEN_DB_PATH') or str(_DEFAULT_DB)
DATABASE_URL = f'sqlite:///{_DB_PATH}'

engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False},  # required for SQLite
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency that provides a DB session and ensures it's closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
