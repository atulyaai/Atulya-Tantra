"""ECC-inspired harness layer for Yantra agents, skills, commands, and safety."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tantra.core.security import PromptInjectionGuard, RiskLevel
from yantra.capabilities import ToolRegistry, create_default_registry
from yantra.dispatch import DispatchResult, Dispatcher
from yantra.events import EventBus, default_bus


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    tool_name: str = ""
    risk: RiskLevel = RiskLevel.LOW
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    skill_name: str
    default_args: dict[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()


@dataclass
class SafetyDecision:
    allowed: bool
    risk: RiskLevel
    reason: str = ""
    sanitized_prompt: str = ""


class SafetyPolicy:
    """Small approval gate for harness commands before they touch tools."""

    _dangerous_patterns = (
        r"\brm\s+-rf\b",
        r"\bremove-item\b.*\b-recurse\b",
        r"\bformat\b",
        r"\bshutdown\b",
        r"\bdel\b.*\*",
        r"\bdrop\s+table\b",
        r"\bdelete\s+from\b",
    )

    def __init__(self):
        self.injection_guard = PromptInjectionGuard()

    def assess(self, command: CommandSpec, prompt: str, kwargs: dict[str, Any]) -> SafetyDecision:
        text = " ".join([prompt, command.name, str(kwargs)])
        sanitized = (
            self.injection_guard.sanitize(prompt)
            if self.injection_guard.detect(prompt)
            else prompt
        )
        for pattern in self._dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return SafetyDecision(
                    allowed=False,
                    risk=RiskLevel.CRITICAL,
                    reason="Dangerous filesystem, shell, or database action blocked",
                    sanitized_prompt=sanitized,
                )
        if command.name in {"exec", "file_write", "file_edit"} or command.skill_name in {
            "run_shell",
            "write_file",
            "edit_file",
        }:
            return SafetyDecision(
                allowed=False,
                risk=RiskLevel.HIGH,
                reason="High-risk command requires an explicit lower-level approval path",
                sanitized_prompt=sanitized,
            )
        return SafetyDecision(
            allowed=True,
            risk=command_risk(command),
            sanitized_prompt=sanitized,
        )


def command_risk(command: CommandSpec) -> RiskLevel:
    if command.name in {"backup", "scan_project", "search_memory", "remember"}:
        return RiskLevel.LOW
    if command.name in {"fix_error", "run_tests", "research"}:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class HarnessRegistry:
    """Canonical registry that de-duplicates agents, skills, commands, and tools."""

    def __init__(self):
        self.agents: dict[str, AgentSpec] = {}
        self.skills: dict[str, SkillSpec] = {}
        self.commands: dict[str, CommandSpec] = {}
        self.aliases: dict[str, str] = {}

    def register_agent(self, spec: AgentSpec) -> None:
        self.agents.setdefault(spec.name, spec)

    def register_skill(self, spec: SkillSpec) -> None:
        canonical = self.skills.setdefault(spec.name, spec)
        for alias in (*canonical.aliases, *spec.aliases):
            self.aliases.setdefault(alias, canonical.name)

    def register_command(self, spec: CommandSpec) -> None:
        canonical = self.commands.setdefault(spec.name, spec)
        for alias in (*canonical.aliases, *spec.aliases):
            self.aliases.setdefault(alias, canonical.name)

    def resolve_command(self, name: str) -> CommandSpec | None:
        resolved = self.aliases.get(name, name)
        return self.commands.get(resolved)

    def duplicate_report(self, tools: ToolRegistry | None = None) -> dict[str, list[str]]:
        report: dict[str, list[str]] = {
            "agent_aliases": [],
            "skill_aliases": [],
            "command_aliases": [],
            "tool_names": [],
        }
        for alias, canonical in self.aliases.items():
            if alias in self.agents and alias != canonical:
                report["agent_aliases"].append(alias)
            if alias in self.skills and alias != canonical:
                report["skill_aliases"].append(alias)
            if alias in self.commands and alias != canonical:
                report["command_aliases"].append(alias)
        if tools:
            duplicate_names = getattr(tools, "duplicate_names", None)
            if callable(duplicate_names):
                report["tool_names"] = duplicate_names()
        return report


def create_default_harness_registry() -> HarnessRegistry:
    registry = HarnessRegistry()

    for agent in (
        AgentSpec("planner", "Break goals into executable steps", ("plan_task", "create_workflow")),
        AgentSpec("coder", "Make code changes and run checks", ("read_file", "edit_file", "run_tests")),
        AgentSpec("researcher", "Search and synthesize external or local knowledge", ("research",)),
        AgentSpec("memory_manager", "Store and retrieve useful long-term context", ("remember", "search_memory")),
        AgentSpec("safety_checker", "Block risky commands and prompt injection", ("safety_review",)),
        AgentSpec("self_improvement", "Turn failures into reusable learning", ("learn_from_output",)),
        AgentSpec("automation_operator", "Run browser, business, device, and MCP automations", ("run_workflow",)),
    ):
        registry.register_agent(agent)

    for skill in (
        SkillSpec("read_file", "Read a local file", "file_read", aliases=("inspect_file",)),
        SkillSpec("write_file", "Write a local file", "file_write", RiskLevel.HIGH),
        SkillSpec("edit_file", "Edit a local file", "file_edit", RiskLevel.HIGH),
        SkillSpec("search_files", "Search local files", "file_search", aliases=("find_file",)),
        SkillSpec("grep_code", "Search file contents", "grep", aliases=("scan_project",)),
        SkillSpec("run_shell", "Run an allow-listed shell command", "exec", RiskLevel.CRITICAL),
        SkillSpec("research", "Search the web", "web_search"),
        SkillSpec("remember", "Store a memory note", "memory_store"),
        SkillSpec("search_memory", "Search memory notes", "memory_search"),
        SkillSpec("create_todo", "Create a todo item", "todo_create"),
        SkillSpec("list_todos", "List todo items", "todo_list"),
        SkillSpec("data_scrub", "Clean duplicate or messy CSV rows", "data_scrub"),
        SkillSpec("payroll", "Compute attendance payroll", "hr_attendance_payroll"),
        SkillSpec("gst_reconcile", "Reconcile GST registers", "gst_reconcile"),
        SkillSpec("invoice", "Generate an invoice", "accounting_invoice"),
        SkillSpec("sap_workflow", "Run a SAP workflow recipe", "sap_gui_automation"),
        SkillSpec("execute_code", "Run a small Python snippet in a temp sandbox", "code_execute", RiskLevel.HIGH),
        SkillSpec("read_pdf", "Read text from a local PDF", "pdf_read"),
        SkillSpec("analyze_csv", "Analyze CSV rows and numeric columns", "csv_analyze"),
        SkillSpec("calendar_event", "Create a local calendar event", "calendar"),
        SkillSpec("email_draft", "Create a local email draft without sending", "email"),
        SkillSpec("chart", "Generate a local SVG chart", "chart_generate"),
    ):
        registry.register_skill(skill)

    for command in (
        CommandSpec("/scan-project", "Search project files", "grep_code", aliases=("scan",)),
        CommandSpec("/remember", "Store useful context", "remember"),
        CommandSpec("/recall", "Search stored context", "search_memory", aliases=("memory",)),
        CommandSpec("/research", "Search the web", "research"),
        CommandSpec("/todo", "Create a todo item", "create_todo"),
        CommandSpec("/todos", "List todo items", "list_todos"),
        CommandSpec("/scrub-data", "Clean CSV rows and remove duplicates", "data_scrub"),
        CommandSpec("/payroll", "Run payroll calculation", "payroll"),
        CommandSpec("/gst", "Run GST reconciliation", "gst_reconcile"),
        CommandSpec("/invoice", "Generate an invoice", "invoice"),
        CommandSpec("/sap", "Run a SAP automation recipe", "sap_workflow"),
        CommandSpec("/code", "Execute a Python snippet", "execute_code"),
        CommandSpec("/pdf", "Read a PDF", "read_pdf"),
        CommandSpec("/csv", "Analyze a CSV", "analyze_csv"),
        CommandSpec("/calendar", "Create a calendar entry", "calendar_event"),
        CommandSpec("/email", "Draft an email", "email_draft"),
        CommandSpec("/chart", "Generate a chart", "chart"),
    ):
        registry.register_command(command)

    return registry


class YantraHarness:
    """High-level command surface that routes canonical commands into existing tools."""

    def __init__(
        self,
        data_dir: str | Path = ".",
        tools: ToolRegistry | None = None,
        events: EventBus | None = None,
        registry: HarnessRegistry | None = None,
        safety: SafetyPolicy | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.tools = tools or create_default_registry(data_dir)
        self.events = events or default_bus
        self.registry = registry or create_default_harness_registry()
        self.safety = safety or SafetyPolicy()
        self.dispatcher = Dispatcher(tools=self.tools, events=self.events)

    async def run(self, command_name: str, prompt: str = "", **kwargs: Any) -> DispatchResult:
        command = self.registry.resolve_command(command_name)
        if not command:
            result = await self.tools.execute(command_name, **kwargs)
            return DispatchResult(
                classification=self.dispatcher.classifier.classify(prompt or command_name),
                tool_result=result,
                model="",
                metadata={"command": command_name, "resolved": False},
            )

        decision = self.safety.assess(command, prompt, kwargs)
        if not decision.allowed:
            from yantra.capabilities import ToolResult

            return DispatchResult(
                classification=self.dispatcher.classifier.classify(prompt or command.name),
                tool_result=ToolResult(success=False, error=decision.reason),
                model="",
                metadata={
                    "command": command.name,
                    "risk": decision.risk.value,
                    "blocked": True,
                },
            )

        skill = self.registry.skills[command.skill_name]
        tool_args = {**command.default_args, **kwargs, "data_dir": str(self.data_dir)}
        return await self.dispatcher.dispatch(
            decision.sanitized_prompt or prompt or command.description,
            tool_name=skill.tool_name,
            **tool_args,
        )

    def report_duplicates(self) -> dict[str, list[str]]:
        return self.registry.duplicate_report(self.tools)

    def catalog(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "agents": [vars(agent) for agent in self.registry.agents.values()],
            "skills": [vars(skill) for skill in self.registry.skills.values()],
            "commands": [vars(command) for command in self.registry.commands.values()],
        }
