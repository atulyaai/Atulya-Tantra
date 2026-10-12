#!/usr/bin/env sh
# Real-device smoke test of the release APK on a CI Android emulator (R8-shrunk build, same signing key).
# Installs, launches, waits for the site to load, rotates, backgrounds/resumes, and fails on any crash.
set -u
APK="$1"; OUT="$2"; PKG=com.atulvij.atulya
mkdir -p "$OUT"
adb install -r "$APK" || exit 1
adb shell pm grant "$PKG" android.permission.RECORD_AUDIO
adb shell pm grant "$PKG" android.permission.CAMERA
adb shell locksettings set-pin 1357 >/dev/null  # the app refuses to run without a screen lock
adb logcat -c
adb shell am start -W -n "$PKG/.MainActivity" | tee "$OUT/launch.txt"
sleep 6
adb exec-out screencap -p > "$OUT/0-unlock-prompt.png"
adb shell input text 1357
adb shell input keyevent KEYCODE_ENTER
sleep 25
adb exec-out screencap -p > "$OUT/1-portrait.png"
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 && adb pull /sdcard/ui.xml "$OUT/ui-portrait.xml" >/dev/null
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 1
sleep 6
adb exec-out screencap -p > "$OUT/2-landscape.png"
adb shell settings put system user_rotation 0
sleep 4
adb shell input keyevent KEYCODE_HOME
sleep 3
adb shell am start -n "$PKG/.MainActivity" >/dev/null
sleep 6  # within the 2-minute grace period: must NOT ask to unlock again
adb exec-out screencap -p > "$OUT/3-resumed.png"
adb shell am start -W -a android.intent.action.VIEW -d "https://atulya.atulvij.com/" "$PKG" >/dev/null
sleep 6
adb exec-out screencap -p > "$OUT/4-applink.png"
adb shell dumpsys package "$PKG" | grep -E "versionName|versionCode" | head -2 | tee "$OUT/version.txt"
adb shell dumpsys meminfo "$PKG" | grep -E "TOTAL PSS|TOTAL:" | head -1 | tee "$OUT/memory.txt"
adb logcat -d > "$OUT/logcat.txt"
grep -E "chromium.*(Uncaught|Error)" "$OUT/logcat.txt" | head -20 > "$OUT/web-errors.txt" || true
if grep -qE "FATAL EXCEPTION|ANR in $PKG" "$OUT/logcat.txt"; then
  echo "CRASH:"; grep -A20 -E "FATAL EXCEPTION|ANR in" "$OUT/logcat.txt" | head -60; exit 1
fi
adb shell pidof "$PKG" >/dev/null || { echo "app is not running after the test"; exit 1; }
echo "smoke test passed; web console errors: $(wc -l < "$OUT/web-errors.txt")"
