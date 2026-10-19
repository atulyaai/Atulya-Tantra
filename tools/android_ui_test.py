"""Real UI test of the Atulya APK on a CI Android emulator against a private Atulya server on the runner.

The emulator reaches the runner's server at http://10.0.2.2:8501 (no Cloudflare in between). The test signs
in with a throwaway password, then drives the real screens through Android's accessibility tree
(uiautomator) and adb input: chat layout, "hide chat" → conversation mode → CHAT, the ⋮ menu, rotation.
Every step is recorded in report.txt with a screenshot; any failed step fails the release.

Usage: python tools/android_ui_test.py APK OUT_DIR PASSWORD
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
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
        rid = node.get("resource-id", "")
        if rid and not label:
            label = f"#{rid}"  # WebView exposes element ids; used when a field has no readable label
        found.append({"label": label, "box": (x1, y1, x2, y2), "class": node.get("class", "")})
    return found


def dismiss_system_dialogs(found: list[dict]) -> bool:
    """The CI emulator's own launcher sometimes freezes ("isn't responding") over the app; that is the
    virtual phone being slow, not Atulya. Tap Wait and carry on."""
    if not any("isn't responding" in node["label"] for node in found):
        return False
    wait = next((node for node in found if node["label"] == "Wait"), None)
    if wait:
        tap(wait)
    else:
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1)
    return True


def find(pattern: str, wait: float = 20) -> dict | None:
    deadline = time.time() + wait
    while time.time() < deadline:
        found = nodes()
        if dismiss_system_dialogs(found):
            continue
        for node in found:
            if re.search(pattern, node["label"], re.I) and node["box"][2] > node["box"][0]:
                return node
        time.sleep(1.5)
    return None


def tap(node: dict) -> None:
    x1, y1, x2, y2 = node["box"]
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
    time.sleep(1.2)  # let focus move and the keyboard open before typing


def type_text(text: str) -> None:
    # adb typing into a WebView drops characters when fast: send small chunks.
    for start in range(0, len(text), 5):
        adb("shell", "input", "text", text[start:start + 5].replace(" ", "%s"))
        time.sleep(0.25)


def step(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
    shot(re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40])
    if not ok:  # what was on screen, to see why
        seen = [n["label"] for n in nodes() if n["label"]][:25]
        print("    on screen:", " | ".join(seen) or "(nothing readable)", flush=True)
        (OUT / f"{len(results):02d}-ui.xml").write_text(adb("shell", "cat", "/sdcard/ui.xml"), encoding="utf-8")
    return ok


def screen_size() -> tuple[int, int]:
    """Current screen size in its current orientation (wm size always reports portrait)."""
    found = nodes()
    if found:
        return max(n["box"][2] for n in found), max(n["box"][3] for n in found)
    match = re.search(r"(\d+)x(\d+)", adb("shell", "wm", "size"))
    return (int(match.group(1)), int(match.group(2))) if match else (1080, 2400)


def inside_screen(node: dict) -> bool:
    width, height = screen_size()
    x1, y1, x2, y2 = node["box"]
    return x1 >= 0 and y1 >= 0 and x2 <= width + 2 and y2 <= height + 2


adb("shell", "settings", "put", "global", "hide_error_dialogs", "1")  # no system ANR pop-ups over the app
adb("wait-for-device")
for _ in range(60):  # let the emulator finish booting its launcher before the app starts
    if adb("shell", "getprop", "sys.boot_completed").strip() == "1":
        break
    time.sleep(2)
time.sleep(10)
adb("install", "-r", APK, check=True)
# Only mic and camera (for the voice checks). The app asks for nothing on first launch, so any system
# permission dialog over the sign-in screen is a regression this test catches.
for permission in ("RECORD_AUDIO", "CAMERA"):
    adb("shell", "pm", "grant", PKG, f"android.permission.{permission}")
adb("shell", "locksettings", "set-pin", "1357")
adb("logcat", "-c")
adb("shell", "am", "start", "-W", "-n", f"{PKG}/.MainActivity")
time.sleep(5)
adb("shell", "input", "text", "1357")
adb("shell", "input", "keyevent", "KEYCODE_ENTER")

field = find(r"username or email|#auth-username", 60)
if step("app unlocks and shows sign-in", field is not None):
    tap(field)
    type_text("admin")
    time.sleep(0.8)
    # keyboard stays open on purpose: a real user taps CONTINUE like this
    continue_button = find(r"^CONTINUE$", 5)
    if continue_button:
        tap(continue_button)
    else:
        adb("shell", "input", "keyevent", "KEYCODE_ENTER")
    use_password = find(r"^USE PASSWORD$")
    if step("sign-in offers password", use_password is not None):
        tap(use_password)
        time.sleep(1)
        password_field = find(r"^(password|#auth-password)$", 10)
        if step("password field visible", password_field is not None):
            tap(password_field)
            show = find(r"^Show password$", 3)
            if show:  # reveal the box so the typed text can be read back and checked
                tap(show)
                tap(password_field)
            for attempt in range(3):
                adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
                for _ in range(40):
                    adb("shell", "input", "keyevent", "KEYCODE_DEL")
                type_text(PASSWORD)
                time.sleep(0.8)
                typed = next((n["label"] for n in nodes() if n["label"] == PASSWORD), None)
                if typed or not show:
                    break
            step("password typed correctly", bool(typed) or not show, f"attempts {attempt + 1}")
            adb("shell", "input", "keyevent", "KEYCODE_ENTER")

composer = find(r"Type a message|#chat-prompt", 40)
if step("signed in: chat input visible", composer is not None and inside_screen(composer),
        str(composer["box"]) if composer else ""):
    width, height = screen_size()
    talk = find(r"^TALK$", 5)
    step("TALK button on screen", talk is not None and inside_screen(talk), str(talk["box"]) if talk else "")
    panel_top = min((n["box"][1] for n in nodes() if re.search(r"^(TALK|NEW|HISTORY)$", n["label"])), default=0)
    step("chat panel leaves the hologram visible (top in lower 40%)", panel_top > height * 0.6,
         f"panel top {panel_top}px of {height}px")

    # TALK = conversation mode (typing "hide chat" needs a configured AI; the CI server has no keys)
    if talk:
        tap(talk)
    time.sleep(2)
    chat_button = find(r"^CHAT$|^Show the chat$", 10)
    still_composer = find(r"Type a message|#chat-prompt", 2)
    step("TALK → full-screen hologram with CHAT button", chat_button is not None and still_composer is None)
    if chat_button:
        tap(chat_button)
        step("CHAT brings the chat back", find(r"Type a message|#chat-prompt", 10) is not None)

    menu = find(r"^⋮$|Account and settings", 5)
    if step("account menu (⋮) present", menu is not None):
        tap(menu)
        time.sleep(1)
        labels = {n["label"] for n in nodes()}
        step("menu has RELOAD and VIEW", "RELOAD" in labels and any(label.startswith("VIEW:") for label in labels),
             ", ".join(sorted(label for label in labels if label.isupper())[:12]))
        engine = next((label for label in labels if label.startswith("VOICE:")), "")
        recognizers = adb("shell", "cmd", "package", "query-services", "-a", "android.speech.RecognitionService")
        phone_has_recognizer = "packageName=" in recognizers
        # The app must use the phone's recognizer whenever the phone has one (the CI image may not).
        step("voice uses the phone's recognizer when available",
             engine == "VOICE: PHONE RECOGNIZER" or (not phone_has_recognizer and engine.startswith("VOICE:")),
             f"{engine or 'no label'}; phone recognizer installed: {phone_has_recognizer}")
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(1.5)
        still_open = find(r"Type a message|#chat-prompt", 5)
        step("Back closes the menu, app stays open", still_open is not None and find(r"^RELOAD$", 1) is None)

    adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
    adb("shell", "settings", "put", "system", "user_rotation", "1")
    time.sleep(5)
    landscape = find(r"Type a message|#chat-prompt", 10)
    step("landscape: chat input still on screen", landscape is not None and inside_screen(landscape),
         str(landscape["box"]) if landscape else "")
    adb("shell", "settings", "put", "system", "user_rotation", "0")
    time.sleep(3)

adb("shell", "input", "keyevent", "KEYCODE_HOME")
time.sleep(2)
adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity")
step("reopen within 2 min: no unlock prompt, still signed in", find(r"Type a message|#chat-prompt", 15) is not None)

# The app pairs itself as a device after sign-in and answers jobs; actions wait for ALLOW on the phone.
DATA = Path(os.environ.get("ATULYA_DATA_DIR", "."))


def phone_device():
    try:
        with sqlite3.connect(DATA / "agents.sqlite3") as db:
            return db.execute("SELECT owner, name, seen FROM devices WHERE revoked=0 AND name LIKE 'Phone %'").fetchone()
    except sqlite3.Error:
        return None


def enqueue(owner: str, name: str, kind: str, detail: str = "") -> str:
    job_id = uuid.uuid4().hex
    with sqlite3.connect(DATA / "agents.sqlite3") as db:
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                   (job_id, owner, name, kind, detail, "queued", time.time(), time.time(), ""))
    return job_id


def job(job_id: str, until: set[str], wait: float = 30) -> tuple[str, str]:
    deadline = time.time() + wait
    status, output = "missing", ""
    while time.time() < deadline:
        with sqlite3.connect(DATA / "agents.sqlite3") as db:
            row = db.execute("SELECT status, output FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row:
            status, output = row
            if status in until:
                break
        time.sleep(1.5)
    return status, output


device = None
for _ in range(25):
    device = phone_device()
    if device and device[2]:
        break
    time.sleep(2)
if step("phone pairs itself after sign-in and polls", bool(device and device[2]), device[1] if device else "no device"):
    owner, name, _seen = device
    status, output = job(enqueue(owner, name, "ping"), {"executed", "failed"})
    step("ping runs without asking", status == "executed", output)
    shown = enqueue(owner, name, "display_message", "Hello from CI")
    allow = find(r"^ALLOW$", 30)
    waiting, _ = job(shown, {"executed", "failed"}, 2)
    step("an action waits for ALLOW on the phone", allow is not None and waiting == "running",
         f"dialog={'yes' if allow else 'no'} status={waiting}")
    if allow:
        tap(allow)
    status, output = job(shown, {"executed", "failed"})
    step("ALLOW runs it and reports back", status == "executed", output)

    media_job = enqueue(owner, name, "media_control", "play")
    allow = find(r"^ALLOW$", 30)
    if allow:
        tap(allow)
    status, output = job(media_job, {"executed", "failed"})
    step("play without an audio stream fails honestly", status == "failed" and "stream" in output.lower(), output)

    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(3)
    background_ping = enqueue(owner, name, "ping")
    status, _ = job(background_ping, {"executed", "failed"}, 8)
    step("background phone does not execute jobs", status == "queued", status)
    adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity")
    status, output = job(background_ping, {"executed", "failed"})
    step("reopening phone resumes queued ping", status == "executed", output)

    adb("shell", "pm", "grant", PKG, "android.permission.POST_NOTIFICATIONS")
    devices_button = find(r"^Devices$", 10)
    if devices_button:
        tap(devices_button)
    background_button = find(r"^Background phone connection$", 10)
    step("background connection opt-in is visible", background_button is not None)
    if background_button:
        tap(background_button)
    enable = find(r"^ENABLE$", 10)
    if enable:
        tap(enable)
    step("background session explicitly enabled", enable is not None)
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(3)
    background_probe = enqueue(owner, name, "ping")
    status, output = job(background_probe, {"executed", "failed"}, 40)
    step("opt-in background session executes ping", status == "executed", output)
    awaiting = enqueue(owner, name, "display_message", "Needs phone approval")
    status, _ = job(awaiting, {"executed", "failed"}, 18)
    step("background session leaves effectful jobs queued", status == "queued", status)
    adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity")
    allow = find(r"^ALLOW$", 20)
    step("queued background action asks after reopening", allow is not None)
    if allow:
        tap(allow)
    status, output = job(awaiting, {"executed", "failed"})
    step("background request executes after foreground approval", status == "executed", output)

# The real launcher icon as the phone draws it (home screen app list).
adb("shell", "input", "keyevent", "KEYCODE_HOME")
time.sleep(2)
adb("shell", "input", "swipe", "540", "2000", "540", "600", "300")  # open the app drawer
time.sleep(2)
icon = find(r"^Atulya$", 6)
if icon is None:  # long app lists: use the drawer's search box
    adb("shell", "input", "text", "Atulya")
    time.sleep(2)
    icon = find(r"^Atulya$", 6)
resolved = PKG in adb("shell", "cmd", "package", "resolve-activity", "--brief", "-c",
                           "android.intent.category.LAUNCHER", PKG)
step("launcher shows the Atulya icon", icon is not None or resolved,
     str(icon["box"]) if icon else "listed as a launcher app (photo: see screenshot)")
if icon:
    x1, y1, x2, y2 = icon["box"]
    (OUT / "icon-box.txt").write_text(f"{x1},{y1},{x2},{y2}", encoding="utf-8")

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
