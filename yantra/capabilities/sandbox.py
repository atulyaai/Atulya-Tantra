from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "find", "grep", "sort", "uniq",
    "echo", "date", "pwd", "which", "python", "python3", "node", "npm",
    "git", "curl", "wget", "pip", "pip3",
}

_BLOCKED_PATTERNS = [
    "rm -rf /", "mkfs", "dd if=", "> /dev/", ":(){ :|:& };:",
    "chmod 777 /", "sudo", "su ", "passwd",
]


class ToolSandbox:
    def __init__(self, workdir: str | Path | None = None, timeout: int = 60):
        self.workdir = Path(workdir or tempfile.mkdtemp(prefix="atulya_sandbox_"))
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._env = os.environ.copy()
        self._env["ATULYA_SANDBOX"] = "1"

    def check_command(self, command: str) -> tuple[bool, str]:
        cmd = shlex.split(command)
        if not cmd:
            return False, "Empty command"
        base = os.path.basename(cmd[0]).lower()
        if base not in _ALLOWED_COMMANDS and base not in ("cmd", "powershell"):
            return False, f"Command '{base}' not in allowed list"
        for pattern in _BLOCKED_PATTERNS:
            if pattern in command.lower():
                return False, f"Command blocked by safety pattern"
        return True, ""

    def run(self, command: str, cwd: str | Path | None = None) -> dict[str, Any]:
        allowed, reason = self.check_command(command)
        if not allowed:
            return {"success": False, "error": reason, "stdout": "", "stderr": ""}
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd or self.workdir,
                env=self._env,
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {self.timeout}s", "stdout": "", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}

    def cleanup(self):
        import shutil
        try:
            shutil.rmtree(self.workdir, ignore_errors=True)
        except Exception as e:
            logger.warning("Sandbox cleanup failed: %s", e)
