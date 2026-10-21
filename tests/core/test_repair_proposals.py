import asyncio
import json
import time

import pytest

from atulya.maintenance import Maintenance


def test_skill_creation_needs_review_and_can_be_rolled_back(project_temp_dir):
    manager = Maintenance(project_temp_dir / "root", project_temp_dir / "data", project_temp_dir / "models")
    path = "tools/skills/check-status/SKILL.md"
    body = "---\nname: check-status\ndescription: Check the current service status.\n---\nCall maintenance_check.\n"
    proposal = manager.propose(path, body, "Add a reusable checked workflow")
    assert not (manager.root / path).exists()
    manager.apply(proposal["id"])
    assert (manager.root / path).read_text() == body
    manager.apply(proposal["id"], rollback=True)
    assert not (manager.root / path).exists()
    with pytest.raises(ValueError, match="name must match"):
        manager.propose(path, body.replace("check-status", "wrong-name"), "Invalid skill")


def test_automatic_proposals_are_opt_in_quiet_for_unchanged_faults_and_limited(project_temp_dir):
    manager = Maintenance(project_temp_dir, project_temp_dir / "data", project_temp_dir / "models")
    calls = []
    alerts = []
    async def propose(report):
        calls.append(report)
        return "Proposed a checked fix; not applied."
    manager.on_problem = propose
    async def notify(report, record):
        alerts.append(record["state"])
        return {"telegram_accepted": True, "push_accepted": 0}
    manager.on_notification = notify
    report = {"findings": [{"area": "webui", "message": "Syntax failed"}]}
    async def exercise():
        await manager.propose_new_problem(report)
        assert not calls
        manager.set_proactive(True)
        await manager.propose_new_problem(report)
        await manager.propose_new_problem(report)
        assert len(calls) == 1
        assert alerts == ["proposed_or_explained"]
        assert manager.proactive_status()["last_run"]["notifications"]["telegram_accepted"]
        changed = {"findings": [{"area": "webui", "message": "Another fault"}]}
        await manager.propose_new_problem(changed)
        assert len(calls) == 1
        last = json.loads(manager.proactive_path.read_text())
        last["at"] = time.time() - 3601
        manager.proactive_path.write_text(json.dumps(last))
        await manager.propose_new_problem(changed)
        assert len(calls) == 2
        assert len(alerts) == 2
        manager.set_proactive(False)
        await manager.propose_new_problem({"findings": [{"message": "Third"}]})
        assert len(calls) == 2
    asyncio.run(exercise())
