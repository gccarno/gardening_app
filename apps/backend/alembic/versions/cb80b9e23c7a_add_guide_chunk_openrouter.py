"""add guide_chunk_openrouter table

Separate table for OpenRouter-embedded growing-guide chunks (see
apps/ml_service/app/embed_provider.py, which added the 'openrouter'
provider). Vectors from different embedding models aren't cosine-comparable
even at the same width, so switching EMBED_PROVIDER away from Gemini gets a
new table rather than overwriting guide_chunk's existing rows.

Populate with:
    uv run python scripts/build_rag.py --rebuild
(with EMBED_PROVIDER=openrouter in .env)

Revision ID: cb80b9e23c7a
Revises: b41c7d92e5a3
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'cb80b9e23c7a'
down_revision: Union[str, None] = 'b41c7d92e5a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'guide_chunk_openrouter',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=200), nullable=True),
        sa.Column('plant_name', sa.String(length=100), nullable=True),
        sa.Column('region', sa.String(length=50), nullable=True),
        sa.Column('page', sa.Integer(), nullable=True),
        # Width must match EMBED_DIMS in apps/ml_service/app/embed_provider.py.
        sa.Column('embedding', Vector(768), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_guide_chunk_openrouter_region', 'guide_chunk_openrouter', ['region'])

    op.execute(
        'CREATE INDEX ix_guide_chunk_openrouter_embedding ON guide_chunk_openrouter '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade() -> None:
    op.drop_index('ix_guide_chunk_openrouter_embedding', table_name='guide_chunk_openrouter')
    op.drop_index('ix_guide_chunk_openrouter_region', table_name='guide_chunk_openrouter')
    op.drop_table('guide_chunk_openrouter')
