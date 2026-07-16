# Android Build Guide

Step-by-step instructions for opening and running the garden app Android project in Android Studio.

---

## Prerequisites

| Tool | Required Version | Download |
|---|---|---|
| Android Studio | Ladybug (2024.2.x) or newer | [developer.android.com/studio](https://developer.android.com/studio) |
| JDK | 17 (bundled with Android Studio) | Included |
| Android SDK | API 35 (Android 15) | Installed via SDK Manager |
| Android SDK min | API 26 (Android 8.0) | Installed via SDK Manager |
| Kotlin | 2.0.0 | Managed by Gradle |

> Android Studio bundles its own JDK 17. You do not need to install a separate JDK unless you use the terminal outside Android Studio.

---

## 1. Open the Project

1. Launch Android Studio.
2. On the welcome screen, click **Open**.
3. Navigate to:
   ```
   C:\Users\gccar\Documents\gardening\garden_app\gardening_app\android
   ```
4. Click **OK**. Android Studio will open the `android/` folder as the project root.
5. Wait for the initial **Gradle sync** to complete (bottom status bar). This downloads all dependencies and may take 2–5 minutes on first open.

> If Gradle sync fails, see [Troubleshooting](#troubleshooting) below.

---

## 2. Configure the Backend Server URL

The Android app connects to the FastAPI backend over HTTP(S). The default URL is the cloud backend on Render, `https://garden-app-wa0b.onrender.com` — no local server needed. See [USING_RENDER.md](USING_RENDER.md) for details. For local development, override the URL as below.

### For the Android Emulator
Set the server URL to `http://10.0.2.2:8000` (the emulator's alias for `localhost` on your development machine) via the login screen's "Server settings" or the Settings tab. Start the FastAPI backend on your machine:
```powershell
cd apps/backend
uv run uvicorn app.main:app --reload --port 8000
```
The emulator routes `10.0.2.2:8000` to your machine's `localhost:8000` automatically.

### For a Physical Device (USB or Wi-Fi)
1. Find your machine's local IP address:
   ```powershell
   ipconfig
   # Look for IPv4 Address under your active adapter, e.g. 192.168.1.42
   ```
2. Start the FastAPI backend binding to all interfaces:
   ```powershell
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
3. In the app, open **Settings** (gear icon on the Dashboard) and set the server URL to:
   ```
   http://192.168.1.42:8000
   ```
   (replace with your actual IP)
4. Tap **Save & Apply**.

> Your phone and development machine must be on the **same Wi-Fi network**.

---

## 3. Run on an Emulator

1. In Android Studio, open **Device Manager** (right side panel or **View → Tool Windows → Device Manager**).
2. Click **+** → **Create Virtual Device**.
3. Choose a device (e.g. **Pixel 8**), click **Next**.
4. Select a system image — choose **API 35 (Android 15)** with Google Play. Download it if needed.
5. Finish the wizard and click **Start** (▶) to launch the emulator.
6. Once the emulator boots, click the green **Run** button (▶) in the toolbar, or press **Shift+F10**.
7. Select your emulator from the deployment target list.

---

## 4. Run on a Physical Android Device (USB)

1. On your Android phone, enable **Developer Options**:
   - Go to **Settings → About phone** → tap **Build number** 7 times.
2. In Developer Options, enable **USB Debugging**.
3. Connect your phone via USB cable.
4. Accept the **"Allow USB debugging?"** prompt on the phone.
5. In Android Studio, click the **Run** button (▶). Your device should appear in the deployment target list.

---

## 5. Build a Debug APK

To install the APK manually (without Android Studio running):

```
Build → Build Bundle(s) / APK(s) → Build APK(s)
```

Or via terminal inside the `android/` directory:
```powershell
.\gradlew assembleDebug
```

The APK will be at:
```
android\app\build\outputs\apk\debug\app-debug.apk
```

Transfer this file to your phone and install it (you may need to enable **Install unknown apps** in Settings).

---

## 6. Project Structure

```
android/
├── app/
│   ├── src/main/java/com/gardenapp/
│   │   ├── data/          # API service, Room DB, repositories
│   │   ├── di/            # Hilt dependency injection modules
│   │   ├── ui/            # Compose screens and ViewModels
│   │   │   ├── dashboard/
│   │   │   ├── gardens/
│   │   │   ├── beds/
│   │   │   ├── plants/
│   │   │   ├── tasks/
│   │   │   ├── library/
│   │   │   ├── planner/
│   │   │   └── settings/
│   │   ├── navigation/    # NavGraph and route definitions
│   │   └── GardenApp.kt   # Hilt Application class
│   └── build.gradle.kts   # App-level build config
├── BUILD.md               # This file
├── FEATURE_GAPS.md        # Feature parity checklist vs web app
└── settings.gradle.kts
```

**Key dependencies** (from `app/build.gradle.kts`):
- Compose BOM `2024.09.00` + Material3
- Hilt `2.51.1` for dependency injection
- Retrofit `2.11.0` + OkHttp `4.12.0` for networking
- Room `2.6.1` for local offline caching
- Coil `2.7.0` for image loading
- Paging 3 `3.3.2` for paginated plant library

---

## 7. Staying in Sync with the Web App

The Android app and the React web app (`apps/web/`) should have feature parity. When the web app gets a new feature, it needs to be ported to Android too. See **`FEATURE_GAPS.md`** for the current list of missing features.

Both apps share the same backend — there is no separate Android database. All data lives in `apps/api/instance/garden.db` (SQLite) on the server, accessed via the FastAPI REST API.

---

## Troubleshooting

### Gradle sync fails: "Could not resolve..."
- Go to **File → Settings → Build, Execution, Deployment → Build Tools → Gradle**
- Ensure **Gradle JDK** is set to the bundled JDK 17.
- Try **File → Invalidate Caches / Restart**.

### "Hilt component annotation processor error"
- Run **Build → Clean Project**, then **Build → Rebuild Project**.
- Make sure KSP (not KAPT) is the annotation processor — the project uses `id("com.google.devtools.ksp")`.

### App crashes immediately with "Connection refused"
- The FastAPI backend is not running or not reachable.
- Check the server is up: open a browser and visit `http://10.0.2.2:8000/api/health` from within the emulator (via Chrome in the emulator).
- On a physical device, verify the server URL in Settings points to your machine's IP, not `10.0.2.2`.

### "Cleartext HTTP traffic not permitted"
- Android 9+ blocks plain HTTP by default. The app has a network security config that allows cleartext to the local network.
- If you see this error after changing the server URL, check that `android/app/src/main/res/xml/network_security_config.xml` permits the domain.

### Emulator is slow / unresponsive
- Enable **Hardware acceleration** (HAXM or Hyper-V) in the SDK Manager.
- Use an **x86_64** system image, not ARM64, for best emulator performance on Intel/AMD machines.
