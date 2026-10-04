"""Learning about the user — facts, habits and approval preferences.

Atulya remembered conversations but never built a picture of *you*. Each user
now has a small profile (``ATULYA_PROFILE_DIR/<user>.json``, local only):

* **Facts** from what you tell it: your name, people ("my wife's name is
  Priya"), where you live and work, likes and dislikes, allergies, birthdays and
  anything you ask it to "remember that …". Understood by patterns, not guessed
  by a model, so a passing remark isn't mistaken for a fact. "What do you know
  about me?" shows everything; "forget …" removes it.
* **Habits** from what you do: an action you take on at least three different
  days around the same hour ("turn on the kitchen light around 7 AM") becomes a
  habit. Habits are shared with the brain as context and can prompt a gentle
  "you usually … around now" notification.
* **Approvals**: after you say yes to the same confirmation five times in a row,
  Atulya offers to stop asking. It only stops if you agree, only for you, and
  only for everyday risks (a door, an email to a person, deleting a reminder or
  event) — running code or changing files always asks. Revoke in the UI or say
  "always ask me first".
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from atulya.raksha import vault

logger = logging.getLogger(__name__)

LEARN_AFTER = 5  # consecutive approvals before offering to stop asking
REOFFER_AFTER_SECONDS = 7 * 86400
HABIT_MIN_DAYS = 3
HABIT_SHARE = 0.6  # share of occurrences within ±1 hour of the usual time
MAX_FACTS = 200
# Confirmations a user may choose to stop answering. Code execution and file
# changes are never learnable.
LEARNABLE_TOOLS = {"home_control", "send_email", "cancel_reminder", "calendar_remove"}
# Where habits come from: things the user did, not what automations did.
USER_SOURCES = {"chat", "voice", "ambient", "live"}
_HABIT_TOOLS = {"home_control", "get_weather", "get_forecast", "calendar_list", "fetch_emails", "current_time"}

_RELATIONS = ("wife|husband|partner|son|daughter|mother|mom|mum|father|dad|brother|sister|boss|manager|friend"
              "|best friend|girlfriend|boyfriend|grandmother|grandma|grandfather|grandpa|uncle|aunt|cousin"
              "|doctor|dog|cat|baby|kid|child|assistant|colleague|neighbour|neighbor")
_STOP_VALUE = {"it", "that", "this", "them", "you", "him", "her", "so", "too", "very", "not", "a", "an", "the"}
_QUESTION_START = ("what", "how", "why", "when", "where", "who", "which", "do ", "does ", "did ", "is ", "are ", "can ",
                   "could ", "would ", "should ", "will ")
_VALUE = r"([a-z0-9][\w' .&-]{0,60}?)"
_END = r"\s*(?:[.,!?;]|\band\b|\bbut\b|\bas\b|\bsince\b|\bbecause\b|$)"


def _clean_value(value: str) -> str:
    words = value.strip(" .,'\"").split()
    return " ".join(words[:6])


def _title(value: str) -> str:
    """Capitalise a name the user typed in lower case; keep their own casing otherwise."""
    if any(c.isupper() for c in value):
        return value
    return " ".join(w[:1].upper() + w[1:] for w in value.split())


def _second_person(text: str) -> str:
    swap = {"i": "you", "me": "you", "my": "your", "mine": "yours", "am": "are", "i'm": "you're", "im": "you're",
            "myself": "yourself", "we": "you", "our": "your"}
    return " ".join(swap.get(w.lower(), w) for w in text.split())


def extract_facts(text: str) -> list[dict[str, str]]:
    """Facts the user stated about themselves (empty for questions and requests)."""
    raw = (text or "").strip()
    t = raw.lower().strip()
    if not t or t.endswith("?") or t.startswith(_QUESTION_START):
        return []
    facts: list[dict[str, str]] = []
    same_len = len(raw) == len(t)

    def grab(m: re.Match, group: int) -> str:
        """The matched words as the user wrote them (patterns run on lower case)."""
        if m.group(group) is None:
            return ""
        return raw[m.start(group):m.end(group)] if same_len else m.group(group)

    def add(kind: str, key: str, value: str) -> None:
        value = _clean_value(value)
        if value and value.lower() not in _STOP_VALUE:
            facts.append({"kind": kind, "key": key, "value": value})

    for m in re.finditer(r"\b(?:my name is|call me|i am called|i'm called)\s+" + _VALUE + _END, t):
        add("name", "name", _title(grab(m, 1)))
    for m in re.finditer(rf"\bmy ({_RELATIONS})(?:'s name is|s name is| name is| is called| is named)\s+" + _VALUE
                         + _END, t):
        add("person", m.group(1), _title(grab(m, 2)))
    # "my wife is Priya" — only a capitalised name, so "my wife is angry" isn't a fact.
    for m in re.finditer(rf"\bmy ({_RELATIONS}) is ([A-Z][\w'-]+(?: [A-Z][\w'-]+)?)\b", raw, flags=re.IGNORECASE):
        name = m.group(2)
        start = raw.find(name, m.start(2))
        if start >= 0 and raw[start].isupper() and not any(f["kind"] == "person" and f["key"] == m.group(1).lower()
                                                           for f in facts):
            add("person", m.group(1).lower(), name)
    for m in re.finditer(rf"\b([A-Z][\w'-]+) is my ({_RELATIONS})\b", raw, flags=re.IGNORECASE):
        if raw[m.start(1)].isupper():
            add("person", m.group(2).lower(), m.group(1))
    for m in re.finditer(r"\bi live in\s+" + _VALUE + _END, t):
        add("place", "home", _title(grab(m, 1)))
    for m in re.finditer(r"\bi(?:'m| am) from\s+" + _VALUE + _END, t):
        add("place", "hometown", _title(grab(m, 1)))
    for m in re.finditer(r"\bi work (?:at|for)\s+" + _VALUE + _END, t):
        add("work", "workplace", _title(grab(m, 1)))
    for m in re.finditer(r"\bi work (?:.{1,40}? )?as (?:an? )?" + _VALUE + _END, t):
        add("work", "job", grab(m, 1))
    for m in re.finditer(r"\bmy birthday is (?:on )?" + _VALUE + _END, t):
        add("date", "birthday", _title(grab(m, 1)))
    for m in re.finditer(r"\bi(?:'m| am) allergic to\s+" + _VALUE + _END, t):
        add("health", "allergy", grab(m, 1))
    for m in re.finditer(r"\bmy favou?rite ([a-z ]{2,20}?) is\s+" + _VALUE + _END, t):
        add("preference", f"favorite {m.group(1).strip()}", grab(m, 2))
    for m in re.finditer(r"\bi (?:really |truly )?(?:like|love|enjoy|prefer)\s+" + _VALUE + _END, t):
        add("preference", "likes", grab(m, 1))
    for m in re.finditer(r"\bi (?:don't|do not|really don't) (?:like|enjoy)\s+" + _VALUE + _END
                         + r"|\bi (?:hate|dislike|can't stand)\s+" + _VALUE + _END, t):
        add("preference", "dislikes", grab(m, 1) or grab(m, 2))
    m = re.search(r"^(?:please )?remember (?:that |this: |: )?((?:i|my|i'm|we|our)\b.{2,160})$", t)
    if m:
        facts.append({"kind": "note", "key": "note", "value": _second_person(grab(m, 1).strip(" ."))})
    # A "don't like" statement also matched "like": keep the dislike only.
    dislikes = {f["value"] for f in facts if f["key"] == "dislikes"}
    return [f for f in facts if not (f["key"] == "likes" and any(f["value"].endswith(d) or d.endswith(f["value"])
                                                                   for d in dislikes))]


def describe_fact(fact: dict[str, Any]) -> str:
    kind, key, value = fact.get("kind"), str(fact.get("key", "")), str(fact.get("value", ""))
    if kind == "name":
        return f"your name is {value}"
    if kind == "person":
        return f"your {key} is {value}"
    if key == "home":
        return f"you live in {value}"
    if key == "hometown":
        return f"you're from {value}"
    if key == "workplace":
        return f"you work at {value}"
    if key == "job":
        return f"you work as {value}"
    if key == "birthday":
        return f"your birthday is {value}"
    if key == "allergy":
        return f"you're allergic to {value}"
    if key == "likes":
        return f"you like {value}"
    if key == "dislikes":
        return f"you don't like {value}"
    if key.startswith("favorite "):
        return f"your {key} is {value}"
    return value


def approval_key(tool: str, arguments: dict[str, Any] | None) -> str:
    """What "the same confirmation" means: this device + action, this recipient…"""
    args = arguments or {}
    if tool == "home_control":
        return f"home_control:{str(args.get('action', '')).lower()}:{args.get('device_id', '')}"
    if tool == "send_email":
        return f"send_email:{str(args.get('to', '')).strip().lower()}"
    return tool


def _habit_signature(tool: str, arguments: dict[str, Any]) -> str | None:
    if tool not in _HABIT_TOOLS:
        return None
    keep = {k: v for k, v in sorted(arguments.items()) if k in ("device_id", "action", "value", "location")}
    return f"{tool}:{json.dumps(keep, sort_keys=True)}"


def _hour_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12} {suffix}"


class ProfileStore:
    """Per-user profiles as JSON files; thread-safe read-modify-write."""

    def __init__(self, directory: str | Path | None = None):
        self.dir = Path(directory or os.environ.get("ATULYA_PROFILE_DIR", "kosh/agent/profiles"))
        self._lock = threading.RLock()

    # ── storage ────────────────────────────────────────────────────────────
    def _path(self, user: str) -> Path:
        return self.dir / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', user or 'default')[:64]}.json"

    def load(self, user: str) -> dict[str, Any]:
        with self._lock:
            try:
                data = json.loads(vault.read_text(self._path(user)))
            except (OSError, json.JSONDecodeError):
                data = {}
        data.setdefault("user", user)
        for key, empty in (("facts", []), ("habits", {}), ("approvals", {}), ("trusted", [])):
            if not isinstance(data.get(key), type(empty)):
                data[key] = empty
        return data

    def _save(self, user: str, data: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        vault.write_text(self._path(user), json.dumps(data, indent=2, ensure_ascii=False))

    def users(self) -> list[str]:
        if not self.dir.exists():
            return []
        return [p.stem for p in self.dir.glob("*.json")]

    # ── facts ──────────────────────────────────────────────────────────────
    def remember(self, user: str, facts: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Store facts; a new value replaces the old one for single-valued keys."""
        stored: list[dict[str, Any]] = []
        with self._lock:
            data = self.load(user)
            for fact in facts:
                multi = fact["key"] in ("likes", "dislikes", "note", "allergy")
                data["facts"] = [
                    f for f in data["facts"]
                    if not (f.get("key") == fact["key"] and (not multi or f.get("value", "").lower() == fact["value"].lower()))
                ]
                # A new like replaces an old dislike of the same thing (and vice versa).
                if fact["key"] in ("likes", "dislikes"):
                    data["facts"] = [f for f in data["facts"]
                                     if not (f.get("key") in ("likes", "dislikes")
                                             and f.get("value", "").lower() == fact["value"].lower())]
                entry = {**fact, "id": f"f_{uuid.uuid4().hex[:8]}", "at": time.time()}
                data["facts"].append(entry)
                stored.append(entry)
            data["facts"] = data["facts"][-MAX_FACTS:]
            self._save(user, data)
        return stored

    def forget(self, user: str, query: str = "", fact_id: str = "") -> list[dict[str, Any]]:
        """Remove facts by id, or those mentioned in ``query`` ("my wife", "coffee")."""
        with self._lock:
            data = self.load(user)
            words = {w for w in re.findall(r"[a-z0-9']+", query.lower()) if len(w) > 2} - {
                "that", "the", "about", "you", "your", "know", "forget", "please", "like", "likes", "and"}
            removed, kept = [], []
            for f in data["facts"]:
                haystack = f"{f.get('key', '')} {f.get('value', '')}".lower()
                hit = f.get("id") == fact_id if fact_id else bool(words) and any(w in haystack for w in words)
                (removed if hit else kept).append(f)
            data["facts"] = kept
            self._save(user, data)
        return removed

    def forget_everything(self, user: str) -> None:
        with self._lock:
            self._save(user, {"user": user, "facts": [], "habits": {}, "approvals": {}, "trusted": []})

    # ── habits ─────────────────────────────────────────────────────────────
    def record_action(self, user: str, tool: str, arguments: dict[str, Any], label: str,
                      now: float | None = None) -> None:
        signature = _habit_signature(tool, arguments or {})
        if not signature:
            return
        now = time.time() if now is None else now
        local = time.localtime(now)
        day = time.strftime("%Y-%m-%d", local)
        with self._lock:
            data = self.load(user)
            habit = data["habits"].setdefault(signature, {"label": label, "tool": tool, "arguments": arguments,
                                                          "hours": {}, "days": [], "count": 0})
            habit["label"] = label
            habit["count"] = int(habit.get("count", 0)) + 1
            hours = habit.setdefault("hours", {})
            hours[str(local.tm_hour)] = int(hours.get(str(local.tm_hour), 0)) + 1
            if day not in habit.setdefault("days", []):
                habit["days"] = [*habit["days"], day][-30:]
            habit["last"] = now
            self._save(user, data)

    @staticmethod
    def _usual_hour(habit: dict[str, Any]) -> int | None:
        if len(habit.get("days") or []) < HABIT_MIN_DAYS:
            return None
        hours = Counter({int(h): int(n) for h, n in (habit.get("hours") or {}).items()})
        total = sum(hours.values())
        if not total:
            return None
        best, best_share = None, 0.0
        for hour in hours:
            near = sum(hours.get((hour + d) % 24, 0) for d in (-1, 0, 1))
            share = near / total
            if share > best_share or (share == best_share and best is not None and hours[hour] > hours[best]):
                best, best_share = hour, share
        return best if best_share >= HABIT_SHARE else None

    def habits(self, user: str) -> list[dict[str, Any]]:
        found = []
        for signature, habit in self.load(user)["habits"].items():
            hour = self._usual_hour(habit)
            if hour is not None:
                found.append({"signature": signature, "label": habit.get("label", ""), "hour": hour,
                              "when": f"around {_hour_label(hour)}", "days": len(habit.get("days") or []),
                              "count": habit.get("count", 0), "tool": habit.get("tool"),
                              "arguments": habit.get("arguments") or {}})
        return sorted(found, key=lambda h: h["hour"])

    def due_habits(self, user: str, now: float | None = None) -> list[dict[str, Any]]:
        """Habits usually done in this hour that haven't happened (or been suggested) today."""
        now = time.time() if now is None else now
        local = time.localtime(now)
        today = time.strftime("%Y-%m-%d", local)
        due = []
        with self._lock:
            data = self.load(user)
            for habit in self.habits(user):
                stored = data["habits"].get(habit["signature"], {})
                if habit["hour"] != local.tm_hour or today in (stored.get("days") or []):
                    continue
                if stored.get("suggested_on") == today:
                    continue
                stored["suggested_on"] = today
                due.append(habit)
            if due:
                self._save(user, data)
        return due

    # ── approvals ──────────────────────────────────────────────────────────
    def record_approval(self, user: str, key: str, label: str, approved: bool) -> dict[str, Any]:
        with self._lock:
            data = self.load(user)
            entry = data["approvals"].setdefault(key, {"label": label, "approved": 0, "declined": 0, "streak": 0})
            entry["label"] = label
            if approved:
                entry["approved"] = int(entry.get("approved", 0)) + 1
                entry["streak"] = int(entry.get("streak", 0)) + 1
            else:
                entry["declined"] = int(entry.get("declined", 0)) + 1
                entry["streak"] = 0
            entry["last"] = time.time()
            self._save(user, data)
            return dict(entry)

    def should_offer_trust(self, user: str, key: str) -> bool:
        if key.split(":", 1)[0] not in LEARNABLE_TOOLS:
            return False
        data = self.load(user)
        entry = data["approvals"].get(key) or {}
        if key in data["trusted"] or int(entry.get("streak", 0)) < LEARN_AFTER:
            return False
        return time.time() - float(entry.get("offered_at", 0)) > REOFFER_AFTER_SECONDS

    def mark_offered(self, user: str, key: str) -> None:
        with self._lock:
            data = self.load(user)
            data["approvals"].setdefault(key, {})["offered_at"] = time.time()
            self._save(user, data)

    def trust(self, user: str, key: str) -> bool:
        if key.split(":", 1)[0] not in LEARNABLE_TOOLS:
            return False
        with self._lock:
            data = self.load(user)
            if key not in data["trusted"]:
                data["trusted"].append(key)
            self._save(user, data)
        return True

    def untrust(self, user: str, key: str | None = None) -> list[str]:
        """Start asking again — for one action, or for everything when key is None."""
        with self._lock:
            data = self.load(user)
            removed = [k for k in data["trusted"] if key is None or k == key]
            data["trusted"] = [k for k in data["trusted"] if k not in removed]
            for k in removed:  # start the count again
                data["approvals"].setdefault(k, {})["streak"] = 0
            self._save(user, data)
        return removed

    def is_trusted(self, user: str, tool: str, arguments: dict[str, Any] | None) -> bool:
        return approval_key(tool, arguments) in self.load(user)["trusted"]

    # ── views ──────────────────────────────────────────────────────────────
    def summary_lines(self, user: str) -> list[str]:
        data = self.load(user)
        lines = [describe_fact(f)[:1].upper() + describe_fact(f)[1:] for f in data["facts"]]
        lines += [f"You usually {h['label']} {h['when']}" for h in self.habits(user)]
        trusted = [data["approvals"].get(k, {}).get("label") or k for k in data["trusted"]]
        if trusted:
            lines.append("I don't ask before I " + ", ".join(trusted))
        return lines

    def context_for(self, user: str) -> str:
        """A short "about the user" block for the brain's system prompt."""
        data = self.load(user)
        lines = [describe_fact(f) for f in data["facts"][-25:]]
        lines += [f"usually {h['label']} {h['when']}" for h in self.habits(user)[:8]]
        if not lines:
            return ""
        return "What you know about the user (use it naturally, don't recite it):\n" + "\n".join(
            f"- {line}" for line in lines)

    def view(self, user: str) -> dict[str, Any]:
        data = self.load(user)
        return {
            "user": user,
            "facts": [{**f, "text": describe_fact(f)} for f in data["facts"]],
            "habits": self.habits(user),
            "approvals": [{"key": k, **v, "trusted": k in data["trusted"],
                           "learnable": k.split(":", 1)[0] in LEARNABLE_TOOLS}
                          for k, v in data["approvals"].items()],
            "trusted": list(data["trusted"]),
            "learn_after": LEARN_AFTER,
        }


# ── what the user asks about their profile ────────────────────────────────
_ABOUT_ME_RE = re.compile(r"\bwhat (?:do|else do) you (?:know|remember) about me\b|\bwhat have you learn(?:ed|t) about me\b"
                          r"|\btell me (?:what you know )?about myself\b|\bwhat do you know of me\b")
_FORGET_ALL_RE = re.compile(r"^(?:please )?forget (?:everything|all)(?: (?:you know|you've learned|about me|that you know))*"
                            r"(?: about me)?$")
_FORGET_RE = re.compile(r"^(?:please )?forget (?:that |about )?(.+)$")
_ALWAYS_ASK_RE = re.compile(r"\b(?:always ask(?: me)?(?: first| before)?|start asking (?:me )?again|ask me (?:first|every time))\b")


def profile_intent(text: str) -> tuple[str, str] | None:
    """('about', '') / ('forget_all', '') / ('forget', what) / ('always_ask', '') or None."""
    t = " ".join(re.sub(r"[^\w\s']", " ", (text or "").lower()).split())
    if not t:
        return None
    if _ABOUT_ME_RE.search(t):
        return ("about", "")
    if _FORGET_ALL_RE.match(t):
        return ("forget_all", "")
    m = _FORGET_RE.match(t)
    if m and not m.group(1).startswith(("it", "to ")):
        return ("forget", m.group(1))
    if _ALWAYS_ASK_RE.search(t):
        return ("always_ask", "")
    return None


_REQUEST_RE = re.compile(r"\b(?:what|how|why|when|where|can you|could you|would you|tell me|turn|switch|set|remind"
                         r"|check|show|play|find|search|book|send)\b")


def is_pure_statement(text: str) -> bool:
    """A short sentence that only tells Atulya something about the user — so it
    can simply acknowledge it. "I live in Delhi, what's the weather?" isn't."""
    t = (text or "").strip().lower()
    return (len(t.split()) <= 14 and "?" not in t and not _REQUEST_RE.search(t)
            and t.startswith(("my ", "i ", "i'm ", "im ", "call me", "remember", "please remember")))


async def watch_habits(store: ProfileStore, events: Any, interval: float = 300.0) -> None:
    """Publish ``habit.due`` when a user's usual action hasn't happened yet today."""
    while True:
        try:
            for user in store.users():
                for habit in store.due_habits(user):
                    await events.emit("habit.due", {"user": user, "label": habit["label"], "when": habit["when"],
                                                    "days": habit["days"]})
        except Exception as exc:  # noqa: BLE001 - never let the watcher die
            logger.debug("habit watch failed: %s", exc)
        await asyncio.sleep(interval)
