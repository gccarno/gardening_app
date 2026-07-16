# Orchestrates the full live E2E run against Render + Neon in ONE warmed-up
# session (free-tier cold start is paid once, in Playwright's global setup):
#
#   1. optional pre-clean of [E2E] residue from failed runs
#   2. Playwright web suite   (build -> click everything -> teardown)
#   3. Android instrumented suite on the attached phone (adb)
#   4. cross-platform sync relay: web mutations -> android verify+mutate -> web verify
#   5. pull the Android E2E_MANIFEST from logcat into the run artifacts
#   6. residue check (exit non-zero if any [E2E] rows remain)
#
# Usage:
#   powershell -File scripts\run_e2e.ps1                 # full run
#   powershell -File scripts\run_e2e.ps1 -PreClean       # sweep leftovers first
#   powershell -File scripts\run_e2e.ps1 -SkipAndroid    # web-only (no phone)
#
# Requires: repo-root .env with USERNAME/PASSWORD; phone attached via adb for
# the Android phases; Android Studio JBR for gradle.
param(
    [switch]$PreClean,
    [switch]$SkipAndroid,
    [string]$BaseUrl = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$web = Join-Path $repo "apps\web"
$android = Join-Path $repo "android"
$artifacts = Join-Path $repo "tests\e2e\artifacts"
New-Item -ItemType Directory -Force $artifacts | Out-Null

# .env credentials for the Android instrumentation args (read from the FILE —
# Windows reserves the USERNAME process variable).
$dotenv = @{}
Get-Content (Join-Path $repo ".env") | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*)\s*$') {
        $dotenv[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
    }
}
if (-not $dotenv["USERNAME"] -or -not $dotenv["PASSWORD"]) {
    Write-Error "USERNAME/PASSWORD missing from .env"
}
if ($BaseUrl) { $env:GARDEN_TEST_BASE_URL = $BaseUrl }

$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$failures = @()

function Invoke-Step($name, $script) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    & $script
    if ($LASTEXITCODE -ne 0) {
        $script:failures += $name
        Write-Host "STEP FAILED: $name" -ForegroundColor Red
    }
}

function Invoke-AndroidTests($extraArgs) {
    $gradleArgs = @(
        ":app:connectedDebugAndroidTest",
        "-Pandroid.testInstrumentationRunnerArguments.E2E_BASE_URL=$($env:GARDEN_TEST_BASE_URL)",
        "-Pandroid.testInstrumentationRunnerArguments.E2E_EMAIL=$($dotenv['USERNAME'])",
        "-Pandroid.testInstrumentationRunnerArguments.E2E_PASSWORD=$($dotenv['PASSWORD'])"
    ) + $extraArgs
    Push-Location $android
    try { & .\gradlew.bat @gradleArgs --console=plain }
    finally { Pop-Location }
}

if ($PreClean) {
    Invoke-Step "pre-clean [E2E] residue" {
        Push-Location $repo
        try { uv run python scripts/e2e_cleanup.py --apply --sql } finally { Pop-Location }
    }
}

# ── Phase A: web suite ────────────────────────────────────────────────────────
Invoke-Step "Playwright web suite" {
    Push-Location $web
    try { npx playwright test } finally { Pop-Location }
}

if (-not $SkipAndroid) {
    # adb attached?
    $devices = (& adb devices) -match "device$"
    if (-not $devices) {
        Write-Host "No adb device attached - skipping Android phases." -ForegroundColor Yellow
    } else {
        & adb logcat -c   # clear so the pulled manifest is only this run

        # ── Phase B: Android suite (Sync test self-skips without sync id) ────
        Invoke-Step "Android instrumented suite" {
            Invoke-AndroidTests @()
        }

        # ── Phase C: cross-platform sync relay ───────────────────────────────
        Invoke-Step "sync relay 1/3: web mutations" {
            $env:E2E_SYNC = "1"; $env:E2E_KEEP_RUN = "1"
            Push-Location $web
            try { npx playwright test sync/sync-web-mutations.spec.ts } finally { Pop-Location }
        }

        $state = Get-Content (Join-Path $artifacts "current-run.json") -Raw | ConvertFrom-Json
        if ($state.syncGardenId) {
            Invoke-Step "sync relay 2/3: android verify + mutate" {
                Invoke-AndroidTests @(
                    "-Pandroid.testInstrumentationRunnerArguments.class=com.gardenapp.e2e.SyncVerifyAndMutateTest",
                    "-Pandroid.testInstrumentationRunnerArguments.E2E_SYNC_GARDEN_ID=$($state.syncGardenId)"
                )
            }
            Invoke-Step "sync relay 3/3: web verifies android" {
                Push-Location $web
                try { npx playwright test sync/sync-verify-android.spec.ts } finally { Pop-Location }
            }
        } else {
            $failures += "sync relay (no syncGardenId in run state)"
        }
        $env:E2E_SYNC = $null; $env:E2E_KEEP_RUN = $null

        # ── Phase D: pull the Android manifest into the run artifacts ────────
        $runId = $state.runId
        & adb logcat -d -s E2E_MANIFEST:I |
            Out-File -Encoding utf8 (Join-Path $artifacts "$runId-android-manifest.log")
    }
}

# ── Phase E: residue check (dry-run sweeper; exits 1 if anything remains) ────
Invoke-Step "residue check" {
    Push-Location $repo
    try { uv run python scripts/e2e_cleanup.py } finally { Pop-Location }
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "E2E run finished with failures:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "Manifests for backtracking: $artifacts" -ForegroundColor Yellow
    exit 1
}
Write-Host "E2E run passed. No [E2E] residue (library clones need --sql cleanup)." -ForegroundColor Green
