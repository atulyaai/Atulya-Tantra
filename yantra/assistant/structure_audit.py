"""Repository structure audit for Atulya Tantra.

This guards the workspace against accidental root-folder sprawl and keeps
subfolders aligned with the ownership map.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ALLOWED_ROOT_DIRS = {
    "assets",
    "atulya",
    "config",
    "docs",
    "drishti",
    "tantra",
    "tests",
    "yantra",
    "tmp",
}

GENERATED_ROOT_DIRS = {
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
    "htmlcov",
    "repo_backups",
    "temp",
}

ALLOWED_ROOT_FILES = {
    ".env",
    ".env.example",
    ".gitignore",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "start.bat",
}

EXPECTED_PACKAGE_DIRS = {
    "atulya": {"docs", "memory", "observability"},
    "tantra": {"config", "core", "data", "npdna", "scripts", "training"},
    "yantra": {
        "assistant",
        "capabilities",
        "mcp",
        "notify",
        "plugins",
        "selfimprovement",
    },
    "drishti": {"dashboard", "frontend", "public"},
}

IGNORED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "dist"}


@dataclass
class StructureIssue:
    severity: str
    path: str
    message: str


@dataclass
class StructureAudit:
    status: str
    root_dirs: list[str] = field(default_factory=list)
    support_dirs: list[str] = field(default_factory=list)
    issues: list[StructureIssue] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class RepoStructureAuditor:
    """Validate root and package folder ownership."""

    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root)

    def run(self) -> dict[str, Any]:
        issues: list[StructureIssue] = []
        root_dirs: list[str] = []
        support_dirs: list[str] = []

        for child in self.repo_root.iterdir():
            name = child.name
            if child.is_dir():
                if name in ALLOWED_ROOT_DIRS:
                    root_dirs.append(name)
                    if name not in {"atulya", "tantra", "yantra", "drishti"}:
                        support_dirs.append(name)
                elif name in GENERATED_ROOT_DIRS:
                    issues.append(StructureIssue(
                        "warning",
                        name,
                        "Generated root directory should be cleaned or ignored.",
                    ))
                elif name == ".git":
                    continue
                else:
                    issues.append(StructureIssue(
                        "error",
                        name,
                        "Unexpected root directory. Move it under its owning package or document it.",
                    ))
            elif child.is_file() and name not in ALLOWED_ROOT_FILES:
                issues.append(StructureIssue(
                    "warning",
                    name,
                    "Unexpected root file. Keep root small and move support files into owner folders.",
                ))

        for package, expected in EXPECTED_PACKAGE_DIRS.items():
            pkg_path = self.repo_root / package
            if not pkg_path.exists():
                issues.append(StructureIssue("error", package, "Expected product package is missing."))
                continue
            for child in pkg_path.iterdir():
                if not child.is_dir() or child.name in IGNORED_DIR_NAMES:
                    continue
                if child.name not in expected:
                    issues.append(StructureIssue(
                        "warning",
                        str(child.relative_to(self.repo_root)),
                        f"Subfolder is not in the documented {package}/ ownership map.",
                    ))

        status = "clean" if not any(issue.severity == "error" for issue in issues) else "needs_fix"
        audit = StructureAudit(
            status=status,
            root_dirs=sorted(root_dirs),
            support_dirs=sorted(support_dirs),
            issues=issues,
        )
        return {
            "timestamp": audit.timestamp,
            "status": audit.status,
            "root_dirs": audit.root_dirs,
            "support_dirs": audit.support_dirs,
            "issues": [vars(issue) for issue in audit.issues],
            "next_actions": self._next_actions(audit.issues),
        }

    def write_report(self, output_path: str | Path = "tmp/structure_audit_report.json") -> Path:
        path = self.repo_root / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.run(), indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _next_actions(issues: list[StructureIssue]) -> list[str]:
        if not issues:
            return ["Structure is clean. Keep new code inside the owning package."]
        return [f"{issue.severity}: {issue.path} - {issue.message}" for issue in issues]


def run_structure_audit(repo_root: str | Path = ".") -> dict[str, Any]:
    return RepoStructureAuditor(repo_root).run()


def main() -> None:
    path = RepoStructureAuditor(".").write_report()
    print(path)


if __name__ == "__main__":
    main()
