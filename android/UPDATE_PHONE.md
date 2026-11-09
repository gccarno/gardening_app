# Updating the app on your phone

The app (`com.gardenapp`) talks to the Render backend by default, so no LAN setup is needed.
Use the release build: it is minified (smaller, faster) and signed with the debug key, so it
installs straight over an existing debug install. `assembleDebug` still works for quick iteration.

## One-time phone setup
1. Settings > About phone > tap *Build number* 7 times to enable Developer options.
2. Developer options > turn on *USB debugging*.
3. Plug in the cable and accept the "Allow USB debugging?" prompt.

## Update (PowerShell)
```powershell
cd C:\Users\gccar\Documents\gardening\garden_app\gardening_app\android
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
.\gradlew assembleRelease --console=plain
$adb = 'C:\Users\gccar\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $adb devices        # the phone should be listed as "device"
& $adb install -r app\build\outputs\apk\release\app-release.apk
```
`-r` keeps your local data and replaces the old version.

## If the install fails
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE`: the old app was signed with a different key. Run
  `& $adb uninstall com.gardenapp`, then install again. Server data is safe; only the
  local cache and app settings are cleared.
- `unauthorized` in `adb devices`: unlock the phone and accept the USB debugging prompt.

## No cable
- **Wireless debugging (Android 11+)**: Developer options > *Wireless debugging* > *Pair device with
  pairing code*, then `& $adb pair <ip:pairport>`, `& $adb connect <ip:port>`, and the same
  `install -r` command.
- **Copy the APK**: send `app-release.apk` to the phone (Drive, email) and open it. This needs
  *Install unknown apps* enabled for the app you open it from.
