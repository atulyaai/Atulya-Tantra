"""Owner maintenance workspace. No setup changes, arbitrary commands, or core edits."""
from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

EDITABLE = frozenset({"webui/index.html", "webui/assistant.js", "webui/renderer.css",
                      "webui/controls.js", "webui/controls.css"})


class Maintenance:
    def __init__(self, root: Path, data_dir: Path, models_dir: Path):
        self.root = root.resolve()
        self.directory = data_dir / "maintenance"
        self.models_dir = models_dir
        self.lock = threading.Lock()
        self.last_check = {}
        self.on_problem = None
        self.policy_path = data_dir / "maintenance-policy.json"
        self.proactive_path = data_dir / "maintenance-proactive-status.json"

    def proactive_status(self) -> dict:
        try:
            policy = json.loads(self.policy_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            policy = {}
        try:
            last = json.loads(self.proactive_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last = {}
        return {"enabled": policy.get("enabled") is True, "last_run": last,
                "limit": "At most one AI proposal run per hour, only for changed findings. Never auto-applies changes."}

    def set_proactive(self, enabled: bool) -> dict:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be true or false")
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.policy_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"enabled": enabled}), encoding="utf-8")
        os.replace(temporary, self.policy_path)
        return self.proactive_status()

    async def propose_new_problem(self, report: dict) -> None:
        status = self.proactive_status()
        if not status["enabled"] or not self.on_problem or not report.get("findings"):
            return
        fingerprint = hashlib.sha256(json.dumps(report["findings"], sort_keys=True).encode()).hexdigest()
        last = status["last_run"]
        if fingerprint == last.get("fingerprint") or time.time() - float(last.get("at", 0)) < 3600:
            return
        record = {"at": time.time(), "fingerprint": fingerprint, "state": "running",
                  "checked_at": report.get("checked_at")}
        self.proactive_path.parent.mkdir(parents=True, exist_ok=True)
        self.proactive_path.write_text(json.dumps(record), encoding="utf-8")
        try:
            result = await asyncio.wait_for(self.on_problem(report), timeout=60)
            record.update(state="proposed_or_explained", result=str(result)[:4000])
        except Exception as exc:
            record.update(state="failed", result=f"Proposal run failed ({type(exc).__name__}); no changes applied.")
        self.proactive_path.write_text(json.dumps(record), encoding="utf-8")

    def path(self, name: str) -> Path:
        if name not in EDITABLE and not re.fullmatch(r"tools/skills/[a-z0-9][a-z0-9-]{0,63}/SKILL\.md", name):
            raise ValueError("This file is protected. Only permitted WebUI files and skill documents can be edited.")
        path = self.root / name
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError("Linked files or directories cannot be edited.")
        return path

    def read(self, name: str) -> dict:
        path = self.path(name)
        raw = path.read_bytes()
        if len(raw) > 300_000:
            raise ValueError("File is too large")
        return {"path": name, "content": raw.decode("utf-8"), "sha256": hashlib.sha256(raw).hexdigest()}

    def _proposal_path(self, proposal_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", proposal_id):
            raise ValueError("Invalid proposal ID")
        return self.directory / f"{proposal_id}.json"

    def propose(self, name: str, content: str, reason: str, *, expected_sha256: str | None = None) -> dict:
        with self.lock:
            path = self.path(name)
            current = self.read(name) if path.exists() else {"content": "", "sha256": None}
            if expected_sha256 is not None and current["sha256"] != expected_sha256:
                raise ValueError("File changed while preparing the patch; read it again")
            if not path.exists() and not name.startswith("tools/skills/"):
                raise ValueError("Only new skills can be created")
            if len(content.encode("utf-8")) > 300_000:
                raise ValueError("Proposed file is too large")
            self.directory.mkdir(parents=True, exist_ok=True)
            proposal_id = uuid4().hex
            check = "Manual browser review required"
            if name.startswith("tools/skills/"):
                slug = Path(name).parent.name
                if not content.startswith("---\n") or len(content.split("---", 2)) != 3:
                    raise ValueError("Skill needs YAML front matter with name and description")
                meta = content.split("---", 2)[1]
                if not re.search(r"^name:\s*" + re.escape(slug) + r"\s*$", meta, re.M):
                    raise ValueError("Skill name must match its directory")
                if not re.search(r"^description:\s*\S.+", meta, re.M):
                    raise ValueError("Skill description is required")
                check = "Skill structure passed; instructions grant no new permissions. Owner review required."
            if name.endswith(".js"):
                staged = self.directory / f"{proposal_id}.js"
                staged.write_text(content, encoding="utf-8")
                try:
                    result = subprocess.run(["node", "--check", str(staged)], capture_output=True,
                                            text=True, timeout=15)
                    if result.returncode:
                        raise ValueError("JavaScript syntax check failed; proposal was not saved")
                    check = "JavaScript syntax passed; browser review required"
                except FileNotFoundError as exc:
                    raise ValueError("Node is unavailable; cannot verify this proposal") from exc
                finally:
                    staged.unlink(missing_ok=True)
            proposal = {"id": proposal_id, "path": name, "reason": reason[:1000],
                        "before": current["content"], "before_sha256": current["sha256"],
                        "after": content, "check": check, "state": "proposed",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "diff": "".join(difflib.unified_diff(current["content"].splitlines(True),
                                         content.splitlines(True), fromfile=name, tofile=name))}
            self._save(proposal)
            return self.public(proposal)

    def _save(self, proposal: dict):
        target = self._proposal_path(proposal["id"])
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(proposal), encoding="utf-8")
        os.replace(temporary, target)

    @staticmethod
    def public(proposal: dict) -> dict:
        return {key: value for key, value in proposal.items() if key not in {"before", "after"}}

    def proposals(self) -> list[dict]:
        result = []
        for path in sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            result.append(self.public(json.loads(path.read_text(encoding="utf-8"))))
        return result

    def apply(self, proposal_id: str, *, rollback: bool = False) -> dict:
        with self.lock:
            proposal = json.loads(self._proposal_path(proposal_id).read_text(encoding="utf-8"))
            if proposal["state"] != ("applied" if rollback else "proposed"):
                raise ValueError("Proposal is no longer in the required state")
            path = self.path(proposal["path"])
            expected = hashlib.sha256(proposal["after"].encode("utf-8")).hexdigest() if rollback else proposal["before_sha256"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            if actual != expected:
                raise ValueError("File changed since review. Create a new proposal; nothing was overwritten.")
            if rollback and proposal["before_sha256"] is None:
                path.unlink()
                proposal["state"] = "rolled_back"
                self._save(proposal)
                return self.public(proposal)
            content = proposal["before"] if rollback else proposal["after"]
            path.parent.mkdir(parents=True, exist_ok=True)
            # Rollback preserves original file bytes including CRLF.
            temporary = path.with_name(path.name + "." + uuid4().hex + ".maintenance-tmp")
            try:
                with temporary.open("xb") as output:
                    output.write(content.encode("utf-8"))
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            proposal["state"] = "rolled_back" if rollback else "applied"
            self._save(proposal)
            return self.public(proposal)

    def search(self, name: str, query: str) -> dict:
        current = self.read(name)
        if not query or len(query) > 200:
            raise ValueError("Provide 1 to 200 search characters")
        matches = []
        for number, line in enumerate(current["content"].splitlines(), 1):
            if query.lower() in line.lower():
                matches.append({"line": number, "text": line[:300]})
                if len(matches) >= 8:
                    break
        return {"path": name, "matches": matches, "sha256": current["sha256"]}

    def patch(self, name: str, old: str, new: str, reason: str) -> dict:
        current = self.read(name)
        if not old or current["content"].count(old) != 1:
            raise ValueError("The old text must match exactly once; read the file and supply a unique block")
        return self.propose(name, current["content"].replace(old, new, 1), reason, expected_sha256=current["sha256"])

    def check(self) -> dict:
        from tools.bootstrap import MEDIAPIPE_FILES
        missing = [name for name in MEDIAPIPE_FILES if not
                   (self.models_dir / "runtime" / "mediapipe" / name).is_file()]
        findings = []
        if missing:
            findings.append({"area": "gesture", "message": "Gesture runtime files are missing", "files": missing})
        if not (self.models_dir / "gesture" / "gesture_recognizer.task").is_file():
            findings.append({"area": "gesture", "message": "Gesture model is missing"})
        for name in ("webui/assistant.js", "webui/controls.js"):
            try:
                result = subprocess.run(["node", "--check", str(self.path(name))],
                                        capture_output=True, timeout=15)
                if result.returncode:
                    findings.append({"area": "webui", "message": f"Syntax check failed: {name}"})
            except FileNotFoundError:
                findings.append({"area": "verification", "message": "Node unavailable: WebUI syntax not checked"})
                break
        self.last_check = {"checked_at": datetime.now(timezone.utc).isoformat(), "findings": findings,
                           "editable_files": sorted(EDITABLE),
                           "skill_policy": "New or existing tools/skills/<slug>/SKILL.md can be proposed and reviewed. Skills grant no new tool permissions.",
                           "policy": "Owner only. Propose and review before applying. Setup and core files are protected."}
        return self.last_check

    async def monitor(self):
        while True:
            try:
                await asyncio.to_thread(self.check)
                await self.propose_new_problem(self.last_check)
            except Exception:
                self.last_check = {"findings": [{"area": "monitor", "message": "Check could not finish"}]}
            await asyncio.sleep(300)


async def maintenance_read(args, ctx):
    if ctx is None or ctx.maintenance is None:
        return "Maintenance is available to the signed-in owner only."
    result = await asyncio.to_thread(ctx.maintenance.read, str(args.get("path", "")))
    offset = max(0, int(args.get("offset", 0)))
    result["total_characters"] = len(result["content"])
    result["content"] = result["content"][offset:offset + 2500]
    result["next_offset"] = offset + len(result["content"])
    return json.dumps(result)


async def maintenance_check(args, ctx):
    if ctx is None or ctx.maintenance is None:
        return "Maintenance is available to the signed-in owner only."
    return json.dumps(await asyncio.to_thread(ctx.maintenance.check))


async def maintenance_propose(args, ctx):
    if ctx is None or ctx.maintenance is None:
        return "Maintenance is available to the signed-in owner only."
    result = await asyncio.to_thread(ctx.maintenance.propose, str(args.get("path", "")),
                                    str(args.get("content", "")), str(args.get("reason", "")))
    return f"Saved proposal {result['id']}. {result['check']}. Review its diff in Maintenance. No live file changed."


async def maintenance_search(args, ctx):
    if ctx is None or ctx.maintenance is None:
        return "Maintenance is available to the signed-in owner only."
    return json.dumps(await asyncio.to_thread(ctx.maintenance.search, str(args.get("path", "")), str(args.get("query", ""))))


async def maintenance_patch(args, ctx):
    if ctx is None or ctx.maintenance is None:
        return "Maintenance is available to the signed-in owner only."
    result = await asyncio.to_thread(ctx.maintenance.patch, str(args.get("path", "")),
                                    str(args.get("old", "")), str(args.get("new", "")), str(args.get("reason", "")))
    return f"Saved patch proposal {result['id']}. {result['check']}. Review its diff in Maintenance. No live file changed."


async def maintenance_set_proactive(args, ctx):
    if ctx is None or ctx.maintenance is None:
        return "Maintenance is available to the signed-in owner only."
    result = await asyncio.to_thread(ctx.maintenance.set_proactive, args.get("enabled"))
    return f"Automatic AI repair proposals {'enabled' if result['enabled'] else 'disabled'}. No automatic application; owner review remains required."
