"""Self-Repair System — auto-fix bugs, evolve architecture, self-healing code."""
from __future__ import annotations

import ast
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RepairAction:
    id: str
    issue_type: str
    description: str
    file_path: str
    line_number: int = 0
    fix_applied: bool = False
    fix_description: str = ""
    timestamp: float = field(default_factory=time.time)


class SelfRepairSystem:
    """Self-repairing code system — detects and fixes issues automatically."""

    def __init__(self, data_dir: str | Path = "data/selfrepair"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._repair_log: list[RepairAction] = []
        self._error_patterns: dict[str, str] = {}
        self._load()

    def _load(self):
        state_file = self.data_dir / "selfrepair_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            self._error_patterns = data.get("error_patterns", {})

    def _save(self):
        state_file = self.data_dir / "selfrepair_state.json"
        data = {"error_patterns": self._error_patterns, "repair_count": len(self._repair_log)}
        state_file.write_text(json.dumps(data, indent=2))

    def analyze_error(self, error: Exception, tb: traceback.StackSummary | None = None) -> RepairAction:
        """Analyze an error and determine fix."""
        error_type = type(error).__name__
        error_msg = str(error)

        # Pattern matching for common errors
        fix = self._get_fix(error_type, error_msg)
        action = RepairAction(
            id=f"repair_{int(time.time())}",
            issue_type=error_type,
            description=f"{error_type}: {error_msg}",
            file_path=tb[0].filename if tb else "",
            line_number=tb[0].lineno if tb else 0,
            fix_description=fix,
        )
        self._repair_log.append(action)
        self._save()
        return action

    def _get_fix(self, error_type: str, error_msg: str) -> str:
        """Get fix suggestion based on error pattern."""
        fixes = {
            "ModuleNotFoundError": "Install missing module: pip install <module_name>",
            "ImportError": "Check import statement and module availability",
            "FileNotFoundError": "Create missing file or check path",
            "KeyError": "Add key existence check before access",
            "IndexError": "Add bounds check before list access",
            "TypeError": "Add type checking or conversion",
            "ValueError": "Add input validation",
            "AttributeError": "Check object type before attribute access",
            "SyntaxError": "Fix syntax error in code",
            "IndentationError": "Fix indentation in code",
            "NameError": "Define variable before use or check spelling",
            "ZeroDivisionError": "Add zero check before division",
            "ConnectionError": "Add retry logic with exponential backoff",
            "TimeoutError": "Increase timeout or add retry logic",
            "MemoryError": "Reduce batch size or add memory optimization",
            "PermissionError": "Check file permissions or run with elevated privileges",
        }
        return fixes.get(error_type, f"Investigate {error_type}: {error_msg}")

    def apply_fix(self, file_path: str, fix_description: str) -> bool:
        """Apply a fix to a file."""
        try:
            path = Path(file_path)
            if not path.exists():
                return False
            content = path.read_text()
            # Apply common fixes
            if "ModuleNotFoundError" in fix_description:
                # Add import at top if missing
                module = fix_description.split("pip install ")[-1]
                if f"import {module}" not in content:
                    content = f"import {module}\n" + content
                    path.write_text(content)
                    return True
            elif "KeyError" in fix_description:
                # Add .get() instead of direct access
                content = content.replace("[key]", ".get(key, None)")
                path.write_text(content)
                return True
            elif "IndexError" in fix_description:
                # Add bounds check
                content = content.replace("list[i]", "list[i] if i < len(list) else None")
                path.write_text(content)
                return True
        except Exception as e:
            logger.error(f"Failed to apply fix: {e}")
        return False

    def evolve_architecture(self, current_config: dict[str, Any]) -> dict[str, Any]:
        """Evolve architecture based on performance metrics."""
        evolved = dict(current_config)

        # Auto-scale based on usage
        if current_config.get("strand_load", 0) > 0.9:
            evolved["num_strands"] = current_config.get("num_strands", 4) + 2
        if current_config.get("memory_usage", 0) > 0.8:
            evolved["context_window"] = max(128, current_config.get("context_window", 256) // 2)
        if current_config.get("error_rate", 0) > 0.1:
            evolved["temperature"] = max(0.1, current_config.get("temperature", 0.7) - 0.1)

        return evolved

    def get_repair_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return [vars(r) for r in self._repair_log[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        by_type = {}
        for r in self._repair_log:
            by_type[r.issue_type] = by_type.get(r.issue_type, 0) + 1
        return {"total_repairs": len(self._repair_log), "by_type": by_type}


class CodeEvolver:
    """Self-evolving code — modifies its own codebase safely."""

    def __init__(self, base_dir: str | Path = "."):
        self.base_dir = Path(base_dir)
        self._evolution_log: list[dict[str, Any]] = []

    def propose_change(self, file_path: str, old_code: str, new_code: str, reason: str) -> dict[str, Any]:
        """Propose a code change."""
        proposal = {
            "id": f"evolve_{int(time.time())}",
            "file": file_path,
            "old_code": old_code[:200],
            "new_code": new_code[:200],
            "reason": reason,
            "timestamp": time.time(),
            "approved": False,
        }
        self._evolution_log.append(proposal)
        return proposal

    def apply_change(self, proposal_id: str) -> bool:
        """Apply an approved code change."""
        for proposal in self._evolution_log:
            if proposal["id"] == proposal_id and proposal.get("approved"):
                path = self.base_dir / proposal["file"]
                if path.exists():
                    path.write_text(proposal["new_code"])
                    return True
        return False

    def get_stats(self) -> dict[str, Any]:
        return {"proposals": len(self._evolution_log), "approved": sum(1 for p in self._evolution_log if p.get("approved"))}
