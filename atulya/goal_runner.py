"""A real plan -> act -> observe -> retry loop for multi-step goals (GOAL M9).

The runner never executes anything itself: every step goes through the shared
Toolbox, so the same permissions, the same approval queue and the same
receipts apply as for a normal chat. The plan comes from the model and is
checked against the tools that are really available before anything runs, so a
hallucinated tool name can never reach an action.

Steps and their receipts are stored, so the owner can ask what happened to a
goal and the answer comes from the record, not from the model's memory. A
restart never repeats a step that already ran.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

STEP_LIMIT = 8
# A step may be corrected once; after that the goal stops and says what failed.
MAX_RETRIES = 1

# The Toolbox answers a side-effecting call with this sentence and queues the approval.
APPROVAL_MARKER = "Approval requested"
# Answers that mean the step itself did not run.
FAILURE_MARKERS = ("is unavailable right now", "timed out", "Invalid input for",
                    "is not available", "failed to", "could not be")
# Answers that mean the step was refused on purpose: retrying would not help.
REFUSAL_MARKERS = ("Only the owner", "not permitted", "needs your approval", "forbidden")


class GoalError(RuntimeError):
    """The goal could not be started or continued."""


class GoalStore:
    """Durable goal and step timeline in SQLite."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "goals.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, goal TEXT NOT NULL,
                status TEXT NOT NULL, step_limit INTEGER NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, summary TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS goal_steps (
                goal_id TEXT NOT NULL, n INTEGER NOT NULL, tool TEXT NOT NULL,
                args TEXT NOT NULL, intent TEXT, status TEXT NOT NULL,
                action_id TEXT, receipt TEXT, started REAL, finished REAL,
                PRIMARY KEY(goal_id, n))""")
            db.execute("CREATE INDEX IF NOT EXISTS goals_owner ON goals(user_id, created)")

    def _db(self):
        return closing(sqlite3.connect(self.path, timeout=10))

    def create(self, user_id: str, goal: str, *, step_limit: int = STEP_LIMIT) -> str:
        if not user_id or not user_id.strip() or not goal.strip():
            raise ValueError("user_id and goal are required")
        if not 1 <= step_limit <= STEP_LIMIT:
            raise ValueError(f"step_limit must be between 1 and {STEP_LIMIT}")
        goal_id, now = uuid.uuid4().hex[:12], time.time()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("INSERT INTO goals VALUES(?,?,?,?,?,?,?,NULL)",
                       (goal_id, user_id, goal.strip()[:2000], "planning", step_limit, now, now))
        return goal_id

    def get(self, user_id: str, goal_id: str) -> dict:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM goals WHERE id=? AND user_id=?", (goal_id, user_id)).fetchone()
            if row is None:
                raise GoalError("That goal was not found for this account.")
            goal = dict(row)
            steps = db.execute("SELECT * FROM goal_steps WHERE goal_id=? ORDER BY n", (goal_id,)).fetchall()
        goal["steps"] = [{**dict(step), "args": json.loads(step["args"]),
                           "receipt": json.loads(step["receipt"]) if step["receipt"] else None}
                          for step in steps]
        return goal

    def list_for(self, user_id: str, limit: int = 10) -> list[dict]:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT id, goal, status, created, updated FROM goals "
                              "WHERE user_id=? ORDER BY created DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def set_plan(self, user_id: str, goal_id: str, steps: list[dict]) -> None:
        now = time.time()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("UPDATE goals SET status='running', updated=? WHERE id=? AND user_id=?",
                       (now, goal_id, user_id))
            db.execute("DELETE FROM goal_steps WHERE goal_id=?", (goal_id,))
            for number, step in enumerate(steps, 1):
                db.execute("INSERT INTO goal_steps VALUES(?,?,?,?,?,?,NULL,NULL,NULL,NULL)",
                           (goal_id, number, step["tool"], json.dumps(step.get("arguments") or {}),
                            step.get("intent", ""), "planned"))

    def start_step(self, user_id: str, goal_id: str, number: int) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("UPDATE goal_steps SET status='running', started=? WHERE goal_id=? AND n=? "
                       "AND status IN ('planned','failed')", (time.time(), goal_id, number))

    def finish_step(self, user_id: str, goal_id: str, number: int, *, status: str,
                    receipt: str = "", action_id: str | None = None) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("UPDATE goal_steps SET status=?, receipt=?, action_id=?, finished=? "
                       "WHERE goal_id=? AND n=?",
                       (status, json.dumps(receipt[:4000]), action_id, time.time(), goal_id, number))

    def finish(self, user_id: str, goal_id: str, *, status: str, summary: str) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("UPDATE goals SET status=?, summary=?, updated=? WHERE id=? AND user_id=?",
                       (status, summary[:2000], time.time(), goal_id, user_id))

    def recover(self, user_id: str) -> list[str]:
        """Mark steps that were running when the process stopped as interrupted."""
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            rows = db.execute("SELECT id FROM goals WHERE user_id=? AND status IN ('planning','running')",
                              (user_id,)).fetchall()
            ids = [row[0] for row in rows]
            for goal_id in ids:
                db.execute("UPDATE goal_steps SET status='interrupted' WHERE goal_id=? AND status='running'",
                           (goal_id,))
                db.execute("UPDATE goals SET status='interrupted', updated=? WHERE id=?",
                           (time.time(), goal_id))
        return ids


def parse_plan(text: str, allowed: set[str], limit: int = STEP_LIMIT) -> list[dict]:
    """Read a JSON plan out of the model's answer. Unknown tools are dropped.

    The model is not trusted with the list of tools it may use: anything it
    names that the caller does not have is removed before anything runs.
    """
    if not text:
        return []
    payload = _first_json(text)
    if payload is None:
        return []
    if isinstance(payload, list):
        raw_steps = payload
    elif isinstance(payload, dict):
        if payload.get("tool"):
            raw_steps = [payload]  # a single step, as asked for when a step is corrected
        else:
            raw_steps = payload.get("steps") or payload.get("plan") or []
    else:
        return []
    steps: list[dict] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            continue
        tool = str(raw.get("tool") or raw.get("name") or "").strip()
        if tool not in allowed:
            continue
        arguments = raw.get("arguments")
        if not isinstance(arguments, dict):
            arguments = raw.get("args") if isinstance(raw.get("args"), dict) else {}
        steps.append({"tool": tool, "arguments": arguments,
                      "intent": str(raw.get("intent") or raw.get("why") or "")[:200]})
        if len(steps) >= limit:
            break
    return steps


def _first_json(text: str):
    """The first JSON object or array in the text, even inside a code fence."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.S)
    candidates = [fenced.group(1)] if fenced else []
    candidates.extend(re.findall(r"(\{.*\}|\[.*\])", text, re.S))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def classify(receipt: str) -> str:
    """What a tool answer means: ok, needs approval, refused or failed."""
    lowered = (receipt or "").strip().lower()
    if lowered.startswith(APPROVAL_MARKER.lower()):
        return "waiting_approval"
    if any(marker.lower() in lowered for marker in REFUSAL_MARKERS):
        return "refused"
    if any(marker.lower() in lowered for marker in FAILURE_MARKERS):
        return "failed"
    return "ok"


class GoalRunner:
    """Plan, act, observe, retry - with every step's receipt on record."""

    def __init__(self, store: GoalStore, toolbox, model, *, step_limit: int = STEP_LIMIT):
        self.store = store
        self.toolbox = toolbox
        self.model = model
        self.step_limit = step_limit

    # -- prompts -----------------------------------------------------------
    def _plan_prompt(self, goal: str) -> str:
        schemas = json.dumps(self.toolbox.schemas)[:12000]
        return (f"Plan this goal with the tools listed below.\n\nGoal: {goal}\n\nTools: {schemas}\n\n"
                "Reply with JSON only, nothing else:\n"
                '{"steps": [{"tool": "tool_name", "arguments": {}, "intent": "why"}]}\n'
                f"Use at most {self.step_limit} steps, in the order they must happen. "
                "Do not include a step that changes something outside Atulya unless the goal needs it.")

    def _retry_prompt(self, goal: str, step: dict, receipt: str) -> str:
        return (f"Goal: {goal}\nThe step {step['tool']} did not work. Its answer was:\n{receipt[:800]}\n\n"
                "Reply with JSON only:\n"
                '{"tool": "tool_name", "arguments": {}, "intent": "why"}\n'
                "or, if it cannot be fixed:\n"
                '{"stop": "why it cannot be done"}')

    def _summary_prompt(self, goal: str, steps: list[dict], status: str) -> str:
        rows = "\n".join(f"{index}. {step['tool']} -> {step['status']}: {str(step.get('receipt') or '')[:300]}"
                         for index, step in enumerate(steps, 1))
        return (f"Goal: {goal}\nStatus: {status}\nStep results:\n{rows}\n\n"
                "Write 2-4 short sentences for the user: what is done, what still needs their approval "
                "and what failed. Claim only what the results show.")

    # -- running -----------------------------------------------------------
    async def run(self, user_id: str, goal: str) -> dict:
        """Plan and run a new goal."""
        goal_id = self.store.create(user_id, goal, step_limit=self.step_limit)
        return await self._drive(user_id, goal_id, goal)

    async def resume(self, user_id: str, goal_id: str) -> dict:
        """Continue a goal that stopped for the owner's approval."""
        goal = self.store.get(user_id, goal_id)
        if goal["status"] not in {"waiting_approval", "interrupted", "failed"}:
            raise GoalError(f"That goal is already {goal['status']}.")
        return await self._drive(user_id, goal_id, goal["goal"], existing=goal)

    async def _drive(self, user_id: str, goal_id: str, goal: str, existing: dict | None = None) -> dict:
        if existing and existing["steps"]:
            steps = [{"tool": step["tool"], "arguments": step["args"], "intent": step["intent"] or "",
                      "status": step["status"], "action_id": step["action_id"],
                      "receipt": step["receipt"]} for step in existing["steps"]]
        else:
            plan_text = await self._ask(self._plan_prompt(goal))
            allowed = {schema["function"]["name"] for schema in self.toolbox.schemas}
            steps = parse_plan(plan_text, allowed, self.step_limit)
            if not steps:
                message = ("I could not turn that goal into steps with the tools available here. "
                           "Nothing was run.")
                self.store.finish(user_id, goal_id, status="failed", summary=message)
                return {"id": goal_id, "status": "failed", "summary": message, "steps": []}
            self.store.set_plan(user_id, goal_id, steps)

        for index, step in enumerate(steps, 1):
            status = step.get("status", "planned")
            if status in {"succeeded", "approved"}:
                continue
            if status == "waiting_approval":
                if not self._approval_gone(step.get("action_id")):
                    return self._stop_for_approval(user_id, goal_id, goal, steps, index)
                # The owner approved it and the card ran the step: do not run it twice.
                step["status"] = "approved"
                step["receipt"] = step.get("receipt") or "Approved by the owner and executed."
                self.store.finish_step(user_id, goal_id, index, status="approved",
                                       receipt=step["receipt"])
                continue
            result = await self._run_step(user_id, goal_id, goal, steps, index, step)
            if result is not None:
                return result
        summary = await self._ask(self._summary_prompt(goal, steps, "succeeded"))
        self.store.finish(user_id, goal_id, status="succeeded", summary=summary)
        return {"id": goal_id, "status": "succeeded", "summary": summary, "steps": steps}

    async def _run_step(self, user_id: str, goal_id: str, goal: str,
                        steps: list[dict], index: int, step: dict):
        """Run one step. Returns a result when the goal must stop, else None."""
        attempts = 0
        while attempts <= MAX_RETRIES:
            attempts += 1
            self.store.start_step(user_id, goal_id, index)
            receipt = await self.toolbox.call(step["tool"], step["arguments"])
            verdict = classify(receipt)
            if verdict == "ok":
                step["status"] = "succeeded"
                step["receipt"] = receipt
                self.store.finish_step(user_id, goal_id, index, status="succeeded", receipt=receipt)
                return None
            if verdict == "waiting_approval":
                action_id = self._newest_action_id()
                step["status"] = "waiting_approval"
                step["receipt"] = receipt
                step["action_id"] = action_id
                self.store.finish_step(user_id, goal_id, index, status="waiting_approval",
                                       receipt=receipt, action_id=action_id)
                return self._stop_for_approval(user_id, goal_id, goal, steps, index)
            if verdict == "refused":
                step["status"] = "refused"
                step["receipt"] = receipt
                self.store.finish_step(user_id, goal_id, index, status="refused", receipt=receipt)
                summary = await self._ask(self._summary_prompt(goal, steps, "refused"))
                self.store.finish(user_id, goal_id, status="refused", summary=summary)
                return {"id": goal_id, "status": "refused", "summary": summary, "steps": steps}
            # failed: one correction from the model, then stop.
            step["status"] = "failed"
            step["receipt"] = receipt
            self.store.finish_step(user_id, goal_id, index, status="failed", receipt=receipt)
            if attempts > MAX_RETRIES:
                summary = await self._ask(self._summary_prompt(goal, steps, "failed"))
                self.store.finish(user_id, goal_id, status="failed", summary=summary)
                return {"id": goal_id, "status": "failed", "summary": summary, "steps": steps}
            fix_text = await self._ask(self._retry_prompt(goal, step, receipt))
            fixed = parse_plan(fix_text, {step["tool"]}, 1)
            if not fixed:
                summary = await self._ask(self._summary_prompt(goal, steps, "failed"))
                self.store.finish(user_id, goal_id, status="failed", summary=summary)
                return {"id": goal_id, "status": "failed", "summary": summary, "steps": steps}
            step["tool"] = fixed[0]["tool"]
            step["arguments"] = fixed[0]["arguments"]
        return None

    def _stop_for_approval(self, user_id: str, goal_id: str, goal: str,
                           steps: list[dict], index: int) -> dict:
        waiting = steps[index - 1]
        summary = (f"Step {index} of the goal needs your approval: {waiting['tool']}. "
                   "Approve it on screen, then ask me to continue the goal.")
        self.store.finish(user_id, goal_id, status="waiting_approval", summary=summary)
        return {"id": goal_id, "status": "waiting_approval", "summary": summary, "steps": steps}

    def _approval_gone(self, action_id: str | None) -> bool:
        """True when the approval card was taken (approved) instead of still waiting."""
        if not action_id:
            return False
        actions = getattr(self.toolbox.context, "actions", None)
        if actions is None:
            return False
        peek = getattr(getattr(actions, "queue", None), "peek", None)
        if peek is None:
            return False
        return peek(action_id) is None

    def _newest_action_id(self) -> str | None:
        actions = getattr(self.toolbox.context, "actions", None)
        created = list(getattr(actions, "created", []) or [])
        return created[-1].id if created else None

    async def _ask(self, prompt: str) -> str:
        try:
            answer = await self.model(prompt)
        except Exception:
            return ""
        return answer if isinstance(answer, str) else ""
