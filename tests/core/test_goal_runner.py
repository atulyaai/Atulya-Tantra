"""A real plan -> act -> observe -> retry loop, with every step on record (GOAL M9)."""
import asyncio
import json

import pytest

from atulya.goal_runner import GoalError, GoalRunner, GoalStore, classify, parse_plan
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import TOOLS, Toolbox


class Box:
    """A toolbox stand-in that records calls and can be told to fail or need approval."""

    def __init__(self, answers=None, schemas=None):
        self.answers = answers or {}
        self.calls = []
        self.schemas = schemas or [{"function": {"name": "get_weather", "parameters": {}}},
                                   {"function": {"name": "create_reminder", "parameters": {}}}]
        self.context = PluginContext("web", None, None, "alice")

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        answer = self.answers.get(name, f"{name} done")
        if callable(answer):
            return answer(name, arguments)
        return answer


def model(answers):
    """A model that replies with the given answers in order."""
    replies = list(answers)

    async def ask(prompt):
        return replies.pop(0) if replies else ""
    return ask


def test_plan_only_keeps_tools_that_exist():
    plan = json.dumps({"steps": [
        {"tool": "get_weather", "arguments": {"when": "tomorrow"}, "intent": "the forecast"},
        {"tool": "rm_rf", "arguments": {}},
        {"tool": "create_reminder", "arguments": {"text": "check"}}]})
    steps = parse_plan(plan, {"get_weather", "create_reminder"})
    assert [step["tool"] for step in steps] == ["get_weather", "create_reminder"]
    assert steps[0]["arguments"] == {"when": "tomorrow"}


def test_plan_is_bounded_by_the_step_limit():
    plan = json.dumps({"steps": [{"tool": "get_weather", "arguments": {}}] * 20})
    assert len(parse_plan(plan, {"get_weather"}, limit=3)) == 3


def test_plan_survives_a_fenced_or_chatty_answer():
    answer = "Sure! Here is the plan:\n```json\n{\"steps\": [{\"tool\": \"get_weather\", \"arguments\": {}}]}\n```\nDone."
    assert parse_plan(answer, {"get_weather"})[0]["tool"] == "get_weather"


@pytest.mark.parametrize("receipt,expected", [
    ("Weather: 24 degrees", "ok"),
    ("Approval requested: 'Send the message'. It has NOT run yet.", "waiting_approval"),
    ("Only the owner can control the smart home.", "refused"),
    ("get_weather timed out.", "failed"),
])
def test_receipts_are_classified(receipt, expected):
    assert classify(receipt) == expected


def test_a_goal_runs_every_step_and_keeps_the_receipts(project_temp_dir):
    box = Box()
    runner = GoalRunner(GoalStore(project_temp_dir), box, model([
        json.dumps({"steps": [{"tool": "get_weather", "arguments": {"when": "tomorrow"}},
                              {"tool": "create_reminder", "arguments": {"text": "check"}}]}),
        "The forecast is ready and the reminder is set."]))
    result = asyncio.run(runner.run("alice", "What is the weather tomorrow and remind me to check"))
    assert result["status"] == "succeeded"
    assert [call[0] for call in box.calls] == ["get_weather", "create_reminder"]
    stored = GoalStore(project_temp_dir).get("alice", result["id"])
    assert [step["status"] for step in stored["steps"]] == ["succeeded", "succeeded"]
    assert stored["steps"][0]["receipt"] == "get_weather done"
    assert stored["summary"] == "The forecast is ready and the reminder is set."


def test_a_failing_step_is_corrected_once_and_then_reported(project_temp_dir):
    attempts = []

    def weather(name, arguments):
        attempts.append(arguments)
        return "get_weather timed out." if len(attempts) == 1 else "Weather: 24 degrees"

    box = Box({"get_weather": weather})
    runner = GoalRunner(GoalStore(project_temp_dir), box, model([
        json.dumps({"steps": [{"tool": "get_weather", "arguments": {"when": "today"}}]}),
        json.dumps({"tool": "get_weather", "arguments": {"when": "tomorrow"}}),
        "It works now."]))
    result = asyncio.run(runner.run("alice", "What is the weather"))
    assert result["status"] == "succeeded"
    assert attempts == [{"when": "today"}, {"when": "tomorrow"}]


def test_a_step_that_keeps_failing_stops_the_goal(project_temp_dir):
    box = Box({"get_weather": "get_weather timed out."})
    runner = GoalRunner(GoalStore(project_temp_dir), box, model([
        json.dumps({"steps": [{"tool": "get_weather", "arguments": {}}]}),
        json.dumps({"tool": "get_weather", "arguments": {}}),
        "The weather service did not answer."]))
    result = asyncio.run(runner.run("alice", "What is the weather"))
    assert result["status"] == "failed"
    assert "did not answer" in result["summary"]
    stored = GoalStore(project_temp_dir).get("alice", result["id"])
    assert stored["steps"][0]["status"] == "failed"


def test_a_step_that_needs_approval_stops_and_says_so(project_temp_dir):
    box = Box({"create_reminder": "Approval requested: 'Set a reminder'. It has NOT run yet."})
    runner = GoalRunner(GoalStore(project_temp_dir), box, model([
        json.dumps({"steps": [{"tool": "create_reminder", "arguments": {"text": "check"}}]}),
        "The reminder needs your approval."]))
    result = asyncio.run(runner.run("alice", "Remind me to check"))
    assert result["status"] == "waiting_approval"
    assert "needs your approval" in result["summary"]
    assert "create_reminder" in result["summary"]
    # Nothing was executed: the step is waiting for the owner, not done.
    stored = GoalStore(project_temp_dir).get("alice", result["id"])
    assert stored["steps"][0]["status"] == "waiting_approval"


def test_a_goal_with_no_usable_plan_runs_nothing(project_temp_dir):
    box = Box()
    runner = GoalRunner(GoalStore(project_temp_dir), box, model(["I cannot do that with these tools."]))
    result = asyncio.run(runner.run("alice", "Do something impossible"))
    assert result["status"] == "failed"
    assert box.calls == []
    assert "Nothing was run" in result["summary"]


def test_a_goal_cannot_nest_another_goal(project_temp_dir):
    box = Box(schemas=[{"function": {"name": "run_goal", "parameters": {}}},
                        {"function": {"name": "get_weather", "parameters": {}}}])
    runner = GoalRunner(GoalStore(project_temp_dir), box, model([
        json.dumps({"steps": [{"tool": "run_goal", "arguments": {"goal": "again"}}]}),
        "Nothing was run."]))
    result = asyncio.run(runner.run("alice", "Do the thing"))
    assert result["status"] == "failed"
    assert box.calls == []


def test_goals_are_scoped_to_the_account(project_temp_dir):
    store = GoalStore(project_temp_dir)
    goal_id = store.create("alice", "Do the thing")
    with pytest.raises(GoalError):
        store.get("bob", goal_id)
    assert store.list_for("bob") == []


def test_a_restart_marks_an_unfinished_goal_as_interrupted(project_temp_dir):
    store = GoalStore(project_temp_dir)
    goal_id = store.create("alice", "Do the thing")
    store.set_plan("alice", goal_id, [{"tool": "get_weather", "arguments": {}, "intent": "weather"}])
    store.start_step("alice", goal_id, 1)
    assert store.recover("alice") == [goal_id]
    goal = store.get("alice", goal_id)
    assert goal["status"] == "interrupted"
    assert goal["steps"][0]["status"] == "interrupted"


def test_the_goal_tool_needs_a_runner_on_the_context(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    box = Toolbox(TOOLS, PluginContext("web", None, None, "alice"))
    answer = asyncio.run(box.call("run_goal", {"goal": "do the thing"}))
    assert "not available" in answer


def test_the_run_goal_tool_plans_runs_and_records_the_goal(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    answers = iter([json.dumps({"steps": [{"tool": "get_time", "arguments": {}}]}),
                    "The time is on record."])

    async def agent(prompt):
        return next(answers, "")

    box = Toolbox(TOOLS, PluginContext("web", None, None, "alice", agent=agent))
    answer = asyncio.run(box.call("run_goal", {"goal": "What time is it?"}))
    assert "succeeded" in answer and "The time is on record." in answer
    listed = asyncio.run(box.call("goal_timeline", {}))
    assert "What time is it?" in listed
    goal_id = answer.split("Goal ", 1)[1].split(" ", 1)[0]
    detail = asyncio.run(box.call("goal_timeline", {"goal_id": goal_id}))
    assert "get_time" in detail and "succeeded" in detail
