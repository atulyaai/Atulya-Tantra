"""Buddhi (बुद्धि, intellect): the one pipeline every request goes through (perceive, understand, decide, act, remember, react), with routines, triggers and what Atulya learns about you."""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import Counter, OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from atulya import mastishk as safety
from atulya import raksha as vault
from atulya.adhar import Event, EventBus, default_bus
from atulya.bhava import access_of, acting_as, current_access, current_user
from atulya.kriya import _match_device, route_intent
from atulya.mastishk import EXCLUDED_FROM_BRAIN, AtulyaLLM, LLMEvent, LLMResponse, _chunk_text, get_default_llm

# ── yojana ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

PLAN_TOOL = "run_plan"
MAX_STEPS = 12
_DEFAULT_ROUTINES_FILE = "kosh/agent/routines.json"

DEFAULT_ROUTINES: list[dict[str, Any]] = [
    {
        "id": "rtn_guests",
        "name": "Guests are coming",
        "phrases": ["ready for guests", "guests are coming", "guests coming", "guests are here",
                    "guests are arriving", "having guests", "company is coming", "visitors are coming"],
        "steps": ["turn on the living room light", "turn on the kitchen light", "set the thermostat to 22"],
        "enabled": True,
    },
    {
        "id": "rtn_goodnight",
        "name": "Good night",
        "phrases": ["good night", "goodnight", "going to bed", "going to sleep", "time for bed", "bedtime"],
        "steps": ["turn off all the lights", "lock the front door"],
        "enabled": True,
    },
    {
        "id": "rtn_leaving",
        "name": "I'm leaving",
        "phrases": ["im leaving", "i am leaving", "leaving home", "leaving the house", "heading out", "im heading out"],
        "steps": ["turn off all the lights", "lock the front door", "set the thermostat to 18"],
        "enabled": True,
    },
    {
        "id": "rtn_morning",
        "name": "Good morning",
        "phrases": ["good morning", "start my day", "morning briefing"],
        "steps": ["turn on the kitchen light", "what time is it", "what's on my calendar", "check my email"],
        "enabled": True,
    },
]

# Clause separators for compound commands.
_SPLIT_RE = re.compile(r"\s*(?:[,;]\s*(?:and\s+|then\s+)?|\band then\b|\bthen\b|\band also\b|\bafter that\b|\band\b)\s*",
                       re.IGNORECASE)
# The verb a clause can lend to the next one: "turn off the kitchen light and the bedroom light".
_VERB_RE = re.compile(r"^(turn (?:on|off)|switch (?:on|off))\b", re.IGNORECASE)
_GROUP_RE = re.compile(r"\b(?:turn|switch)\s+(on|off)\b.*\blights\b|\ball\s+(?:the\s+)?lights\s+(on|off)\b",
                       re.IGNORECASE)
_EXPLICIT_ROUTINE_RE = re.compile(r"\b(?:run|start|do|activate|begin)\s+(?:the\s+|my\s+)?(.+?)\s+routine\b"
                                  r"|\broutine\s+(.+)$")
_QUESTION_WORDS = {"what", "how", "why", "when", "where", "who", "which", "whats", "hows"}
# Requests that describe an outcome rather than an action — worth planning with the brain.
GOAL_RE = re.compile(
    r"\b(?:get|make)\b.{0,40}\bready\b|\bprepare\b|\bprep\b|\bset (?:up|the mood)\b|\bgetting ready\b"
    r"|\bmovie (?:night|time)\b|\bwind down\b|\btime to (?:work|focus|relax|sleep|study)\b",
    re.IGNORECASE,
)
# Tool outputs that mean the step didn't really work, even when the tool "succeeded".
_FAIL_RE = re.compile(
    r"^(?:error|failed|could not|couldn't|invalid|unknown)\b"
    r"|\b(?:not configured|couldn't|could not|failed to|not found|isn't supported|not installed)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", "", (text or "").lower()).split())


def looks_failed(output: str) -> bool:
    return bool(_FAIL_RE.search(output or ""))


@dataclass
class PlanStep:
    command: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | done | failed | skipped
    result: str = ""
    verified: bool | None = None


@dataclass
class Plan:
    goal: str
    title: str
    source: str  # routine | group | compound | brain
    steps: list[PlanStep] = field(default_factory=list)
    routine_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"goal": self.goal, "title": self.title, "source": self.source,
                "routine_id": self.routine_id, "steps": [asdict(s) for s in self.steps]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        steps = [PlanStep(command=str(s.get("command", "")), tool=str(s.get("tool", "")),
                          arguments=dict(s.get("arguments") or {}))
                 for s in data.get("steps") or [] if isinstance(s, dict)]
        return cls(goal=str(data.get("goal", "")), title=str(data.get("title", "")),
                   source=str(data.get("source", "")), steps=steps, routine_id=str(data.get("routine_id", "")))

    def summary(self) -> dict[str, Any]:
        """What a UI shows and a confirmation refers to."""
        return {"goal": self.goal, "title": self.title, "steps": [s.command for s in self.steps]}


# ── understanding a clause ────────────────────────────────────────────────
def _light_devices() -> list[tuple[str, str]]:
    from atulya.kriya import _HOME_DEVICES  # lazy: tools imports are heavy

    return [(did, dev.get("name", did)) for did, dev in _HOME_DEVICES.items() if dev.get("type") == "light"]


def steps_for_clause(clause: str) -> list[PlanStep] | None:
    """One clause -> its steps (a light group expands to every light); None if unclear."""
    clause = (clause or "").strip(" .")
    if not clause:
        return None
    lowered = clause.lower()
    group = _GROUP_RE.search(lowered)
    if group and _match_device(lowered) is None:
        state = group.group(1) or group.group(2)
        return [PlanStep(command=f"turn {state} the {name.lower()}", tool="home_control",
                         arguments={"device_id": did, "action": state})
                for did, name in _light_devices()]
    routed = route_intent(clause)
    if routed is None:
        return None
    return [PlanStep(command=clause, tool=routed.tool, arguments=dict(routed.arguments))]


def compound_steps(text: str) -> list[PlanStep] | None:
    """Split "do X and Y then Z" into steps; None unless every clause is clear."""
    clauses = [c.strip(" .") for c in _SPLIT_RE.split(text or "") if c and c.strip(" .")]
    if len(clauses) < 2:
        return None
    steps: list[PlanStep] = []
    verb = ""
    for clause in clauses:
        found = steps_for_clause(clause)
        if found is None and verb:  # "... and the bedroom light" borrows "turn off"
            found = steps_for_clause(f"{verb} {clause}")
        if found is None:
            return None
        m = _VERB_RE.match(clause.lower())
        verb = m.group(1) if m else verb
        steps.extend(found)
    return steps


def expand_command(text: str, routines: "RoutineStore | None" = None) -> list[PlanStep]:
    """Every concrete step a command would run — lets rule engines check a
    routine or compound command for risky steps before running it."""
    plan = Planner(routines).plan(text)
    if plan is not None:
        return plan.steps
    return steps_for_clause(text) or []


def routine_steps(routine: dict[str, Any]) -> list[PlanStep]:
    steps: list[PlanStep] = []
    for command in routine.get("steps") or []:
        steps.extend(steps_for_clause(str(command)) or [])
    return steps[:MAX_STEPS]


# ── routines ──────────────────────────────────────────────────────────────
def _has_devices_to_run_them() -> bool:
    """The example routines turn lights on and lock doors. Only offer them when something real can do that
    (Home Assistant, or a device you added); otherwise every step would just say "no hub is connected"."""
    from atulya.kriya import simulated_home
    from atulya.upakaran import HomeAssistantBridge, get_hub

    try:
        return simulated_home() or HomeAssistantBridge().configured or bool(get_hub().devices)
    except Exception:  # noqa: BLE001 - a broken device file must not stop routines from loading
        return False


class RoutineStore:
    """Named step lists, kept in ATULYA_ROUTINES_FILE (default kosh/agent/routines.json)."""

    def __init__(self, path: str | Path | None = None, seed_defaults: bool = True):
        self.path = Path(path or os.environ.get("ATULYA_ROUTINES_FILE", _DEFAULT_ROUTINES_FILE))
        if seed_defaults and not self.path.exists() and _has_devices_to_run_them():
            self._save([dict(r) for r in DEFAULT_ROUTINES])

    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    def get(self, routine_id: str) -> dict[str, Any] | None:
        return next((r for r in self.list() if r.get("id") == routine_id), None)

    def save(self, routine: dict[str, Any]) -> dict[str, Any]:
        name = str(routine.get("name") or "").strip()
        if not name:
            raise ValueError("a routine needs a name")
        steps = [str(s).strip() for s in routine.get("steps") or [] if str(s).strip()]
        if not steps:
            raise ValueError("a routine needs at least one step")
        for command in steps:
            if steps_for_clause(command) is None:
                raise ValueError(f"Atulya doesn't understand the step '{command}' as a command")
        phrases = routine.get("phrases") or []
        if isinstance(phrases, str):
            phrases = phrases.split(",")
        clean = {
            "id": str(routine.get("id") or f"rtn_{uuid.uuid4().hex[:8]}"),
            "name": name[:80],
            "phrases": [p for p in (_normalize(str(p)) for p in phrases) if p][:20] or [_normalize(name)],
            "steps": steps[:MAX_STEPS],
            "enabled": bool(routine.get("enabled", True)),
        }
        routines = [r for r in self.list() if r.get("id") != clean["id"]]
        routines.append(clean)
        self._save(routines)
        return clean

    def remove(self, routine_id: str) -> bool:
        routines = self.list()
        kept = [r for r in routines if r.get("id") != routine_id]
        if len(kept) == len(routines):
            return False
        self._save(kept)
        return True

    def match(self, text: str) -> dict[str, Any] | None:
        """The routine this utterance asks for, if any.

        "Run the guests routine" always matches by name. Otherwise a phrase must
        make up most of the utterance ("good night, Atulya" yes; "tell me a good
        night story" no), and questions never start a routine.
        """
        norm = _normalize(text)
        if not norm or norm.split()[0] in _QUESTION_WORDS:
            return None
        routines = [r for r in self.list() if r.get("enabled", True)]
        explicit = _EXPLICIT_ROUTINE_RE.search(norm)
        if explicit:
            wanted = (explicit.group(1) or explicit.group(2) or "").strip()
            for r in routines:
                names = {_normalize(r.get("name", "")), r.get("id", "").removeprefix("rtn_"), *r.get("phrases", [])}
                if wanted in names or (len(wanted) >= 3 and any(wanted in n for n in names)):
                    return r
        words = norm.split()
        padded = f" {norm} "
        best: tuple[int, dict[str, Any]] | None = None
        for r in routines:
            for phrase in r.get("phrases", []):
                phrase = _normalize(phrase)
                if phrase and f" {phrase} " in padded and len(words) - len(phrase.split()) <= 3:
                    score = len(phrase)
                    if best is None or score > best[0]:
                        best = (score, r)
        return best[1] if best else None

    def _save(self, routines: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(routines, indent=2, ensure_ascii=False), encoding="utf-8")


# ── the planner ───────────────────────────────────────────────────────────
class Planner:
    def __init__(self, routines: RoutineStore | None = None):
        self._routines = routines

    @property
    def routines(self) -> RoutineStore:
        if self._routines is None:
            self._routines = RoutineStore()
        return self._routines

    def plan(self, text: str) -> Plan | None:
        """A deterministic plan (routine, device group or compound command), or None."""
        text = (text or "").strip()
        if not text:
            return None
        routine = self.routines.match(text)
        if routine:
            steps = routine_steps(routine)
            if steps:
                return Plan(goal=text, title=str(routine.get("name")), source="routine",
                            steps=steps, routine_id=str(routine.get("id")))
        steps = steps_for_clause(text)
        if steps and len(steps) > 1:
            return Plan(goal=text, title=text[:80], source="group", steps=steps)
        steps = compound_steps(text)
        if steps and len(steps) > 1:
            return Plan(goal=text, title=text[:80], source="compound", steps=steps[:MAX_STEPS])
        return None

    @staticmethod
    def is_goal(text: str) -> bool:
        return bool(GOAL_RE.search(text or ""))

    async def plan_with_brain(self, text: str, llm: Any, provider: str = "") -> Plan | None:
        """Ask the language model to break a goal into commands; keep only clear ones."""
        prompt = decomposition_prompt(text)
        try:
            router = getattr(llm, "router", None)
            if router is not None and hasattr(router, "chat"):
                # Straight to the model: a planning prompt isn't a conversation to remember.
                reply, _ = await router.chat(prompt, _PLANNER_SYSTEM, preferred_provider=provider)
            else:
                reply = getattr(await llm.ask(prompt, tools_enabled=False), "text", "")
        except Exception as exc:  # noqa: BLE001 - planning is best-effort; the brain still answers
            logger.debug("brain decomposition failed: %s", exc)
            return None
        steps = parse_brain_steps(str(reply or ""))
        if not steps:
            return None
        return Plan(goal=text, title=text[:80], source="brain", steps=steps)


_PLANNER_SYSTEM = "You turn goals into short, concrete smart-home and assistant commands. Output commands only."


def decomposition_prompt(goal: str) -> str:
    from atulya.kriya import _HOME_DEVICES

    devices = ", ".join(dev.get("name", did).lower() for did, dev in _HOME_DEVICES.items())
    return (
        "You plan actions for a home assistant. Break the goal below into at most 6 short "
        "commands, one per line, with no numbering and no explanation. Use only commands like:\n"
        "turn on the <device> / turn off the <device> / set the thermostat to <degrees> / "
        "lock the front door / remind me to <task> in <N> minutes / what's the weather in <city> / "
        "what's on my calendar / check my email / what time is it\n"
        f"Devices: {devices}.\n"
        "If nothing fits, answer NONE.\n\n"
        f"Goal: {goal}"
    )


def parse_brain_steps(text: str) -> list[PlanStep]:
    """Model output -> validated steps. Unclear lines are dropped, never guessed."""
    steps: list[PlanStep] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)]|step\s*\d+[:.)]?)\s*", "", line, flags=re.IGNORECASE).strip(" .\"'`")
        if not line or line.upper() == "NONE":
            continue
        for step in steps_for_clause(line) or []:
            key = json.dumps([step.tool, step.arguments], sort_keys=True)
            if key not in seen:
                seen.add(key)
                steps.append(step)
    return steps[:6]


# ── checking a step worked ────────────────────────────────────────────────
_EXPECTED_STATE = {"on": "on", "off": "off", "lock": "locked", "unlock": "unlocked"}


async def verify_step(step: PlanStep) -> tuple[bool | None, str]:
    """Check a device actually reached the requested state.

    Returns (True, detail) when confirmed, (False, detail) on a mismatch and
    (None, "") when there's nothing to check. With Home Assistant configured the
    real device state is read back; otherwise the simulated state is checked.
    """
    if step.tool != "home_control":
        return None, ""
    device = str(step.arguments.get("device_id") or "")
    action = str(step.arguments.get("action") or "").lower()
    expected = _EXPECTED_STATE.get(action)
    if action == "set_temperature":
        expected = str(step.arguments.get("value") or "")
    if not expected:
        return None, ""

    from atulya.upakaran import HomeAssistantBridge

    bridge = HomeAssistantBridge()
    if bridge.configured:
        entity = bridge.entity_for(device)
        if not entity:
            return None, ""
        ok, actual = False, ""
        for attempt in range(3):  # devices take a moment ("locking" -> "locked")
            try:
                state = await bridge.state(entity)
            except Exception as exc:  # noqa: BLE001 - an unreadable state is "unchecked", not a failure
                logger.debug("could not read %s: %s", entity, exc)
                return None, ""
            if action == "set_temperature":
                actual = str((state.get("attributes") or {}).get("temperature", ""))
            else:
                actual = str(state.get("state", ""))
            ok = _state_matches(action, actual, expected)
            if ok:
                break
            if attempt < 2:
                await asyncio.sleep(VERIFY_RETRY_SECONDS)
        return ok, f"{entity} is {actual or 'unknown'}"

    from atulya.kriya import _HOME_DEVICES

    dev = _HOME_DEVICES.get(device)
    if not dev:
        return None, ""
    if action == "set_temperature":
        actual = str(dev.get("temperature", ""))
        return _state_matches(action, actual, expected), f"{dev['name']} is at {actual}°"
    actual = str(dev.get("state", ""))
    return _state_matches(action, actual, expected), f"{dev['name']} is {actual}"


VERIFY_RETRY_SECONDS = 0.5


def _state_matches(action: str, actual: str, expected: str) -> bool:
    if action == "set_temperature":
        return _same_number(actual, expected)
    if action == "on":  # a climate device that's "on" reports its mode (heat, cool, auto…)
        return actual not in ("", "off", "unavailable", "unknown")
    return actual == expected


def _same_number(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 0.01
    except ValueError:
        return a == b


# ── parichay ────────────────────────────────────────────────────────────
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
    # Learn a naturally phrased first name, but only when it looks like a proper
    # name. The pronoun carries its own case so the name part can require a
    # capital: without that, IGNORECASE would record "I'm tired" as your name.
    for m in re.finditer(r"\b(?:[Ii] am|[Ii]'m|[Ii]m)\s+([A-Z][\w'-]+)\b", raw):
        if not any(f["kind"] == "name" for f in facts):
            add("name", "name", m.group(1))
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

    def context_for(self, user: str, display_name: str = "") -> str:
        """A short "about the user" block for the brain's system prompt."""
        data = self.load(user)
        lines = [describe_fact(f) for f in data["facts"][-25:]]
        lines += [f"usually {h['label']} {h['when']}" for h in self.habits(user)[:8]]
        display_name = re.sub(r"[\r\n\t]+", " ", str(display_name or "")).strip()[:80]
        if display_name:
            lines.insert(0, f"the signed-in account uses the display name {json.dumps(display_name, ensure_ascii=False)}")
        if not lines:
            return ""
        return "What you know about the user (use it naturally, adapt to learned preferences, and don't recite it):\n" + "\n".join(
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
                          r"|\btell me (?:what you know )?about myself\b|\bwhat do you know of me\b"
                          r"|\bwho am i\b|\bwhat(?:'s| is) my name\b")
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


# ── prerak ────────────────────────────────────────────────────────────
TRIGGER_SOURCE = "trigger"
_DEFAULT_RULES_FILE = "kosh/agent/triggers.json"

# Built-in reflexes, seeded on first run (users can edit, disable or delete them).
DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "id": "trg_reminder_alert",
        "name": "Reminder alerts",
        "event": "reminder.due",
        "notify": "Reminder: {message}",
        "enabled": True,
        "cooldown_seconds": 0,
    },
    {
        "id": "trg_health_alert",
        "name": "System health alerts",
        "event": ["health.warning", "health.error"],
        "notify": "System check '{check}' needs attention: {message}",
        "enabled": True,
        "cooldown_seconds": 900,
    },
    {
        "id": "trg_automation_failed",
        "name": "Automation failure alerts",
        "event": "automation.failed",
        "notify": "Automation '{job}' failed: {error}",
        "enabled": True,
        "cooldown_seconds": 300,
    },
    {
        "id": "trg_habit_nudge",
        "name": "Habit nudges",
        "event": "habit.due",
        "notify": "You usually {label} {when} — just say the word.",
        "enabled": True,
        "cooldown_seconds": 0,
    },
    {
        "id": "trg_calendar_soon",
        "name": "Meeting heads-up",
        "event": "calendar.soon",
        "notify": "{title} starts in {minutes} minutes.",
        "enabled": True,
        "cooldown_seconds": 0,
    },
    {
        "id": "trg_bill_due",
        "name": "Bill reminders",
        "event": "bill.due",
        "notify": "{name} ({amount}) is due {due}.",
        "enabled": True,
        "cooldown_seconds": 0,
    },
    {
        "id": "trg_someone_at_door",
        "name": "Someone at the door",
        "event": ["vision.person", "doorbell.pressed"],
        "match": {"camera": "door"},
        "notify": "Someone is at the {camera}.",
        "enabled": True,
        "cooldown_seconds": 60,
    },
]
# Rules shipped before new defaults were added; used to top up older rule files
# without bringing back a default the user deleted.
_ORIGINAL_DEFAULTS = {"trg_reminder_alert", "trg_health_alert", "trg_automation_failed"}

_FIELD_RE = re.compile(r"\{(\w+)\}")


def render(template: str, payload: dict[str, Any]) -> str:
    """Fill ``{field}`` placeholders from the payload (plain names only)."""
    return _FIELD_RE.sub(lambda m: str(payload.get(m.group(1), ""))[:300], template)


def _event_matches(pattern: Any, event_type: str) -> bool:
    patterns = pattern if isinstance(pattern, list) else [pattern]
    return any(isinstance(p, str) and fnmatch.fnmatchcase(event_type, p) for p in patterns)


def _payload_matches(match: dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    for key, expected in (match or {}).items():
        actual = payload.get(key)
        if isinstance(actual, str) and isinstance(expected, str):
            if expected.lower() not in actual.lower():
                return False
        elif actual != expected:
            return False
    return True


class TriggerEngine:
    def __init__(
        self,
        rules_file: str | Path | None = None,
        kernel: Any = None,
        events: EventBus | None = None,
        seed_defaults: bool = True,
    ):
        self.rules_file = Path(rules_file or os.environ.get("ATULYA_TRIGGERS_FILE", _DEFAULT_RULES_FILE))
        self._kernel = kernel
        self.events = events or default_bus
        self._started = False
        self._last_fired: dict[str, float] = {}
        self._tasks: set[asyncio.Task] = set()
        if seed_defaults:
            self._seed_defaults()

    @property
    def kernel(self) -> Any:
        if self._kernel is None:

            self._kernel = get_kernel()
        return self._kernel

    def start(self) -> None:
        """Subscribe to every event on the bus (idempotent)."""
        if not self._started:
            self.events.subscribe("*", self._on_event)
            self._started = True

    def stop(self) -> None:
        if self._started:
            self.events.unsubscribe("*", self._on_event)
            self._started = False

    def _seed_defaults(self) -> None:
        """First run: every built-in rule. Later: only built-ins added since, once."""
        seeded_file = self.rules_file.with_name(self.rules_file.stem + ".seeded.json")
        if not self.rules_file.exists():
            self._save([dict(rule) for rule in DEFAULT_RULES])
        else:
            try:
                seeded = set(json.loads(seeded_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError):
                seeded = set(_ORIGINAL_DEFAULTS)
            rules = self.list_rules()
            have = {r.get("id") for r in rules}
            new = [dict(r) for r in DEFAULT_RULES if r["id"] not in seeded and r["id"] not in have]
            if new:
                self._save(rules + new)
        try:
            seeded_file.write_text(json.dumps(sorted(r["id"] for r in DEFAULT_RULES)), encoding="utf-8")
        except OSError:
            pass

    # ── rules ──────────────────────────────────────────────────────────────
    def list_rules(self) -> list[dict[str, Any]]:
        if not self.rules_file.exists():
            return []
        try:
            data = json.loads(self.rules_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [rule for rule in data if isinstance(rule, dict)] if isinstance(data, list) else []

    def add_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        event = rule.get("event")
        if not event or not (isinstance(event, str) or isinstance(event, list)):
            raise ValueError("rule needs an 'event' (type, glob, or list)")
        if not (rule.get("notify") or rule.get("command")):
            raise ValueError("rule needs 'notify' and/or 'command'")
        clean = {
            "id": str(rule.get("id") or f"trg_{uuid.uuid4().hex[:10]}"),
            "name": str(rule.get("name") or rule.get("command") or rule.get("notify"))[:120],
            "event": event,
            "match": rule.get("match") if isinstance(rule.get("match"), dict) else {},
            "notify": str(rule.get("notify") or ""),
            "command": str(rule.get("command") or ""),
            "allow_risky": bool(rule.get("allow_risky", False)),
            "cooldown_seconds": max(0, int(rule.get("cooldown_seconds", 60))),
            "enabled": bool(rule.get("enabled", True)),
        }
        rules = self.list_rules()
        previous = next((r for r in rules if r.get("id") == clean["id"]), None)
        if previous:  # editing (e.g. pause/resume) keeps the rule's history
            for key in ("fire_count", "last_fired", "last_result"):
                if key in previous:
                    clean[key] = previous[key]
        rules = [r for r in rules if r.get("id") != clean["id"]]
        rules.append(clean)
        self._save(rules)
        return clean

    def remove_rule(self, rule_id: str) -> bool:
        rules = self.list_rules()
        kept = [r for r in rules if r.get("id") != rule_id]
        if len(kept) == len(rules):
            return False
        self._save(kept)
        return True

    def matching_rules(self, event: Event) -> list[dict[str, Any]]:
        # Loop guard: never react to what a trigger itself caused.
        if event.payload.get("source") == TRIGGER_SOURCE or event.type in ("trigger.fired", "notification"):
            return []
        return [
            rule for rule in self.list_rules()
            if rule.get("enabled", True)
            and _event_matches(rule.get("event"), event.type)
            and _payload_matches(rule.get("match"), event.payload)
        ]

    # ── firing ─────────────────────────────────────────────────────────────
    async def _on_event(self, event: Event) -> None:
        now = time.monotonic()
        for rule in self.matching_rules(event):
            rid = str(rule.get("id"))
            cooldown = float(rule.get("cooldown_seconds", 60) or 0)
            if cooldown and now - self._last_fired.get(rid, -1e18) < cooldown:
                continue
            self._last_fired[rid] = now
            # Run in the background: the emitter (e.g. a chat request) must not wait.
            task = asyncio.create_task(self.fire(rule, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def fire(self, rule: dict[str, Any], event: Event) -> dict[str, Any]:
        name = str(rule.get("name") or rule.get("id"))
        result: dict[str, Any] = {"rule": rule.get("id"), "name": name, "event": event.type,
                                  "source": TRIGGER_SOURCE}
        if rule.get("notify"):
            text = render(str(rule["notify"]), event.payload)
            await self._notify(name, text)
            result["notified"] = text

        command = str(rule.get("command") or "").strip()
        if command:
            # A command may be a routine or several commands: check every step.
            planner = getattr(self.kernel, "planner", None)
            steps = expand_command(command, getattr(planner, "routines", None))
            risky = [s for s in steps if safety.needs_confirmation(s.tool, s.arguments)]
            if risky and not rule.get("allow_risky"):
                blocked = (f"Trigger '{name}' wanted to {safety.describe_action(risky[0].tool, risky[0].arguments)}, "
                           "but risky actions need allow_risky on the rule.")
                await self._notify(name, blocked)
                result["blocked"] = blocked
            else:
                try:
                    response = await self.kernel.handle(command, user=TRIGGER_SOURCE, source=TRIGGER_SOURCE)
                    result["response"] = response.text
                except Exception as exc:  # noqa: BLE001 - a failing rule must not break the bus
                    result["error"] = str(exc)
                    logger.warning("trigger %s failed: %s", name, exc)

        self._record(str(rule.get("id")), result)
        try:
            await self.events.emit("trigger.fired", result)
        except Exception:  # noqa: BLE001
            pass
        return result

    async def drain(self) -> None:
        """Wait for in-flight trigger tasks (used by tests and shutdown)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _notify(self, title: str, message: str) -> None:
        # Published on the bus; the web layer relays "notification" events to
        # connected clients, so the core never depends on the UI.
        try:
            await self.events.emit("notification", {"title": title, "message": message, "source": TRIGGER_SOURCE})
        except Exception:  # noqa: BLE001
            pass

    def _record(self, rule_id: str, result: dict[str, Any]) -> None:
        rules = self.list_rules()
        for rule in rules:
            if rule.get("id") == rule_id:
                rule["fire_count"] = int(rule.get("fire_count") or 0) + 1
                rule["last_fired"] = time.time()
                rule["last_result"] = {k: v for k, v in result.items() if k in ("notified", "response", "blocked", "error")}
        self._save(rules)

    def _save(self, rules: list[dict[str, Any]]) -> None:
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        self.rules_file.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


_SENSORS_CONNECTED = False


def connect_sensors(events: EventBus | None = None) -> None:
    """Publish reminder firings on the event bus (idempotent).

    Reminders previously fired into callbacks nobody registered, so a due
    reminder reached no one; now it becomes a ``reminder.due`` event.
    """
    global _SENSORS_CONNECTED
    if _SENSORS_CONNECTED:
        return
    bus = events or default_bus
    from atulya.kriya import register_reminder_callback

    async def _reminder_due(event_type: str, entry: dict[str, Any]) -> None:
        await bus.emit("reminder.due", {
            "id": entry.get("id"),
            "message": entry.get("message", ""),
            "scheduled_time": entry.get("scheduled_time"),
        })

    register_reminder_callback(_reminder_due)
    _SENSORS_CONNECTED = True


# ── buddhi ────────────────────────────────────────────────────────────
KERNEL_PROVIDER = "Atulya Kernel"
KERNEL_ORIGIN = "kernel"


def _same_action(held: dict[str, Any] | None, approved: dict[str, Any]) -> bool:
    """Is this approval for exactly the action that was held (same tool, same arguments)?"""
    if not held:
        return False

    def key(action: dict[str, Any]) -> tuple[str, str]:
        return str(action.get("tool") or ""), json.dumps(action.get("arguments") or {}, sort_keys=True, default=str)

    return key(held) == key(approved)
# Commands the user authored in advance (scheduled jobs, trigger rules) were
# approved when they were created, so they don't stop to ask again.
PRE_AUTHORIZED_SOURCES = {"automation", "trigger"}
PENDING_TTL_SECONDS = 120
# Offers only the kernel makes and answers; never tools the brain or a client can call.
TRUST_TOOL = "trust_action"
FORGET_TOOL = "forget_profile"
_INTERNAL_TOOLS = {TRUST_TOOL, FORGET_TOOL}
_MAX_PENDING = 256

_FILLER = {"please", "ji", "sir", "atulya", "it", "ahead", "for", "sure", "thanks", "thank", "you", "that", "now", "karo", "do"}
# No "ha": laughter ("ha ha") must never release a held action.
_AFFIRM = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "approve", "approved",
           "proceed", "haan", "go", "do"}
_DENY = {"no", "nope", "nah", "cancel", "stop", "dont", "abort", "nahi", "mat", "never", "mind", "nevermind"}


def confirmation_intent(text: str) -> str | None:
    """Return 'affirm' / 'deny' when the whole utterance is a clear yes / no.

    Deliberately strict: "stop the music" is a new command, not a cancel, and
    only a clear yes can release a held action.
    """
    tokens = re.sub(r"[^\w\s]", "", (text or "").lower()).split()
    if not tokens or len(tokens) > 6:
        return None
    if tokens[0] in _DENY and all(t in _DENY or t in _FILLER for t in tokens):
        return "deny"
    if tokens[0] in _AFFIRM and all(t in _AFFIRM or t in _FILLER for t in tokens):
        return "affirm"
    return None


def _brain_kwargs(
    history: list[dict[str, str]] | None,
    approved_tool: dict[str, Any] | None,
    provider: str,
    tools_enabled: bool,
) -> dict[str, Any]:
    """Only the arguments that carry information, so any brain with a narrower
    ``ask``/``stream`` signature (e.g. a test double) still works."""
    kwargs: dict[str, Any] = {}
    if history:
        kwargs["history"] = history
    if approved_tool:
        kwargs["approved_tool_call"] = approved_tool
    if provider:
        kwargs["provider"] = provider
    if not tools_enabled:
        kwargs["tools_enabled"] = False
    return kwargs


def _is_privileged(user: Any, source: str) -> bool:
    """May this caller perform confirmation-level actions at all?

    Web users carry a role: only admins may unlock doors, send email, delete
    data or run code — a guest account can still turn on lights or set
    reminders. Pre-authorized sources (automations, trigger rules) are created
    by admins. Callers without role information (CLI, direct use) are local
    and trusted.
    """
    if source in PRE_AUTHORIZED_SOURCES:
        return True
    if isinstance(user, dict):
        return user.get("role") == "admin"
    return True


def _kernel_tools() -> set[str]:
    from atulya import kriya as agent_tools

    return set(agent_tools.TOOL_REGISTRY) - EXCLUDED_FROM_BRAIN


# ── trace: the real stages a request went through, for UIs to display ──────
def _step(stage: str, title: str, detail: str) -> dict[str, str]:
    return {"stage": stage, "title": title, "detail": str(detail)[:240]}


def _describe_call(tool: str, args: dict[str, Any]) -> str:
    shown = ", ".join(f"{k}={v}" for k, v in args.items() if v not in ("", None))
    return f"{tool}({shown})"


def _brain_trace(response: Any, lead: list[dict[str, str]]) -> list[dict[str, str]]:
    steps = list(lead)
    for s in getattr(response, "tool_steps", None) or []:
        steps.append(_step("act", "Tool", f"{s.get('tool')}: {'done' if s.get('success') else 'failed'}"))
    if getattr(response, "needs_approval", False):
        pending = getattr(response, "pending_tool", None) or {}
        steps.append(_step("decide", "Needs confirmation",
                           safety.describe_action(pending.get("tool", ""), pending.get("arguments"))))
    else:
        steps.append(_step("think", "Answer", f"Answered by {getattr(response, 'provider', '') or 'the brain'}"))
    return steps


def _set_trace(response: Any, trace: list[dict[str, str]]) -> Any:
    try:
        response.trace = trace
    except (AttributeError, TypeError):  # a foreign response object
        pass
    return response


def _lead_step(approved_tool: dict[str, Any] | None) -> list[dict[str, str]]:
    if approved_tool:
        phrase = safety.describe_action(approved_tool.get("tool", ""), approved_tool.get("arguments"))
        return [_step("decide", "Approved", f"You approved: {phrase}")]
    return [_step("understand", "Conversation", "No direct command — thinking it through")]


class CognitiveKernel:
    def __init__(
        self,
        llm: Any = None,
        events: EventBus | None = None,
        planner: Planner | None = None,
        profiles: ProfileStore | None = None,
    ):
        self._llm = llm
        self.events = events or default_bus
        self.planner = planner or Planner()
        self.profiles = profiles or ProfileStore()
        self._pending: OrderedDict[str, tuple[dict[str, Any], float]] = OrderedDict()

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = get_default_llm()
        return self._llm

    # ── public entry points ────────────────────────────────────────────────
    async def handle(
        self,
        text: str,
        *,
        user: Any = None,
        history: list[dict[str, str]] | None = None,
        source: str = "chat",
        approved_tool: dict[str, Any] | None = None,
        provider: str = "",
        tools_enabled: bool = True,
    ) -> LLMResponse:
        # Personal tools (Gmail, Calendar) act for whoever is asking.
        with acting_as(self._user_key(user), access_of(user)):
            return await self._handle(text, user, history, source, approved_tool, provider, tools_enabled)

    async def _handle(self, text: str, user: Any, history: list[dict[str, str]] | None, source: str,
                      approved_tool: dict[str, Any] | None, provider: str, tools_enabled: bool) -> LLMResponse:
        fast = await self._fast_path(text, user, history, source, approved_tool, provider, tools_enabled)
        if fast is not None:
            return fast
        response = await self.llm.ask(text, **self._ask_kwargs(user, history, approved_tool, provider, tools_enabled))
        for step in getattr(response, "tool_steps", None) or []:
            await self._publish_step(step, user, source)
        if getattr(response, "needs_approval", False):
            self._hold(user, getattr(response, "pending_tool", None), origin="llm")
        return _set_trace(response, _brain_trace(response, _lead_step(approved_tool)))

    async def stream(
        self,
        text: str,
        *,
        user: Any = None,
        history: list[dict[str, str]] | None = None,
        source: str = "chat",
        approved_tool: dict[str, Any] | None = None,
        provider: str = "",
        tools_enabled: bool = True,
    ) -> AsyncIterator[LLMEvent]:
        token = current_user.set(self._user_key(user))
        access_token = current_access.set(access_of(user))
        try:
            async for event in self._stream(text, user, history, source, approved_tool, provider, tools_enabled):
                yield event
        finally:
            try:
                current_user.reset(token)
                current_access.reset(access_token)
            except ValueError:  # closed from another context (e.g. a dropped connection)
                pass

    async def _stream(self, text: str, user: Any, history: list[dict[str, str]] | None, source: str,
                      approved_tool: dict[str, Any] | None, provider: str,
                      tools_enabled: bool) -> AsyncIterator[LLMEvent]:
        fast = await self._fast_path(text, user, history, source, approved_tool, provider, tools_enabled)
        if fast is not None:
            for event in response_events(fast):
                yield event
            return
        tool_steps: list[dict[str, Any]] = []
        kwargs = self._ask_kwargs(user, history, approved_tool, provider, tools_enabled)
        async for event in self.llm.stream(text, **kwargs):
            if event.type == "tool" and isinstance(event.metadata, dict):
                tool_steps.append(event.metadata)
                await self._publish_step(event.metadata, user, source)
            if event.type == "done":
                meta = dict(event.metadata or {})
                if meta.get("needs_approval"):
                    self._hold(user, meta.get("pending_tool"), origin="llm")
                summary = LLMResponse(text="", provider=str(meta.get("provider") or ""), tool_steps=tool_steps,
                                      needs_approval=bool(meta.get("needs_approval")),
                                      pending_tool=meta.get("pending_tool"))
                meta["trace"] = _brain_trace(summary, _lead_step(approved_tool))
                event = LLMEvent("done", content=event.content, metadata=meta)
            yield event

    def pending_action(self, user: Any = None) -> dict[str, Any] | None:
        """The action currently held for this user's confirmation, if any."""
        key = self._user_key(user)
        entry = self._pending.get(key)
        if entry is None:
            return None
        action, created = entry
        if time.monotonic() - created > PENDING_TTL_SECONDS:
            self._pending.pop(key, None)
            return None
        return action

    def _ask_kwargs(self, user: Any, history: list[dict[str, str]] | None, approved_tool: dict[str, Any] | None,
                    provider: str, tools_enabled: bool) -> dict[str, Any]:
        kwargs = _brain_kwargs(history, approved_tool, provider, tools_enabled)
        if isinstance(self.llm, AtulyaLLM):  # the real brain also gets what it knows about the user
            display_name = (user.get("profile_display_name") or user.get("display_name", "")) if isinstance(user, dict) else ""
            context = self.profiles.context_for(self._user_key(user), display_name=display_name)
            if context:
                kwargs["context"] = context
        return kwargs

    # ── pipeline ───────────────────────────────────────────────────────────
    async def _fast_path(
        self,
        text: str,
        user: Any,
        history: list[dict[str, str]] | None,
        source: str,
        approved_tool: dict[str, Any] | None,
        provider: str,
        tools_enabled: bool,
    ) -> LLMResponse | None:
        """Handle what the kernel can decide itself; None means 'ask the brain'."""
        text = (text or "").strip()
        key = self._user_key(user)

        # UI "Approve": this resolves whatever was held. Kernel-held assistant
        # actions run here; anything else goes to the brain's approval flow.
        if approved_tool:
            held = self.pending_action(user)
            self._pending.pop(key, None)
            tool = approved_tool.get("tool")
            if tool in _INTERNAL_TOOLS:  # only ever the offer the kernel itself made
                return await self._internal(held if held and held.get("tool") == tool else None, user, True)
            if tool == PLAN_TOOL:
                return await self._approved_plan(approved_tool, held, user=user, source=source, prompt=text)
            denied = await self._deny_if_unprivileged(approved_tool, user, source)
            if denied is not None:
                return denied
            if not _same_action(held, approved_tool):  # only what Atulya itself asked about, once
                return await self._not_waiting(approved_tool, user, source)
            self._learn_approval(user, approved_tool, True)
            if approved_tool.get("origin") == KERNEL_ORIGIN and approved_tool.get("tool") in _kernel_tools():
                response = await self._act(approved_tool, user=user, source=source, prompt=text,
                                           trace=_lead_step(approved_tool))
                return self._maybe_offer_trust(response, user, approved_tool)
            return None

        # A spoken/typed yes or no resolves the held action. Any other message
        # means the conversation moved on, so the held action is dropped — a
        # stray "yes" later can never release it.
        pending = self.pending_action(user)
        if pending is not None:
            self._pending.pop(key, None)
            intent = confirmation_intent(text)
            held_tool = str(pending.get("tool", ""))
            phrase = safety.describe_action(held_tool, pending.get("arguments"))
            if intent is not None and held_tool in _INTERNAL_TOOLS:
                return await self._internal(pending, user, intent == "affirm")
            is_plan = held_tool == PLAN_TOOL and isinstance(pending.get("plan"), dict)
            if intent == "affirm":
                confirmed = [_step("decide", "Confirmed", f"You confirmed: {phrase}")]
                if is_plan:
                    plan = Plan.from_dict(pending["plan"])
                    self._learn_plan_approval(user, plan, True)
                    return await self._run_plan(plan, user=user, source=source, prompt=text, trace=confirmed)
                denied = await self._deny_if_unprivileged(pending, user, source)
                if denied is not None:
                    return denied
                self._learn_approval(user, pending, True)
                if pending.get("origin") == KERNEL_ORIGIN:
                    response = await self._act(pending, user=user, source=source, prompt=text, trace=confirmed)
                    return self._maybe_offer_trust(response, user, pending)
                llm_call = {k: v for k, v in pending.items() if k != "origin"}
                response = await self.llm.ask(text, **self._ask_kwargs(user, history, llm_call, provider, True))
                for step in getattr(response, "tool_steps", None) or []:
                    await self._publish_step(step, user, source)
                return _set_trace(response, _brain_trace(response, confirmed))
            if intent == "deny":
                if is_plan:
                    self._learn_plan_approval(user, Plan.from_dict(pending["plan"]), False)
                else:
                    self._learn_approval(user, pending, False)
                await self._emit("action.cancelled", {"tool": held_tool, "user": key, "source": source})
                return LLMResponse(text=f"Okay, I won't {phrase}.", provider=KERNEL_PROVIDER,
                                   trace=[_step("decide", "Cancelled", f"Cancelled: {phrase}")])

        # Learn about the user from what they say, and answer questions about it.
        if text and source in USER_SOURCES:
            about = await self._profile_turn(text, user)
            if about is not None:
                return about

        if not tools_enabled or not text:
            return None

        # Understand a goal: a routine, a device group or several commands at
        # once become a plan; goal-like requests ask the brain for the steps.
        plan = self.planner.plan(text)
        if plan is None and self.planner.is_goal(text) and route_intent(text) is None:
            plan = await self.planner.plan_with_brain(text, self.llm, provider=provider)
        if plan is not None:
            return await self._start_plan(plan, user=user, source=source, prompt=text)

        # Understand: turn a clear command into a concrete action.
        routed = route_intent(text)
        if routed is None:
            return None
        action = {"tool": routed.tool, "arguments": dict(routed.arguments), "origin": KERNEL_ORIGIN}
        understood = _step("understand", "Intent", _describe_call(routed.tool, routed.arguments))

        # Decide: risky actions need an admin, and wait for confirmation unless
        # pre-authorized or the user has told Atulya to stop asking.
        assessment = safety.assess(routed.tool, routed.arguments)
        denied = await self._deny_if_unprivileged(action, user, source)
        if denied is not None:
            return _set_trace(denied, [understood, *denied.trace])
        trusted = assessment.needs_confirmation and self.profiles.is_trusted(key, routed.tool, routed.arguments)
        if assessment.needs_confirmation and source not in PRE_AUTHORIZED_SOURCES and not trusted:
            self._hold(user, action, origin=KERNEL_ORIGIN)
            phrase = safety.describe_action(routed.tool, routed.arguments)
            await self._emit("action.pending", {"tool": routed.tool, "arguments": routed.arguments,
                                                "user": key, "source": source, "reason": assessment.reason})
            return LLMResponse(
                text=(f"Just to confirm — should I {phrase}? That {assessment.reason}. "
                      "Say yes to go ahead, or no to cancel."),
                provider=KERNEL_PROVIDER,
                needs_approval=True,
                pending_tool={**action, "description": phrase},
                trace=[understood, _step("decide", "Needs confirmation", f"That {assessment.reason}")],
            )

        # Act.
        if trusted:
            why = "You told me I don't need to ask"
        else:
            why = "Pre-authorized by you" if assessment.needs_confirmation else "Safe to run now"
        return await self._act(action, user=user, source=source, prompt=text,
                               trace=[understood, _step("decide", "Allowed", why)])

    # ── learning about the user ────────────────────────────────────────────
    async def _profile_turn(self, text: str, user: Any) -> LLMResponse | None:
        key = self._user_key(user)
        intent = profile_intent(text)
        if intent is not None:
            kind, what = intent
            asked = _step("understand", "About you", "A question about what I've learned")
            if kind == "about":
                lines = self.profiles.summary_lines(key)
                display_name = (user.get("profile_display_name") or user.get("display_name", "")) if isinstance(user, dict) else ""
                display_name = re.sub(r"[\r\n\t]+", " ", str(display_name or "")).strip()[:80]
                if display_name:
                    lines.insert(0, f"Your signed-in account's display name is {display_name}.")
                reply = ("Here's what I know about you:\n" + "\n".join(f"- {line}" for line in lines) if lines else
                         "I don't know much about you yet. Tell me things like “my name is …”, "
                         "“my wife's name is …” or “I like …” and I'll remember.")
                return LLMResponse(text=reply, provider=KERNEL_PROVIDER,
                                   trace=[asked, _step("remember", "Profile", f"{len(lines)} things I know")])
            if kind == "forget_all":
                offer = {"tool": FORGET_TOOL, "arguments": {}, "origin": KERNEL_ORIGIN}
                self._hold(user, offer, origin=KERNEL_ORIGIN)
                return LLMResponse(text="Should I forget everything I've learned about you? Say yes or no.",
                                   provider=KERNEL_PROVIDER, needs_approval=True,
                                   pending_tool={**offer, "description": safety.describe_action(FORGET_TOOL, {})},
                                   trace=[asked, _step("decide", "Needs confirmation", "Deletes your profile")])
            if kind == "forget":
                removed = self.profiles.forget(key, what)
                reply = ("Done — I've forgotten that " + "; ".join(describe_fact(f) for f in removed) + "."
                         if removed else "I didn't have that remembered.")
                return LLMResponse(text=reply, provider=KERNEL_PROVIDER,
                                   trace=[asked, _step("remember", "Forgot", f"{len(removed)} facts removed")])
            if kind == "always_ask":
                removed = self.profiles.untrust(key)
                reply = ("Okay — I'll ask before every risky action again." if removed
                         else "I already ask before every risky action.")
                return LLMResponse(text=reply, provider=KERNEL_PROVIDER,
                                   trace=[asked, _step("decide", "Always ask", f"{len(removed)} actions")])

        facts = extract_facts(text)
        if not facts:
            return None
        stored = self.profiles.remember(key, facts)
        learned = [describe_fact(f) for f in stored]
        await self._emit("profile.learned", {"user": key, "facts": learned})
        if not is_pure_statement(text):
            return None  # remembered quietly; the brain answers the rest
        return LLMResponse(text="Got it — I'll remember that " + " and ".join(learned) + ".",
                           provider=KERNEL_PROVIDER,
                           trace=[_step("understand", "About you", "Something you told me about yourself"),
                                  _step("remember", "Profile", "; ".join(learned))])

    def _learn_approval(self, user: Any, action: dict[str, Any], approved: bool) -> None:
        tool = str(action.get("tool") or "")
        args = action.get("arguments") or {}
        if not safety.needs_confirmation(tool, args):
            return
        try:
            self.profiles.record_approval(self._user_key(user), approval_key(tool, args),
                                          safety.describe_action(tool, args), approved)
        except OSError as exc:  # learning is best-effort
            logger.debug("could not record approval: %s", exc)

    def _learn_plan_approval(self, user: Any, plan: Plan, approved: bool) -> None:
        for step in plan.steps:
            self._learn_approval(user, {"tool": step.tool, "arguments": step.arguments}, approved)

    def _learn_action(self, user: Any, source: str, tool: str, args: dict[str, Any], ok: bool) -> None:
        if not ok or source not in USER_SOURCES:
            return
        try:
            self.profiles.record_action(self._user_key(user), tool, args, safety.describe_action(tool, args))
        except OSError as exc:
            logger.debug("could not record habit: %s", exc)

    def _maybe_offer_trust(self, response: LLMResponse, user: Any, action: dict[str, Any]) -> LLMResponse:
        """After the Nth yes in a row, offer to stop asking (only with the user's OK)."""
        tool = str(action.get("tool") or "")
        args = action.get("arguments") or {}
        key = self._user_key(user)
        k = approval_key(tool, args)
        succeeded = bool(response.tool_steps) and bool(response.tool_steps[0].get("success"))
        if not succeeded or not self.profiles.should_offer_trust(key, k):
            return response
        self.profiles.mark_offered(key, k)
        label = safety.describe_action(tool, args)
        offer = {"tool": TRUST_TOOL, "arguments": {"key": k, "label": label}, "origin": KERNEL_ORIGIN}
        self._hold(user, offer, origin=KERNEL_ORIGIN)
        response.text += (f"\n\nBy the way, you've said yes to this {LEARN_AFTER} times in a row. "
                          f"Want me to stop asking before I {label}? Say yes or no.")
        response.needs_approval = True
        response.pending_tool = {**offer, "description": safety.describe_action(TRUST_TOOL, offer["arguments"])}
        response.trace = [*response.trace, _step("remember", "Learned", f"You always approve: {label}")]
        return response

    async def _internal(self, action: dict[str, Any] | None, user: Any, affirmed: bool) -> LLMResponse:
        """Answer an offer the kernel made (stop asking / forget everything)."""
        key = self._user_key(user)
        if action is None:
            return LLMResponse(text="That question has expired, so I haven't changed anything.",
                               provider=KERNEL_PROVIDER, trace=[_step("decide", "Expired", "Nothing changed")])
        tool = action.get("tool")
        args = action.get("arguments") or {}
        if tool == TRUST_TOOL:
            label = str(args.get("label") or "do that")
            if affirmed and self.profiles.trust(key, str(args.get("key") or "")):
                await self._emit("profile.trusted", {"user": key, "action": label})
                return LLMResponse(
                    text=(f"Okay — I won't ask again before I {label}. You can change this under "
                          "About you, or just say “always ask me first”."),
                    provider=KERNEL_PROVIDER, trace=[_step("remember", "Learned", f"Won't ask before: {label}")])
            return LLMResponse(text="Okay, I'll keep asking first.", provider=KERNEL_PROVIDER,
                               trace=[_step("decide", "Keep asking", label)])
        if affirmed:  # FORGET_TOOL
            self.profiles.forget_everything(key)
            await self._emit("profile.forgotten", {"user": key})
            return LLMResponse(text="Done — I've forgotten everything I'd learned about you.",
                               provider=KERNEL_PROVIDER, trace=[_step("remember", "Forgot", "Profile cleared")])
        return LLMResponse(text="Okay, I'll keep what I know.", provider=KERNEL_PROVIDER,
                           trace=[_step("decide", "Kept", "Profile unchanged")])

    async def _not_waiting(self, action: dict[str, Any], user: Any, source: str) -> LLMResponse:
        """An approval for something that was never asked (or has expired): refuse, and say so."""
        tool = str(action.get("tool") or "")
        await self._emit("action.denied", {"tool": tool, "user": self._user_key(user), "source": source,
                                           "reason": "no matching request was waiting"})
        return LLMResponse(
            text="That approval has expired or was never requested, so I did not do it. Ask me again.",
            provider=KERNEL_PROVIDER,
            trace=[_step("decide", "Refused", "No matching request was waiting for approval")],
        )

    async def _deny_if_unprivileged(self, action: dict[str, Any], user: Any, source: str) -> LLMResponse | None:
        """Refuse a confirmation-level action for a non-admin web user."""
        tool = str(action.get("tool") or "")
        args = action.get("arguments") or {}
        assessment = safety.assess(tool, args)
        if not assessment.needs_confirmation or _is_privileged(user, source):
            return None
        phrase = safety.describe_action(tool, args)
        await self._emit("action.denied", {"tool": tool, "user": self._user_key(user),
                                           "source": source, "reason": assessment.reason})
        return LLMResponse(
            text=f"Sorry — only an admin can {phrase}. That {assessment.reason}.",
            provider=KERNEL_PROVIDER,
            trace=[_step("decide", "Refused", f"Admin only — that {assessment.reason}")],
        )

    async def _act(
        self,
        action: dict[str, Any],
        *,
        user: Any,
        source: str,
        prompt: str,
        trace: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        tool = str(action.get("tool") or "")
        args = dict(action.get("arguments") or {})
        step = await self._execute(tool, args)
        ok = bool(step.get("success"))
        text = step.get("output") if ok else f"I couldn't do that — {step.get('error') or 'the tool failed'}."
        text = text or "Done."
        steps = [*(trace or []), _step("act", "Action" if ok else "Action failed", text)]
        self._learn_action(user, source, tool, args, ok)
        # Remember what was done, and let the rest of the system react to it.
        if await self._remember(prompt or safety.describe_action(tool, args), text):
            steps.append(_step("remember", "Memory", "Saved to memory"))
        await self._emit("action.executed", {"tool": tool, "arguments": args, "success": ok,
                                             "source": source, "user": self._user_key(user), "result": text[:500]})
        return LLMResponse(text=text, provider=KERNEL_PROVIDER, tool_steps=[step], trace=steps)

    # ── plans ──────────────────────────────────────────────────────────────
    async def start_plan(self, plan: Plan, *, user: Any = None, source: str = "chat") -> LLMResponse:
        """Run a plan (e.g. a routine started from the UI) with the usual safety rules."""
        return await self._start_plan(plan, user=user, source=source, prompt=plan.goal)

    async def _start_plan(self, plan: Plan, *, user: Any, source: str, prompt: str) -> LLMResponse:
        """Run a plan now, or hold it for one confirmation if a step is risky."""
        planned = _step("plan", "Plan", f"{plan.title}: {len(plan.steps)} steps ({plan.source})")
        key = self._user_key(user)
        risky = [(i, s, safety.assess(s.tool, s.arguments)) for i, s in enumerate(plan.steps, 1)]
        risky = [(i, s, a) for i, s, a in risky
                 if a.needs_confirmation and not self.profiles.is_trusted(key, s.tool, s.arguments)]
        if risky and source not in PRE_AUTHORIZED_SOURCES and _is_privileged(user, source):
            action = {"tool": PLAN_TOOL, "arguments": plan.summary(), "origin": KERNEL_ORIGIN}
            self._hold(user, {**action, "plan": plan.to_dict()}, origin=KERNEL_ORIGIN)
            await self._emit("action.pending", {"tool": PLAN_TOOL, "arguments": plan.summary(), "user": key,
                                                "source": source, "reason": risky[0][2].reason})
            flagged = {i: a.reason for i, _, a in risky}
            lines = [f"{i}. {s.command}" + (f" — that {flagged[i]}" if i in flagged else "")
                     for i, s in enumerate(plan.steps, 1)]
            return LLMResponse(
                text=f"Here's my plan for “{plan.title}”:\n" + "\n".join(lines)
                     + "\nShould I go ahead? Say yes or no.",
                provider=KERNEL_PROVIDER,
                needs_approval=True,
                pending_tool={**action, "description": safety.describe_action(PLAN_TOOL, plan.summary())},
                trace=[planned, _step("decide", "Needs confirmation",
                                      f"Step {risky[0][0]} {risky[0][2].reason}")],
            )
        return await self._run_plan(plan, user=user, source=source, prompt=prompt, trace=[planned])

    async def _approved_plan(self, approved: dict[str, Any], held: dict[str, Any] | None, *,
                             user: Any, source: str, prompt: str) -> LLMResponse:
        """UI Approve for a plan: run the plan the kernel held, never a client-edited one."""
        approved_trace = [_step("decide", "Approved", "You approved the plan")]
        if held and held.get("tool") == PLAN_TOOL and isinstance(held.get("plan"), dict):
            plan = Plan.from_dict(held["plan"])
            self._learn_plan_approval(user, plan, True)
            return await self._run_plan(plan, user=user, source=source, prompt=prompt, trace=approved_trace)
        # The hold expired: rebuild from the plain commands, each re-understood.
        args = approved.get("arguments") or {}
        steps = []
        for command in args.get("steps") or []:
            found = steps_for_clause(str(command))
            if not found:
                return LLMResponse(text="That plan has expired — please ask me again.", provider=KERNEL_PROVIDER,
                                   trace=[_step("decide", "Expired", "The held plan expired")])
            steps.extend(found)
        plan = Plan(goal=str(args.get("goal") or prompt), title=str(args.get("title") or "your plan"),
                    source="approved", steps=steps)
        return await self._run_plan(plan, user=user, source=source, prompt=prompt, trace=approved_trace)

    async def _run_plan(self, plan: Plan, *, user: Any, source: str, prompt: str,
                        trace: list[dict[str, str]] | None = None) -> LLMResponse:
        """Run each step through safety and the tools, then check it worked."""
        key = self._user_key(user)
        steps_trace = list(trace or [])
        privileged = _is_privileged(user, source)
        total = len(plan.steps)
        await self._emit("plan.started", {"title": plan.title, "goal": plan.goal, "source": source,
                                          "user": key, "steps": [s.command for s in plan.steps]})
        tool_steps: list[dict[str, Any]] = []
        lines: list[str] = []
        for i, step in enumerate(plan.steps, 1):
            assessment = safety.assess(step.tool, step.arguments)
            phrase = safety.describe_action(step.tool, step.arguments)
            if assessment.needs_confirmation and not privileged:
                step.status, step.result = "skipped", f"only an admin can {phrase}"
                lines.append(f"Skipped: {phrase} (only an admin can do that).")
                steps_trace.append(_step("decide", f"Step {i}/{total} skipped", f"Admin only — {phrase}"))
                continue
            result = await self._execute(step.tool, dict(step.arguments))
            output = str(result.get("output") or result.get("error") or "")
            ok = bool(result.get("success")) and not looks_failed(output)
            check = None
            if ok:  # did the device really change? (the tool saying so isn't proof)
                verified, detail = await verify_step(step)
                step.verified = verified
                if verified is not None:
                    check = _step("check", "Checked" if verified else "Check failed", detail)
                if verified is False:
                    ok = False
                    output = f"{output} But when I checked, {detail}."
            step.status, step.result = ("done" if ok else "failed"), output
            self._learn_action(user, source, step.tool, step.arguments, ok)
            tool_steps.append({**result, "success": ok})
            lines.append(output if ok else f"Couldn't {phrase}: {output}")
            steps_trace.append(_step("act", f"Step {i}/{total}" if ok else f"Step {i}/{total} failed", output))
            if check:
                steps_trace.append(check)
            await self._emit("action.executed", {"tool": step.tool, "arguments": step.arguments, "success": ok,
                                                 "source": source, "user": key, "result": output[:500],
                                                 "plan": plan.title})
            await self._emit("plan.step", {"title": plan.title, "index": i, "total": total,
                                           "command": step.command, "success": ok, "user": key})
        done = sum(1 for s in plan.steps if s.status == "done")
        heading = (f"{plan.title} — all {total} steps done." if done == total
                   else f"{plan.title} — {done} of {total} steps done.")
        text = heading + "\n" + "\n".join(lines)
        if await self._remember(prompt or plan.goal, text):
            steps_trace.append(_step("remember", "Memory", "Saved to memory"))
        await self._emit("plan.completed", {"title": plan.title, "goal": plan.goal, "done": done, "total": total,
                                            "failed": sum(1 for s in plan.steps if s.status == "failed"),
                                            "user": key, "source": source})
        return LLMResponse(text=text, provider=KERNEL_PROVIDER, tool_steps=tool_steps, trace=steps_trace)

    async def _execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if isinstance(self.llm, AtulyaLLM) and self.llm.tools.get(tool) is not None:
            return await self.llm.run_tool({"tool": tool, "arguments": args})
        from atulya.kriya import execute_tool  # brains without the unified registry

        out = await execute_tool(tool, **args)
        failed = out.startswith("Error")
        return {"tool": tool, "arguments": args, "success": not failed,
                "output": "" if failed else out, "error": out if failed else ""}

    async def _publish_step(self, step: dict[str, Any], user: Any, source: str) -> None:
        """Publish a tool the brain ran natively, so triggers see it too."""
        self._learn_action(user, source, str(step.get("tool") or ""), step.get("arguments") or {},
                           bool(step.get("success")))
        await self._emit("action.executed", {
            "tool": step.get("tool"), "arguments": step.get("arguments") or {},
            "success": bool(step.get("success")), "source": source, "user": self._user_key(user),
            "result": str(step.get("output") or step.get("error") or "")[:500], "via": "brain",
        })

    async def _remember(self, prompt: str, text: str) -> bool:
        """Write to long-term memory; True when the brain actually keeps memory."""
        if isinstance(self.llm, AtulyaLLM) and self.llm.use_memory:
            try:
                await self.llm.remember(prompt, text)
                return True
            except Exception as exc:  # noqa: BLE001 - memory is best-effort
                logger.debug("kernel memory write failed: %s", exc)
        return False

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            await self.events.emit(event_type, payload)
        except Exception as exc:  # noqa: BLE001 - events are best-effort
            logger.debug("kernel event emit failed: %s", exc)

    def _hold(self, user: Any, action: dict[str, Any] | None, *, origin: str) -> None:
        if not action:
            return
        key = self._user_key(user)
        self._pending[key] = ({**action, "origin": action.get("origin", origin)}, time.monotonic())
        self._pending.move_to_end(key)
        while len(self._pending) > _MAX_PENDING:
            self._pending.popitem(last=False)

    @staticmethod
    def _user_key(user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("profile_user") or user.get("username") or "default")
        return str(user or "default")


def response_events(response: LLMResponse) -> list[LLMEvent]:
    """Render a finished response as the same event sequence the brain streams."""
    events = [LLMEvent("tool", metadata=step) for step in response.tool_steps]
    events += [LLMEvent("token", content=chunk) for chunk in _chunk_text(response.text)]
    meta: dict[str, Any] = {"provider": response.provider, "steps": response.tool_steps, "trace": response.trace}
    if response.needs_approval:
        pending = response.pending_tool or {}
        meta.update({"needs_approval": True, "pending_tool": pending,
                     "tool": pending.get("tool"), "tool_args": pending.get("arguments", {})})
    events.append(LLMEvent("done", metadata=meta))
    return events


_KERNELS: OrderedDict[int, tuple[Any, CognitiveKernel]] = OrderedDict()


def get_kernel(llm: Any = None) -> CognitiveKernel:
    """The kernel wrapping ``llm`` (default brain if None); one per brain instance."""
    llm = llm if llm is not None else get_default_llm()
    entry = _KERNELS.get(id(llm))
    if entry is not None and entry[0] is llm:
        return entry[1]
    kernel = CognitiveKernel(llm=llm)
    _KERNELS[id(llm)] = (llm, kernel)
    while len(_KERNELS) > 8:
        _KERNELS.popitem(last=False)
    return kernel

