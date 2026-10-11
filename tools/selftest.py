"""Real end-to-end checks against the Atulya server running on this machine.

    python -m atulya.cli selftest            # safe checks
    python -m atulya.cli selftest --actions  # also approve a real PC action (opens and closes Calculator)

Nothing is faked: it talks to the live server over HTTP, the configured cloud/local
model, the local speech models (TTS -> STT round trip), and the real OS. It signs in
by creating a short-lived session directly in data/auth.sqlite3 (only possible on the
host itself) and revokes it at the end.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from dataclasses import dataclass, field

import httpx

from atulya.auth import AuthStore
from atulya.settings import Settings


@dataclass
class Report:
    rows: list[tuple[str, bool, str, float]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str, seconds: float) -> None:
        self.rows.append((name, ok, detail, seconds))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name:<28} {seconds:6.2f}s  {detail}", flush=True)


def _timed(report: Report, name: str, fn) -> object:
    started = time.perf_counter()
    try:
        ok, detail, value = fn()
    except Exception as exc:  # report, never crash the run
        ok, detail, value = False, f"{type(exc).__name__}: {exc}"[:200], None
    report.add(name, ok, detail, time.perf_counter() - started)
    return value


def _stream_chat(client: httpx.Client, text: str, conversation: str) -> tuple[str, list[dict], float | None]:
    started = time.perf_counter()
    first = None
    reply, confirms = "", []
    with client.stream("POST", "/api/chat", json={
        "messages": [{"role": "user", "content": text}], "conversation_id": conversation, "stream": True,
    }, timeout=120) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            if event.get("text"):
                first = first or time.perf_counter() - started
                reply += event["text"]
            if event.get("confirm"):
                confirms.append(event["confirm"])
            if event.get("error"):
                raise RuntimeError(event["error"])
    return reply, confirms, first


def _server_process_stats(port: int) -> str:
    try:
        import psutil
    except ImportError:
        return "psutil missing"
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN and conn.pid:
            proc = psutil.Process(conn.pid)
            children = proc.children(recursive=True)
            rss = sum(p.memory_info().rss for p in [proc, *children]) / 1024 ** 2
            return f"server RSS {rss:.0f} MB incl. {len(children)} child process(es)"
    return "server process not found"


def main(actions: bool = False) -> int:
    settings = Settings.from_environment()
    base = f"http://localhost:{settings.port}"
    store = AuthStore(settings.data_dir)
    token = store.create_session("admin")
    report = Report()
    conversation = f"selftest{int(time.time())}"
    print(f"Atulya self-test against {base}\n")
    try:
        with httpx.Client(base_url=base, cookies={"atulya_session": token}, timeout=60) as client:
            _timed(report, "health", lambda: (
                (r := client.get("/api/health")).status_code == 200 and r.json()["status"] == "ok",
                ", ".join(f"{k}={v}" for k, v in r.json().items() if k.endswith(("ready", "configured"))), None))

            def status():
                client.get(f"/api/status?conversation_id={conversation}")
                time.sleep(1)
                data = client.get(f"/api/status?conversation_id={conversation}").json()
                return "cpu" in data and "memory" in data, f"cpu {data['cpu']['label']} · mem {data['memory']['label']} · telegram {data['telegram']['label']}", None
            _timed(report, "live status panel", status)

            def instant():
                r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "calculate 24*7"}],
                                                   "conversation_id": conversation})
                return r.json().get("text") == "168", f"fast path answered {r.json().get('text')!r}", None
            _timed(report, "fast path (no model)", instant)

            def tools():
                reply, _, first = _stream_chat(client, "What is 17*23, and what's the weather in Delhi right now?", conversation)
                ok = "391" in reply and any(word in reply.lower() for word in ("°c", "temperature", "weather"))
                return ok, f"first token {first or 0:.1f}s · {reply[:90]!r}", None
            _timed(report, "model + 2 tools", tools)

            def memory():
                client.post("/api/chat", json={"messages": [{"role": "user", "content": "remember that my selftest code word is mango"}],
                                               "conversation_id": conversation})
                reply, _, _ = _stream_chat(client, "What is my selftest code word? Check your saved memories.", conversation)
                client.delete(f"/api/memory?conversation_id={conversation}&query=mango")
                return "mango" in reply.lower(), reply[:90], None
            _timed(report, "memory save + recall", memory)

            def voice_round_trip():
                phrase = "Atulya, please set a reminder for the meeting tomorrow."
                wav = client.post("/api/voice/synthesize", json={"text": phrase, "language": "en"}, timeout=120)
                if wav.status_code != 200:
                    return False, f"TTS HTTP {wav.status_code}", None
                heard = client.post("/api/voice/transcribe", files={"audio": ("t.wav", wav.content, "audio/wav")},
                                    data={"language": ""}, timeout=180).json().get("text", "")
                words = {"reminder", "meeting", "tomorrow"}
                hits = sum(word in heard.lower() for word in words)
                return hits >= 2, f"TTS {len(wav.content) // 1024} KB -> STT heard {heard!r}", None
            _timed(report, "speech TTS -> STT (local)", voice_round_trip)

            def briefing():
                r = client.post("/api/briefing", json={"conversation_id": conversation, "force": True}, timeout=180)
                text = r.json().get("text", "")
                return r.status_code == 200 and len(text) > 40, text[:90], None
            _timed(report, "morning briefing", briefing)

            def approval_flow():
                reply, confirms, _ = _stream_chat(client, "Open the Calculator app.", conversation)
                if not confirms:
                    return False, f"no approval requested · {reply[:80]!r}", None
                action = confirms[0]
                if not actions:
                    client.post(f"/api/actions/{action['id']}", json={"approve": False})
                    return True, f"approval requested: {action['summary']} (denied; run with --actions to execute)", None
                result = client.post(f"/api/actions/{action['id']}", json={"approve": True}).json().get("text", "")
                time.sleep(3)
                if platform.system() == "Windows":
                    subprocess.run(["taskkill", "/IM", "CalculatorApp.exe", "/F"], capture_output=True)
                return "Opened" in result, f"{action['summary']} -> {result}", None
            _timed(report, "PC action with approval", approval_flow)

            def telegram():
                token_value = os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN", "").strip()
                if not token_value:
                    return True, "not configured (skipped)", None
                me = httpx.get(f"https://api.telegram.org/bot{token_value}/getMe", timeout=15)
                state = client.get(f"/api/status?conversation_id={conversation}").json()["telegram"]["label"]
                return me.status_code == 200 and state == "Connected", f"bot reachable={me.status_code == 200} · polling: {state}", None
            _timed(report, "telegram", telegram)

            client.delete(f"/api/conversations/{conversation}")
    finally:
        store.revoke_session(token)

    print("\n" + _server_process_stats(settings.port))
    failed = [row for row in report.rows if not row[1]]
    print(f"\n{len(report.rows) - len(failed)}/{len(report.rows)} checks passed.")
    return 1 if failed else 0
