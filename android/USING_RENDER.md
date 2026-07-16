# Using the Android App with the Render Cloud Backend

The Android app talks to the FastAPI backend hosted on Render:

**https://garden-app-wa0b.onrender.com**

This is the app's **default server URL** (`ServerConfig.DEFAULT_BASE_URL`), so a freshly
installed app works anywhere with internet — no local server, no LAN setup.

> Note: `garden-app.onrender.com` (without the `-wa0b` suffix) is **someone else's site**.
> Always use the suffixed URL above.

## Signing In

1. Open the app. The login screen appears.
2. Enter the email and password of an account **created on the web app** (registration is
   web-only; the Android app cannot create accounts).
3. Tap **Sign in**. On success the token is stored and you stay logged in across restarts.

The server URL is saved after the first successful login, and can be changed later in the
**Settings** tab or via **"Server settings"** on the login screen.

## Cold Starts (Free Tier)

The Render service runs on the free tier, which **spins down after ~15 minutes of no
traffic**. The first request after idle can take **30–60 seconds** while the service boots.

- If a login or sync appears to hang right after opening the app, wait up to a minute and
  try again — the second attempt is usually instant.
- You can pre-warm it by opening https://garden-app-wa0b.onrender.com/api/health in any
  browser and waiting for `{"status": ...}`.

## Switching Between Cloud and Local Backends

| Scenario | Server URL |
|---|---|
| Normal use (anywhere) | `https://garden-app-wa0b.onrender.com` (default) |
| Local backend + **emulator** | `http://10.0.2.2:8000` |
| Local backend + **physical device** on your Wi-Fi | `http://<your PC's LAN IP>:8000`, e.g. `http://192.168.4.24:8000` |

For local backends, start the server so it's reachable from the device:

```powershell
cd apps/backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**HTTP vs HTTPS:** only **debug builds** allow plain `http://` URLs (cleartext). Release
builds are HTTPS-only, so they can effectively only use the Render URL.

## Remote Login Tests

JVM unit tests that log in against the real Render backend live at
`app/src/test/java/com/gardenapp/remote/RemoteLoginTest.kt`. They read the login
credentials from the repo-root `.env` file (`USERNAME` / `PASSWORD` keys) and are
**skipped automatically** when that file or those keys are absent (e.g. in CI).

```powershell
cd android
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
.\gradlew :app:testDebugUnitTest --console=plain
```

To run the same tests against a local backend instead, set an override URL first:

```powershell
$env:GARDEN_TEST_BASE_URL = 'http://127.0.0.1:8000'
```

The web app has an equivalent suite at `apps/web/src/test/remote-login.test.ts`
(run with `npm test` in `apps/web`; same `.env` gating and `GARDEN_TEST_BASE_URL` override).

## Fetching Render Logs

`scripts/render_logs.py` pulls recent service logs from the Render API for debugging:

```powershell
uv run python scripts/render_logs.py            # last 100 log lines
uv run python scripts/render_logs.py --limit 300
uv run python scripts/render_logs.py --errors   # level=error, HTTP >= 400, tracebacks
uv run python scripts/render_logs.py --grep "plants"
uv run python scripts/render_logs.py --json     # machine-readable JSON lines
```

Access-log lines are parsed into method/path/status, so `--errors` catches failing
requests (4xx/5xx) as well as server tracebacks. Live tests for the Render API
integration are in `tests/integration/test_render_api.py` (skipped when the key is
absent); parsing has offline unit tests in `tests/unit/test_render_log_parsing.py`.

It needs a **Render API key** in the repo-root `.env`:

1. Render Dashboard → click your avatar → **Account Settings** → **API Keys** → Create.
2. Add to `.env`: `RENDER_API_KEY=rnd_...`

Without the key the script exits with instructions instead of logs.

## Troubleshooting

- **"Failed to connect" immediately** — check the device has internet and the URL has no
  typo (must be `https://garden-app-wa0b.onrender.com`).
- **Hangs ~30–60 s then works** — free-tier cold start, see above.
- **401 on login** — wrong email/password, or the account doesn't exist yet (create it on
  the web app first).
- **Works on Wi-Fi but not mobile data with a `http://192.168.x.x` URL** — LAN URLs only
  work on your home network; switch back to the Render URL.
- **Server-side errors (500s)** — pull the logs with `scripts/render_logs.py`.
