"""Alembic environment — wired to the app's models and DATABASE_URL.

Usage (from the repo root):
    uv run alembic revision --autogenerate -m "add my_column"
    uv run alembic upgrade head

The database URL comes from the same resolution as the app itself
(DATABASE_URL env var, else GARDEN_DB_PATH, else the legacy SQLite file).
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from apps.backend.app.db.models import Base
from apps.backend.app.db.session import DATABASE_URL

config = context.config
config.set_main_option('sqlalchemy.url', DATABASE_URL)

# Only the commands that write to the database itself. `revision --autogenerate`
# and `merge` just write a local file, and autogenerating against the real schema
# is the point of it; `current`, `history` and `check` are how you diagnose a
# drift like the one below. All of those stay allowed.
#
# This matters because .env points DATABASE_URL at the production Neon endpoint,
# so every local alembic run targets production unless told otherwise.
_WRITE_COMMANDS = {'upgrade', 'downgrade', 'stamp'}
_LOCAL_HOSTS = {None, '', 'localhost', '127.0.0.1', '::1'}


def _cli_command() -> str | None:
    """Name of the Alembic CLI command, or None when driven from the app.

    Alembic only populates cmd_opts in its own argv parser, so the app calling
    command.upgrade() programmatically comes through as None.
    """
    cmd_opts = getattr(config, 'cmd_opts', None)
    if cmd_opts is None:
        return None
    return getattr(cmd_opts, 'cmd', [None])[0].__name__


def _refuse_remote_write_from_cli() -> None:
    """Stop a laptop from migrating production ahead of the deployed code.

    On 2026-08-01 the guide_chunk revision was applied to Neon by hand while the
    revision file was still uncommitted. Alembic then found a stamped revision
    the deployed code had never heard of, so every startup died on
    "Can't locate revision identified by 'b41c7d92e5a3'" — a two-day outage that
    nothing in CI could see, because CI only ever compares code against code.

    Migrations reach production by being pushed: main.py applies them on startup.
    """
    command = _cli_command()
    if command not in _WRITE_COMMANDS:
        return
    if os.environ.get('ALEMBIC_ALLOW_REMOTE') == '1':
        return

    host = make_url(DATABASE_URL).host
    if host in _LOCAL_HOSTS:
        return

    raise SystemExit(
        f"\nalembic {command}: refusing to write to the remote database at {host}.\n\n"
        f"Migrations reach production by being committed and pushed. The app runs\n"
        f"them on startup (apps/backend/app/main.py, _run_alembic_upgrade). Applying\n"
        f"one from here stamps the live database with a revision the deployed code\n"
        f"does not have, and every restart then crashes until they line up again.\n\n"
        f"Point DATABASE_URL at a local or throwaway database instead. If this is a\n"
        f"deliberate recovery step, such as a one-off stamp:\n"
        f"    ALEMBIC_ALLOW_REMOTE=1 uv run alembic {command} ...\n"
    )


_refuse_remote_write_from_cli()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
