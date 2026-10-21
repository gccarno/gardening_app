"""add plant_image_prototype

Per-species image-embedding prototypes for on-device plant ID. The vector
column is untyped and unindexed on purpose — see PlantImagePrototype.

Populate after upgrading with:
    uv run --no-sync python scripts/build_plantid_prototypes.py --version <v>

Revision ID: f3c9a1d5e7b2
Revises: e8a2c4b6d1f3
Create Date: 2026-10-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'f3c9a1d5e7b2'
down_revision: Union[str, None] = 'e8a2c4b6d1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'plant_image_prototype',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_version', sa.String(length=40), nullable=False),
        sa.Column('species_key', sa.String(length=200), nullable=False),
        sa.Column('scientific_name', sa.String(length=200), nullable=False),
        sa.Column('plant_library_id', sa.Integer(), nullable=True),
        sa.Column('n_images', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(), nullable=False),
        sa.ForeignKeyConstraint(['plant_library_id'], ['plant_library.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_version', 'species_key',
                            name='uq_plant_image_prototype_version_species'),
    )
    op.create_index('ix_plant_image_prototype_model_version', 'plant_image_prototype',
                    ['model_version'])


def downgrade() -> None:
    op.drop_index('ix_plant_image_prototype_model_version', table_name='plant_image_prototype')
    op.drop_table('plant_image_prototype')
