"""Unified tool system with 20+ tools."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._duplicate_names: set[str] = set()

    def register(self, tool: Tool):
        if tool.name in self._tools:
            self._duplicate_names.add(tool.name)
        self._tools[tool.name] = tool

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {name}")
        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def filter_tools(self, categories: list[str]) -> list[Tool]:
        return [t for t in self._tools.values() if any(c in t.name for c in categories)]

    def duplicate_names(self) -> list[str]:
        return sorted(self._duplicate_names)


class FileReadTool(Tool):
    name = "file_read"
    description = "Read file contents"
    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        try:
            content = Path(path).read_text()
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to file"
    async def execute(self, path: str, content: str, **kwargs: Any) -> ToolResult:
        try:
            Path(path).write_text(content)
            return ToolResult(success=True, output=f"Written {len(content)} bytes")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileEditTool(Tool):
    name = "file_edit"
    description = "Edit file with search/replace"
    async def execute(self, path: str, old: str, new: str, **kwargs: Any) -> ToolResult:
        try:
            content = Path(path).read_text()
            if old not in content:
                return ToolResult(success=False, error="Search string not found")
            content = content.replace(old, new)
            Path(path).write_text(content)
            return ToolResult(success=True, output="File edited")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileSearchTool(Tool):
    name = "file_search"
    description = "Search for files by pattern"
    async def execute(self, pattern: str, path: str = ".", **kwargs: Any) -> ToolResult:
        try:
            matches = list(Path(path).glob(pattern))
            return ToolResult(success=True, output="\n".join(str(m) for m in matches))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GrepTool(Tool):
    name = "grep"
    description = "Search file contents with regex"
    async def execute(self, pattern: str, path: str = ".", max_file_size: int = 1_048_576, **kwargs: Any) -> ToolResult:
        try:
            results = []
            for f in Path(path).rglob("*"):
                if f.is_file():
                    try:
                        if f.stat().st_size > max_file_size:
                            continue
                        content = f.read_text()
                        if re.search(pattern, content):
                            results.append(str(f))
                    except Exception:
                        pass
            return ToolResult(success=True, output="\n".join(results))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ExecTool(Tool):
    name = "exec"
    description = "Execute a shell command"
    async def execute(self, command: str, allow_exec: bool = False, allow_list: list[str] | None = None, **kwargs: Any) -> ToolResult:
        if not allow_exec:
            return ToolResult(success=False, error="Execution requires allow_exec=True and RiskLevel.CRITICAL approval")
        from tantra.core.security import ApprovalSystem, RiskLevel
        approval = ApprovalSystem()
        if approval.requires_approval(command, level=RiskLevel.CRITICAL):
            return ToolResult(success=False, error="Command rejected by approval system")
        allowed = allow_list or os.environ.get("ATULYA_EXEC_ALLOWLIST", "").split(",")
        allowed = [item.strip() for item in allowed if item.strip()]
        try:
            executable = shlex.split(command, posix=False)[0].lower()
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        if not allowed or executable not in {item.lower() for item in allowed}:
            return ToolResult(success=False, error=f"Command not allow-listed: {executable}")
        try:
            cmd_list = shlex.split(command, posix=False)
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
            return ToolResult(success=result.returncode == 0, output=result.stdout, error=result.stderr)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web"
    async def execute(self, query: str, **kwargs: Any) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(query, max_results=5)
            return ToolResult(success=True, output=json.dumps(results, indent=2))
        except ImportError:
            return ToolResult(success=False, error="duckduckgo_search not installed")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch URL content"
    async def execute(self, url: str, **kwargs: Any) -> ToolResult:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                return ToolResult(success=True, output=resp.read().decode()[:5000])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class TodoCreateTool(Tool):
    name = "todo_create"
    description = "Create a todo item"
    async def execute(self, text: str, **kwargs: Any) -> ToolResult:
        todos_file = Path(kwargs.get("data_dir", ".")) / "todos.json"
        todos = []
        if todos_file.exists():
            todos = json.loads(todos_file.read_text())
        todos.append({"id": str(len(todos)+1), "text": text, "done": False, "created": time.time()})
        todos_file.write_text(json.dumps(todos, indent=2))
        return ToolResult(success=True, output=f"Created todo #{len(todos)}")


class TodoListTool(Tool):
    name = "todo_list"
    description = "List todos"
    async def execute(self, **kwargs: Any) -> ToolResult:
        todos_file = Path(kwargs.get("data_dir", ".")) / "todos.json"
        if not todos_file.exists():
            return ToolResult(success=True, output="No todos")
        todos = json.loads(todos_file.read_text())
        return ToolResult(success=True, output=json.dumps(todos, indent=2))


_DEFAULT_MEMORY_DIR = Path.home() / ".atulya" / "memory"

class MemoryStoreTool(Tool):
    name = "memory_store"
    description = "Store a memory note"
    async def execute(self, content: str, tags: str = "", **kwargs: Any) -> ToolResult:
        memory_dir = Path(kwargs.get("data_dir") or os.environ.get("ATULYA_DATA_DIR") or _DEFAULT_MEMORY_DIR)
        memory_dir.mkdir(parents=True, exist_ok=True)
        entry = {"id": str(int(time.time())), "content": content, "tags": tags.split(",") if tags else [], "created": time.time()}
        (memory_dir / f"{entry['id']}.json").write_text(json.dumps(entry))
        return ToolResult(success=True, output=f"Stored memory {entry['id']}")


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search memory notes"
    async def execute(self, query: str, **kwargs: Any) -> ToolResult:
        memory_dir = Path(kwargs.get("data_dir") or os.environ.get("ATULYA_DATA_DIR") or _DEFAULT_MEMORY_DIR)
        results = []
        if memory_dir.exists():
            for f in memory_dir.glob("*.json"):
                data = json.loads(f.read_text())
                if query.lower() in data.get("content", "").lower():
                    results.append(data)
        return ToolResult(success=True, output=json.dumps(results, indent=2))


def create_default_registry(data_dir: str | Path = ".") -> ToolRegistry:
    from yantra.capabilities.business_automation import (
        HRAttendancePayrollTool,
        DataScrubberTool,
        GSTReconciliationTool,
        AccountingERPTool,
        SAPAutomationTool
    )
    from yantra.capabilities.office_tools import (
        CalendarTool,
        CSVAnalyzeTool,
        ChartGenerateTool,
        CodeExecuteTool,
        EmailDraftTool,
        PDFReadTool,
    )
    registry = ToolRegistry()
    for tool_class in [FileReadTool, FileWriteTool, FileEditTool, FileSearchTool, GrepTool,
                       ExecTool, WebSearchTool, WebFetchTool, TodoCreateTool, TodoListTool,
                       MemoryStoreTool, MemorySearchTool, HRAttendancePayrollTool,
                       DataScrubberTool, GSTReconciliationTool, AccountingERPTool,
                       SAPAutomationTool, CodeExecuteTool, PDFReadTool, CSVAnalyzeTool,
                       CalendarTool, EmailDraftTool, ChartGenerateTool]:
        registry.register(tool_class())
    return registry
