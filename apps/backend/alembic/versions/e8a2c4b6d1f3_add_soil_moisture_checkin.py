"""add soil_moisture_checkin

A gardener's dry/ok/wet reading per bed per day: ground truth for whether a bed
actually needed water, which the watering model's inferred labels cannot give.

Revision ID: e8a2c4b6d1f3
Revises: d7e1f3a9c5b2
Create Date: 2026-10-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8a2c4b6d1f3'
down_revision: Union[str, None] = 'd7e1f3a9c5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'soil_moisture_checkin',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('garden_id', sa.Integer(), nullable=False),
        sa.Column('bed_id', sa.Integer(), nullable=False),
        sa.Column('check_date', sa.Date(), nullable=False),
        sa.Column('level', sa.String(length=8), nullable=False),
        sa.Column('notes', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['garden_id'], ['garden.id']),
        sa.ForeignKeyConstraint(['bed_id'], ['garden_bed.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_soil_moisture_checkin_garden_id', 'soil_moisture_checkin', ['garden_id'])
    op.create_index('ix_soil_moisture_checkin_bed_id', 'soil_moisture_checkin', ['bed_id'])


def downgrade() -> None:
    op.drop_index('ix_soil_moisture_checkin_bed_id', table_name='soil_moisture_checkin')
    op.drop_index('ix_soil_moisture_checkin_garden_id', table_name='soil_moisture_checkin')
    op.drop_table('soil_moisture_checkin')
