# Live E2E Suite (web + Android + cross-platform sync)

End-to-end tests that build a full garden **against the live Render backend
and Neon database**, click/tap everything on every screen of both apps,
verify web ⇄ Android sync, and tear the data down.

## The three suites

| Suite | Where | Runner |
|---|---|---|
| Web UI (78 tests, specs `01`–`10` + `99-teardown`) | `apps/web/e2e/` | Playwright (`npm run test:e2e` in `apps/web`) |
| Android UI (`A00`…`Z99` ordered classes) | `android/app/src/androidTest/java/com/gardenapp/e2e/` | `gradlew connectedDebugAndroidTest` (phone via adb) |
| Sync relay (web mutates → Android verifies+mutates → web verifies) | `apps/web/e2e/sync/` + `SyncVerifyAndMutateTest` | only via the orchestrator |

## Run it

```powershell
# full run, one warmed-up session (web → android → sync relay → residue check)
powershell -File scripts\run_e2e.ps1

# sweep leftovers from a previously failed run first
powershell -File scripts\run_e2e.ps1 -PreClean

# no phone attached
powershell -File scripts\run_e2e.ps1 -SkipAndroid

# selectors dry-run against a local server (never touches Neon)
$env:GARDEN_TEST_BASE_URL = "http://127.0.0.1:8000"
cd apps\web; npx playwright test
```

Credentials come from the repo-root `.env` (`USERNAME` / `PASSWORD`) — read
from the **file**, never the process environment (Windows reserves
`USERNAME`). CI/hosts without `.env` fail fast in global setup.

## Production-data safety

- Every entity the suite creates is named with the **`[E2E]` prefix** plus a
  per-run ID (`e2e-<timestamp>`). Nothing without that exact prefix is ever
  deleted.
- Every create/mutate is appended to a **JSONL manifest**
  (`tests/e2e/artifacts/<run-id>.jsonl`; Android via `E2E_MANIFEST` logcat,
  pulled by the orchestrator). After a failed teardown the manifest is the
  backtracking record for Neon.
- Teardown deletes **children first** — `DELETE /api/gardens/{id}` does not
  cascade (see `apps/backend/app/routers/gardens.py`), so orphans would be
  stranded otherwise — then the garden, then asserts zero `[E2E]` residue.
- **Known leftovers by design:** `PlantLibrary` clones and `WeatherLog`
  rain-log rows have no delete endpoints. `scripts/e2e_cleanup.py --apply
  --sql` removes them directly in Neon (`DATABASE_URL` from `.env`). The
  sweeper is also the recovery tool after any failed run:

```bash
uv run python scripts/e2e_cleanup.py              # dry-run report
uv run python scripts/e2e_cleanup.py --apply --sql # actually remove
```

- Never registers users (prod quirk: first registered user owns all gardens),
  never clicks Perenual "Save to Library", never calls
  `/api/chat/restart-model`.

## What is skipped / limited on prod

- **AI + external services** (chat, identify, tip-of-the-day, Perenual,
  weather fetch): tested skip-if-unavailable — the UI must respond, but a
  down backend skips rather than fails.
- **Garden sharing invites**: needs a second real account; only the owner row
  is asserted.
- **Web-only features** (annotations, background uploads, full library edit,
  members) and **Android-only chrome** (settings, offline banner, deep links)
  follow `android/FEATURE_GAPS.md`.

## Sync relay details

`run_e2e.ps1` chains: `sync/sync-web-mutations.spec.ts` (creates the shared
`[E2E] … Sync Garden`, writes `syncGardenId` into
`tests/e2e/artifacts/current-run.json`) → `SyncVerifyAndMutateTest` on the
phone (gets the id as the `E2E_SYNC_GARDEN_ID` instrumentation arg) →
`sync/sync-verify-android.spec.ts` (verifies, deletes the sync garden).
`E2E_KEEP_RUN=1` keeps all three phases on one run ID.
