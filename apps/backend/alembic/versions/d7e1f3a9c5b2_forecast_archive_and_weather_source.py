"""add weather_forecast_archive, widen weather_log.source

weather_forecast_archive stores each provider's per-day forecast as of the night
it was fetched, so forecast accuracy can be measured against WeatherLog.
weather_log.source grows from 10 to 32 characters so it can record the provider
('tomorrow-io', 'open-meteo') instead of the blanket 'api'.

Revision ID: d7e1f3a9c5b2
Revises: cb80b9e23c7a
Create Date: 2026-10-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7e1f3a9c5b2'
down_revision: Union[str, None] = 'cb80b9e23c7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('weather_log', 'source',
                    existing_type=sa.String(length=10),
                    type_=sa.String(length=32),
                    existing_nullable=False)

    op.create_table(
        'weather_forecast_archive',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('garden_id', sa.Integer(), nullable=False),
        sa.Column('fetched_date', sa.Date(), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('lead_days', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('precip_mm', sa.Float(), nullable=True),
        sa.Column('precip_prob', sa.Float(), nullable=True),
        sa.Column('temp_max_c', sa.Float(), nullable=True),
        sa.Column('temp_min_c', sa.Float(), nullable=True),
        sa.Column('wind_kmh', sa.Float(), nullable=True),
        sa.Column('et0_mm', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['garden_id'], ['garden.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('garden_id', 'fetched_date', 'target_date', 'provider',
                            name='uq_forecast_archive_garden_fetch_target_provider'),
    )
    op.create_index('ix_weather_forecast_archive_garden_id',
                    'weather_forecast_archive', ['garden_id'])


def downgrade() -> None:
    op.drop_index('ix_weather_forecast_archive_garden_id',
                  table_name='weather_forecast_archive')
    op.drop_table('weather_forecast_archive')
    # Narrowing fails if any row holds a provider name longer than 10 chars.
    op.execute("UPDATE weather_log SET source = 'api' WHERE length(source) > 10")
    op.alter_column('weather_log', 'source',
                    existing_type=sa.String(length=32),
                    type_=sa.String(length=10),
                    existing_nullable=False)
