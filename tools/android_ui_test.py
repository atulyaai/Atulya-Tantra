"""Real UI test of the Atulya APK on a CI Android emulator against a private Atulya server on the runner.

The emulator reaches the runner's server at http://10.0.2.2:8501 (no Cloudflare in between). The test signs
in with a throwaway password, then drives the real screens through Android's accessibility tree
(uiautomator) and adb input: chat layout, "hide chat" → conversation mode → CHAT, the ⋮ menu, rotation.
Every step is recorded in report.txt with a screenshot; any failed step fails the release.

Usage: python tools/android_ui_test.py APK OUT_DIR PASSWORD
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PKG = "com.atulvij.atulya"
APK, OUT, PASSWORD = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
results: list[tuple[str, bool, str]] = []


def adb(*args: str, check: bool = False) -> str:
    done = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=120)
    if check and done.returncode:
        raise RuntimeError(f"adb {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def shot(name: str) -> None:
    with (OUT / f"{len(results):02d}-{name}.png").open("wb") as handle:
        subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=handle, timeout=60)


def nodes() -> list[dict]:
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    raw = adb("shell", "cat", "/sdcard/ui.xml")
    try:
        root = ET.fromstring(raw[raw.find("<"):])
    except ET.ParseError:
        return []
    found = []
    for node in root.iter("node"):
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if not match:
            continue
        x1, y1, x2, y2 = map(int, match.groups())
        label = " ".join(filter(None, (node.get("text"), node.get("content-desc"), node.get("hint")))).strip()
        found.append({"label": label, "box": (x1, y1, x2, y2), "class": node.get("class", "")})
    return found


def find(pattern: str, wait: float = 20) -> dict | None:
    deadline = time.time() + wait
    while time.time() < deadline:
        for node in nodes():
            if re.search(pattern, node["label"], re.I) and node["box"][2] > node["box"][0]:
                return node
        time.sleep(1.5)
    return None


def tap(node: dict) -> None:
    x1, y1, x2, y2 = node["box"]
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


def type_text(text: str) -> None:
    adb("shell", "input", "text", text.replace(" ", "%s"))


def step(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
    shot(name.replace(" ", "-").lower()[:40])
    return ok


def screen_size() -> tuple[int, int]:
    match = re.search(r"(\d+)x(\d+)", adb("shell", "wm", "size"))
    return (int(match.group(1)), int(match.group(2))) if match else (1080, 2400)


def inside_screen(node: dict) -> bool:
    width, height = screen_size()
    x1, y1, x2, y2 = node["box"]
    return x1 >= 0 and y1 >= 0 and x2 <= width + 2 and y2 <= height + 2


adb("install", "-r", APK, check=True)
for permission in ("RECORD_AUDIO", "CAMERA"):
    adb("shell", "pm", "grant", PKG, f"android.permission.{permission}")
adb("shell", "locksettings", "set-pin", "1357")
adb("logcat", "-c")
adb("shell", "am", "start", "-W", "-n", f"{PKG}/.MainActivity")
time.sleep(5)
adb("shell", "input", "text", "1357")
adb("shell", "input", "keyevent", "KEYCODE_ENTER")

field = find(r"username or email", 60)
if step("app unlocks and shows sign-in", field is not None):
    tap(field)
    type_text("admin")
    adb("shell", "input", "keyevent", "KEYCODE_ENTER")
    use_password = find(r"^USE PASSWORD$")
    if step("sign-in offers password", use_password is not None):
        tap(use_password)
        time.sleep(1)
        password_field = next((n for n in nodes() if re.fullmatch(r"password", n["label"], re.I)), None)
        if step("password field visible", password_field is not None):
            tap(password_field)
            type_text(PASSWORD)
            adb("shell", "input", "keyevent", "KEYCODE_ENTER")

composer = find(r"Type a message", 40)
if step("signed in: chat input visible", composer is not None and inside_screen(composer),
        str(composer["box"]) if composer else ""):
    width, height = screen_size()
    talk = find(r"^TALK$", 5)
    step("TALK button on screen", talk is not None and inside_screen(talk), str(talk["box"]) if talk else "")
    panel_top = min((n["box"][1] for n in nodes() if re.search(r"^(TALK|NEW|HISTORY)$", n["label"])), default=0)
    step("chat panel leaves the hologram visible (top in lower 40%)", panel_top > height * 0.6,
         f"panel top {panel_top}px of {height}px")

    tap(composer)
    type_text("hide chat")
    adb("shell", "input", "keyevent", "KEYCODE_ENTER")
    time.sleep(2)
    chat_button = find(r"^CHAT$", 10)
    still_composer = find(r"Type a message", 2)
    step("'hide chat' → full-screen hologram with CHAT button", chat_button is not None and still_composer is None)
    if chat_button:
        tap(chat_button)
        step("CHAT brings the chat back", find(r"Type a message", 10) is not None)

    menu = find(r"^⋮$|Account and settings", 5)
    if step("account menu (⋮) present", menu is not None):
        tap(menu)
        time.sleep(1)
        labels = {n["label"] for n in nodes()}
        step("menu has RELOAD and VIEW", "RELOAD" in labels and any(label.startswith("VIEW:") for label in labels),
             ", ".join(sorted(label for label in labels if label.isupper())[:12]))
        adb("shell", "input", "keyevent", "KEYCODE_BACK")

    adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
    adb("shell", "settings", "put", "system", "user_rotation", "1")
    time.sleep(5)
    landscape = find(r"Type a message", 10)
    step("landscape: chat input still on screen", landscape is not None and inside_screen(landscape))
    adb("shell", "settings", "put", "system", "user_rotation", "0")
    time.sleep(3)

adb("shell", "input", "keyevent", "KEYCODE_HOME")
time.sleep(2)
adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity")
step("reopen within 2 min: no unlock prompt, still signed in", find(r"Type a message", 15) is not None)

log = adb("logcat", "-d")
(OUT / "logcat.txt").write_text(log, encoding="utf-8")
crashed = re.search(rf"FATAL EXCEPTION|ANR in {re.escape(PKG)}", log)
step("no crash or freeze", crashed is None)
memory = re.search(r"TOTAL PSS:\s+(\d+)", adb("shell", "dumpsys", "meminfo", PKG))
step("memory under 250 MB", memory is not None and int(memory.group(1)) < 250_000,
     f"{int(memory.group(1)) // 1024} MB" if memory else "")

report = "\n".join(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}" for name, ok, detail in results)
(OUT / "report.txt").write_text(report + "\n", encoding="utf-8")
failed = [name for name, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} UI checks passed")
sys.exit(1 if failed else 0)
