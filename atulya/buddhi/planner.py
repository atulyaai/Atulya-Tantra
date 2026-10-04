"""Multi-step planning — goals become checked sequences of actions.

"Turn off the kitchen light" is one action; "get the house ready for guests" is
a goal. The planner turns a goal into a plan of concrete steps. The kernel then
runs every step through the same safety policy and tools as a single command,
and checks each one worked.

Where plans come from (first match wins):

1. **Routines** — named, editable step lists ("Guests are coming", "Good night",
   "I'm leaving", "Good morning"), started by their phrases or by
   "run the <name> routine".
2. **Device groups** — "turn off all the lights" becomes one step per light.
3. **Compound commands** — "turn off the kitchen light and lock the door" is
   split into clauses; every clause must be a clear command on its own.
4. **The brain** — for goal-like requests ("get ready for movie night") the
   language model proposes steps. Only steps the intent router understands are
   kept, so the model can't invent tools or arguments.

Safety is unchanged: a plan with a risky step (e.g. unlocking the door) asks
once for the whole plan, and a non-admin's risky steps are skipped.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from atulya.yantra.intent_router import _match_device, route_intent

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
    from atulya.yantra.tools import _HOME_DEVICES  # lazy: tools imports are heavy

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
class RoutineStore:
    """Named step lists, kept in ATULYA_ROUTINES_FILE (default kosh/agent/routines.json)."""

    def __init__(self, path: str | Path | None = None, seed_defaults: bool = True):
        self.path = Path(path or os.environ.get("ATULYA_ROUTINES_FILE", _DEFAULT_ROUTINES_FILE))
        if seed_defaults and not self.path.exists():
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
    from atulya.yantra.tools import _HOME_DEVICES

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

    from atulya.yantra.home_assistant import HomeAssistantBridge

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

    from atulya.yantra.tools import _HOME_DEVICES

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
