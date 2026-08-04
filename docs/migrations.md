# Database migrations

Phase 3 of the observability work. Schema changes now go through Alembic, tested
on a disposable Neon branch, with a CI check that catches the exact bug that took
production down on 2026-07-21.

See [`observability.md`](observability.md) for the other phases.

---

## What was wrong

`apps/backend/app/main.py` carried a hand-maintained list of raw DDL that ran
against production on every boot:

```python
_POSTGRES_MIGRATIONS = [
    'ALTER TABLE weather_log ADD COLUMN IF NOT EXISTS humidity_pct FLOAT',
    'ALTER TABLE weather_log ADD COLUMN IF NOT EXISTS et0_mm FLOAT',
]
```

That list exists *because of* the outage. `humidity_pct` and `et0_mm` were added
to the model and written by the weather job, but `create_all()` only creates
missing tables — it never alters existing ones. The live table lacked both
columns, and the mismatch surfaced only as a 500 from the nightly job, days later.

The list patched that instance. It did nothing about the next one: adding a
column to `models.py` and forgetting the DDL was still a silent, deploy-time
error with no check anywhere.

## What it is now

| Concern | Before | Now |
|---|---|---|
| Table creation (Postgres) | `Base.metadata.create_all()` | `alembic upgrade head` |
| Column changes (Postgres) | hand-written `ALTER TABLE` list | Alembic revisions |
| Detecting drift | production 500 | `alembic check` in CI |
| Testing a migration | none | Neon branch |
| SQLite (local/legacy) | `create_all` + PRAGMA backfills | **unchanged** |

`create_all()` is deliberately **not** called on Postgres any more. The initial
revision creates every table, so running both would race: `create_all` makes the
table, then the migration's `CREATE TABLE` fails.

SQLite keeps the old path. The revisions are Postgres-shaped and SQLite can't
`ALTER` columns the same way.

## Changing the schema

```bash
# 1. Edit apps/backend/app/db/models.py

# 2. Make a disposable Neon branch to test against
#    (MCP: create_branch, or the Neon console)

# 3. Point at the branch, never production
export DATABASE_URL='postgresql+psycopg://…branch-host…/neondb?sslmode=require'

# 4. Generate the revision
uv run alembic revision --autogenerate -m "add weather_log.wind_mph"

# 5. READ IT. Autogenerate is a first draft, not an oracle — it misses
#    server defaults, renames (it emits drop+add, which loses data), and
#    CHECK constraints.

# 6. Apply and verify on the branch
uv run alembic upgrade head
uv run alembic check          # -> "No new upgrade operations detected."

# 7. Commit the revision. Production migrates itself on next deploy.
```

Set `expiresAt` when creating the branch so it cleans itself up.

## How it reaches production

`_run_alembic_upgrade()` in `main.py` runs `alembic upgrade head` at startup.
Chosen over migrating in Render's `buildCommand` because a failed migration then
means the app doesn't boot, the health check fails, and Render rolls back — the
database can't end up ahead of the running code. Cost is one extra query per cold
start when nothing is pending.

## The guard against migrating production by hand (added 2026-08-04)

`.env` points `DATABASE_URL` at the production Neon endpoint, so a bare
`uv run alembic upgrade head` migrates **production** — which is how the
2026-08-01 outage happened. The `guide_chunk` revision was applied to Neon from a
laptop while the revision file was still uncommitted. Alembic then found the live
database stamped at a revision the deployed code had never heard of, and every
startup died in the lifespan:

```
CommandError: Can't locate revision identified by 'b41c7d92e5a3'
```

The app never served a request. Production was down for two days; the nightly
jobs and live E2E both failed with connection timeouts, which read as "Render is
being flaky" rather than as a schema fault. The process above was already
correct — step 3 says *never production* — but nothing enforced it.

`apps/backend/alembic/env.py` now refuses `upgrade`, `downgrade` and `stamp` from
the CLI when `DATABASE_URL` points anywhere that isn't localhost:

```
alembic upgrade: refusing to write to the remote database at ep-crimson-star-….neon.tech.
```

- Read-only commands (`current`, `history`, `check`) still work against
  production — that is how you diagnose a drift like this one.
- `revision --autogenerate` still works too; it only writes a local file, and
  diffing against the real schema is the point of it.
- The app is unaffected. The guard keys off `config.cmd_opts`, which Alembic only
  populates in its own argv parser, so `_run_alembic_upgrade()` calling
  `command.upgrade()` comes through as not-a-CLI-invocation.
- For a deliberate recovery step, such as re-stamping a restored backup:
  `ALEMBIC_ALLOW_REMOTE=1 uv run alembic stamp head`

## The CI check (the actual safety net)

`.github/workflows/ci.yaml` gained a `migrations` job that, against a throwaway
Postgres service container:

1. `alembic upgrade head` — builds the schema from revisions alone
2. `alembic check` — asserts the result matches `models.py`
3. `alembic downgrade base` — asserts the revisions are reversible

No Neon credential, no contact with production.

The service container is `pgvector/pgvector:pg18`, not stock `postgres:18`. The
`guide_chunk` revision opens with `CREATE EXTENSION vector`, which stock Postgres
does not ship — Neon has it, so that gap only ever shows up in CI.

**This is what would have caught the July 21 bug.** Verified by simulating it:
adding `wind_mph` to the `WeatherLog` model without a revision made `check` fail
with

```
FAILED: New upgrade operations detected:
  [('add_column', None, 'weather_log', Column('wind_mph', Float(), ...))]
```

## Adopting Alembic on the existing database (done once, 2026-07-26)

The initial revision was generated against an **empty** database so it contains
real `create_table` calls (19 of them) rather than being an empty baseline. An
empty baseline would have been quicker, but migrations then couldn't build a
schema from scratch, which is what makes the CI check possible.

Production already had the schema, so it was marked as already-at that revision
rather than re-running it:

```bash
uv run alembic stamp head
```

Before stamping, production was compared against a branch built purely from the
migrations (Neon `compare_database_schema`). The only differences were the
`alembic_version` table itself and **column order in `weather_log`** — production
has `source, humidity_pct, et0_mm`, the migration produces
`humidity_pct, et0_mm, source`, because the two columns were appended by
`ALTER TABLE` during the outage fix. Same columns, no semantic difference for
named-column access. Stamping was therefore truthful.

> If the database is ever restored from a pre-Alembic backup, it must be stamped
> again before the app starts, or `upgrade head` will try to create tables that
> already exist.

## Verified on 2026-07-26

- ✅ `alembic check` against a branch of production: no drift — models and the
  live schema were already in sync
- ✅ Simulated the July 21 bug; `check` failed with the correct `add_column`
- ✅ Applied a test migration to a branch, confirmed the column existed there and
  **not** in production (0 rows in `information_schema`) — branch isolation works
- ✅ Wiped a branch and rebuilt all 19 tables from revisions alone; `check` clean
- ✅ Round trip: `upgrade` → `downgrade base` → `upgrade` → `check` clean
- ✅ App startup path migrates an empty Postgres and is idempotent across restarts
- ✅ Production stamped; `alembic check` against production now clean
- ✅ 196 unit/data tests pass

## Not done

- `_GARDEN_MIGRATIONS` / `_PLANT_LIBRARY_MIGRATIONS` (the SQLite PRAGMA
  backfills) are untouched. They only run on SQLite, which is the frozen
  pre-migration backup and local dev.
- ~~No revision has yet been written *by* this workflow in anger — the only one
  is the initial schema. The first real column change is the true test.~~
  The first real revision was `b41c7d92e5a3` (`guide_chunk`), and it failed the
  test: not because the tooling was wrong, but because the revision was applied
  to production before it was committed. Hence the guard above.
