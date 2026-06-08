"""Product alignment audit for Atulya Tantra.

The audit keeps the project honest against the current product direction:
Atulya as personality/memory, Tantra as support and compatibility layer,
Yantra as action layer, Drishti as the mobile/desktop live experience, and
custom LLM/model work in a separate repository.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AlignmentTarget:
    name: str
    required_terms: tuple[str, ...]
    files: tuple[str, ...]
    weight: int = 1


@dataclass
class AlignmentFinding:
    target: str
    status: str
    score: float
    present_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    note: str = ""


DEFAULT_TARGETS = (
    AlignmentTarget(
        name="Atulya identity and memory",
        required_terms=("personality", "memory", "identity", "assistant brain"),
        files=("README.md", "atulya/docs/PROJECT_MAP.md", "atulya/identity.py", "atulya/memory"),
        weight=2,
    ),
    AlignmentTarget(
        name="Tantra support and model-repo boundary",
        required_terms=("security", "context", "compatibility", "provider", "separate model repo"),
        files=("README.md", "tantra/README.md", "tantra/core"),
        weight=2,
    ),
    AlignmentTarget(
        name="Yantra action automation",
        required_terms=("automation", "browser", "device", "voice", "dispatch"),
        files=("README.md", "yantra/capabilities", "yantra/dispatch.py", "yantra/device_controller.py"),
        weight=3,
    ),
    AlignmentTarget(
        name="Drishti live mobile experience",
        required_terms=("mobile", "voice", "camera", "Live Mode", "PWA"),
        files=("README.md", "drishti/frontend/src/main.jsx", "drishti/public/manifest.webmanifest"),
        weight=3,
    ),
    AlignmentTarget(
        name="Provider and agent fallback",
        required_terms=("OpenAI", "Gemini", "OpenRouter", "Ollama", "OpenCode"),
        files=("README.md", "tantra/core/model_failover.py"),
        weight=1,
    ),
)


class ProductAlignmentAuditor:
    """Scan repo text for alignment with the agreed product direction."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        targets: tuple[AlignmentTarget, ...] = DEFAULT_TARGETS,
    ):
        self.repo_root = Path(repo_root)
        self.targets = targets

    def run(self) -> dict[str, Any]:
        findings = [self._check_target(target) for target in self.targets]
        weighted_total = sum(target.weight for target in self.targets)
        weighted_score = 0.0
        for target, finding in zip(self.targets, findings):
            weighted_score += finding.score * target.weight

        score = round(weighted_score / max(1, weighted_total), 3)
        blockers = [
            f"{finding.target}: missing {', '.join(finding.missing_terms)}"
            for finding in findings
            if finding.status != "aligned"
        ]
        return {
            "timestamp": time.time(),
            "score": score,
            "status": "aligned" if score >= 0.8 and not blockers else "needs_attention",
            "findings": [vars(finding) for finding in findings],
            "blockers": blockers,
            "next_actions": self._next_actions(findings),
        }

    def write_report(self, output_path: str | Path = "tmp/product_alignment_report.json") -> Path:
        path = self.repo_root / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.run(), indent=2), encoding="utf-8")
        return path

    def _check_target(self, target: AlignmentTarget) -> AlignmentFinding:
        corpus = self._read_files(target.files)
        lower = corpus.lower()
        present = [term for term in target.required_terms if term.lower() in lower]
        missing = [term for term in target.required_terms if term.lower() not in lower]
        score = len(present) / max(1, len(target.required_terms))
        status = "aligned" if not missing else "partial" if present else "missing"
        return AlignmentFinding(
            target=target.name,
            status=status,
            score=round(score, 3),
            present_terms=present,
            missing_terms=missing,
            note=self._note_for(target.name, missing),
        )

    def _read_files(self, paths: tuple[str, ...]) -> str:
        chunks: list[str] = []
        for rel in paths:
            path = self.repo_root / rel
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file() and child.suffix.lower() in {".py", ".md", ".jsx", ".js", ".json"}:
                        chunks.append(self._safe_read(child))
            elif path.is_file():
                chunks.append(self._safe_read(path))
        return "\n".join(chunks)

    @staticmethod
    def _safe_read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    @staticmethod
    def _note_for(name: str, missing: list[str]) -> str:
        if not missing:
            return "Direction is represented in README and code."
        if "Drishti" in name:
            return "Live interface exists, but missing terms show where the visible experience may drift."
        if "Yantra" in name:
            return "Action layer should be wired through dispatch and real tool execution."
        return "Documentation or implementation should be updated to keep this pillar explicit."

    @staticmethod
    def _next_actions(findings: list[AlignmentFinding]) -> list[str]:
        actions: list[str] = []
        for finding in findings:
            if finding.missing_terms:
                actions.append(
                    f"Update {finding.target} for: {', '.join(finding.missing_terms)}"
                )
        if not actions:
            actions.append("Keep building Drishti Live Mode and route real actions through Yantra.")
        return actions


def run_alignment_audit(repo_root: str | Path = ".") -> dict[str, Any]:
    return ProductAlignmentAuditor(repo_root).run()


def main() -> None:
    path = ProductAlignmentAuditor(".").write_report()
    print(path)


if __name__ == "__main__":
    main()
