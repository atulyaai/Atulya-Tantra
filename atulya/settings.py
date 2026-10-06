"""Settings: settings, .env reading, the data folder move, text helpers, safe maths, the event bus and the heartbeat."""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import math
import operator
import os
import re
import shutil
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable


# ── layout ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AtulyaConfig:
    root_dir: Path
    data_dir: Path
    model_dir: Path
    logs_dir: Path
    config_path: Path | None = None

    @classmethod
    def load(
        cls,
        root_dir: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> "AtulyaConfig":
        root = Path(root_dir or os.environ.get("ATULYA_ROOT", Path.cwd())).resolve()
        path = Path(config_path or os.environ.get("ATULYA_CONFIG", root / "config.json"))
        values: dict[str, Any] = {}
        if path.exists():
            try:
                values = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                values = {}

        def resolve(name: str, default: str) -> Path:
            env_name = f"ATULYA_{name.upper()}"
            raw = os.environ.get(env_name, values.get(name, default))
            candidate = Path(raw)
            return candidate if candidate.is_absolute() else root / candidate

        return cls(
            root_dir=root,
            data_dir=resolve("data_dir", "data"),
            model_dir=resolve("model_dir", "data/models"),
            logs_dir=resolve("logs_dir", "data/logs"),
            config_path=path if path.exists() else None,
        )


def get_config() -> AtulyaConfig:
    return AtulyaConfig.load()


# ── environment ────────────────────────────────────────────────────────────
def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value[:1] in ("'", '"') and value.count(value[0]) >= 2:
            value = value[1:value.index(value[0], 1)]
        else:
            value = value.split(" #", 1)[0].strip()
        if key:
            values[key] = value
    return values


def load_env(paths: list[Path] | None = None) -> list[Path]:
    """Load the first-found values from each file; returns the files that were read."""
    root = Path(__file__).resolve().parents[1]
    read: list[Path] = []
    for path in paths or [root / ".env", Path.cwd() / ".env"]:
        try:
            values = parse_env(path.read_text(encoding="utf-8-sig"))
        except OSError:
            continue
        read.append(path)
        for key, value in values.items():
            if value and not os.environ.get(key):
                os.environ[key] = value
    return read


def env_path() -> Path:
    """The .env that Atulya writes to: the one next to start.bat."""
    return Path(__file__).resolve().parents[1] / ".env"


def set_env_value(key: str, value: str, path: Path | None = None) -> None:
    """Set (or, with an empty value, remove) one variable in .env and in this running process."""
    if not key.replace("_", "").isalnum() or any(c in value for c in "\r\n\0"):
        raise ValueError("Invalid key or value")
    path = path or env_path()
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        name = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if "=" in line and not line.lstrip().startswith("#") and name == key:
            if value and not done:
                out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if value and not done:
        out.append(f"{key}={value}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)  # keys: readable by you only (a no-op on Windows)
    except OSError:
        pass
    tmp.replace(path)
    if value:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)


# ── data ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


def migrate(root: str | Path = ".") -> str:
    """Move ``<root>/kosh`` to ``<root>/data`` if only the old one exists. Returns what happened, for logging and tests.

    ``data`` is the folder's current name; ``kosh`` is what installs made
    before this release called it. A folder that already is ``data`` is left
    alone, so this is safe to run every start.
    """
    root = Path(root)
    old, new = root / "kosh", root / "data"
    if not old.is_dir() or new.exists():
        return "nothing to do"
    try:
        old.rename(new)
        return "moved kosh to data"
    except OSError:  # e.g. a file inside is open on Windows: copy instead, and leave the old folder as a backup
        try:
            shutil.copytree(old, new)
            logger.warning("Copied your data folder to data. You can delete the old kosh folder when you are sure.")
            return "copied kosh to data"
        except OSError as exc:
            logger.warning("Could not move kosh to data (%s). Close other Atulya windows and start again.", exc)
            return "failed"


def migrate_all() -> list[str]:
    """Run :func:`migrate` for the folder you started Atulya from and for the project folder (they are usually the same)."""
    roots = {Path.cwd().resolve(), Path(__file__).resolve().parents[1]}
    return [migrate(r) for r in sorted(roots)]


# ── text ────────────────────────────────────────────────────────────
# Emoji, pictographs, dingbats, flags, skin tones, variation selectors and joiners.
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoticons, symbols, transport, supplemental pictographs
    "\U00002600-\U000027BF"   # misc symbols and dingbats
    "\U00002B00-\U00002BFF"   # arrows and stars
    "\U00002300-\U000023FF"   # misc technical (watch, hourglass...)
    "\U0001F1E6-\U0001F1FF"   # flags
    "\uFE0E\uFE0F\u200D\u20E3"  # variation selectors, zero-width joiner, keycap
    "]+"
)


def strip_emoji(text: str) -> str:
    """Remove emoji so a voice never reads out "smiling face with smiling eyes"."""
    cleaned = _EMOJI.sub("", text or "")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


# ── maths ────────────────────────────────────────────────────────────
class SafeExpressionError(ValueError):
    """Raised when an expression uses unsupported syntax or values."""


_BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

def _safe_pow(base: Any, exp: Any, mod: Any = None) -> Any:
    if not isinstance(exp, (int, float)):
        raise SafeExpressionError("exponent must be a number")
    if mod is not None:
        return pow(base, exp, mod)
    return pow(base, exp)


_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": _safe_pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
}

_CONSTANTS = {"pi": math.pi, "e": math.e}


def safe_math_eval(expression: str) -> Any:
    """Evaluate a restricted arithmetic expression."""

    if len(expression) > 512:
        raise SafeExpressionError("expression is too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SafeExpressionError("invalid expression") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise SafeExpressionError("only numeric literals are allowed")

    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise SafeExpressionError(f"unknown name: {node.id}")

    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise SafeExpressionError("operator is not allowed")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise SafeExpressionError("exponent is too large")
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise SafeExpressionError("operator is not allowed")
        return op(_eval_node(node.operand))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise SafeExpressionError("only named math functions are allowed")
        func = _FUNCTIONS.get(node.func.id)
        if func is None:
            raise SafeExpressionError(f"function is not allowed: {node.func.id}")
        if node.keywords:
            raise SafeExpressionError("keyword arguments are not allowed")
        args = [_eval_node(arg) for arg in node.args]
        return func(*args)

    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(elt) for elt in node.elts]

    raise SafeExpressionError(f"syntax is not allowed: {type(node).__name__}")


# ── events ────────────────────────────────────────────────────────────
_MAX_HISTORY = 1000


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> Event:
        event = Event(event_type, payload or {})
        with self._lock:
            self._history.append(event)
            if len(self._history) > _MAX_HISTORY:
                self._history = self._history[-_MAX_HISTORY:]
        handlers = [*self._subscribers.get(event_type, []), *self._subscribers.get("*", [])]
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("Handler %s failed for event %s: %s", handler, event_type, e)
        return event

    def history(self, limit: int = 100) -> list[Event]:
        with self._lock:
            return list(self._history[-limit:])


default_bus = EventBus()


# ── heartbeat ────────────────────────────────────────────────────────────
@dataclass
class HealthCheck:
    name: str
    status: str = "ok"
    message: str = ""
    timestamp: float = field(default_factory=time.time)


class HeartbeatSystem:
    def __init__(self, data_dir: str | Path = "data", events: Any = None, interval: float | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._checks: list[HealthCheck] = []
        self._running = False
        self._interval = float(interval or os.environ.get("ATULYA_HEARTBEAT_INTERVAL", "300"))
        # Optional event bus: status *changes* are published as health.<status>.
        self.events = events
        self._last_status: dict[str, str] = {}

    async def start(self):
        self._running = True
        while self._running:
            await self._run_checks()
            await asyncio.sleep(self._interval)

    async def stop(self):
        self._running = False

    async def _run_checks(self):
        self._checks = [
            await self._memory_check(),
            await self._disk_check(),
            await self._task_check(),
            await self._maintenance_check(),
            await self._provider_check(),
        ]
        self._save_status()
        await self._publish_changes()

    async def _publish_changes(self) -> None:
        """Emit health.<status> only when a check changes state (edge-triggered),
        so a persistent warning alerts once instead of every interval. The
        first run publishes only non-ok states."""
        if self.events is None:
            return
        for check in self._checks:
            previous = self._last_status.get(check.name)
            self._last_status[check.name] = check.status
            if previous == check.status or (previous is None and check.status in ("ok", "info")):
                continue
            try:
                await self.events.emit(f"health.{check.status}", {
                    "check": check.name,
                    "status": check.status,
                    "message": check.message,
                    "previous": previous or "",
                })
            except Exception as exc:  # noqa: BLE001 - monitoring must never crash
                logger.debug("heartbeat event emit failed: %s", exc)

    async def _memory_check(self) -> HealthCheck:
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                return HealthCheck("memory", "warning", f"Memory usage: {mem.percent}%")
            return HealthCheck("memory", "ok", f"Memory usage: {mem.percent}%")
        except ImportError:
            return HealthCheck("memory", "ok", "psutil not available")

    async def _disk_check(self) -> HealthCheck:
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.data_dir)
            usage_pct = (used / total) * 100
            if usage_pct > 90:
                return HealthCheck("disk", "warning", f"Disk usage: {usage_pct:.1f}%")
            return HealthCheck("disk", "ok", f"Disk usage: {usage_pct:.1f}%")
        except Exception as e:
            return HealthCheck("disk", "error", str(e))

    async def _provider_check(self) -> HealthCheck:
        try:
            # Reuse the live brain's router rather than building (and possibly
            # re-downloading a model for) a new one every interval.
            from atulya.brain import get_default_llm
            router = get_default_llm().router
            available = [p.name() for p in router.providers if p.is_available()]
            if not available:
                return HealthCheck("provider", "warning", "No intelligence providers are available")
            return HealthCheck("provider", "ok", f"Available providers: {', '.join(available)}")
        except Exception as e:
            return HealthCheck("provider", "warning", str(e))


    async def _task_check(self) -> HealthCheck:
        """Check for pending tasks from Kanban system."""
        try:
            kanban_dir = self.data_dir / "kanban"
            pending = 0
            if kanban_dir.exists():
                for f in kanban_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    for task in data.get("tasks", {}).values():
                        if task.get("status") in ["todo", "in_progress"]:
                            pending += 1
            if pending > 0:
                return HealthCheck("tasks", "info", f"{pending} pending tasks")
            return HealthCheck("tasks", "ok", "No pending tasks")
        except Exception:
            return HealthCheck("tasks", "ok", "No task system")

    async def _maintenance_check(self) -> HealthCheck:
        """Check if maintenance is needed (log cleanup, memory compaction, etc.)."""
        issues = []
        # Check log size
        logs_dir = self.data_dir / "logs"
        if logs_dir.exists():
            log_size = sum(f.stat().st_size for f in logs_dir.glob("*.log"))
            if log_size > 100 * 1024 * 1024:  # 100MB
                issues.append(f"Logs: {log_size / 1024 / 1024:.1f}MB")

        # Check memory DB size
        memory_dir = self.data_dir / "memory"
        if memory_dir.exists():
            db_size = sum(f.stat().st_size for f in memory_dir.glob("*.db"))
            if db_size > 500 * 1024 * 1024:  # 500MB
                issues.append(f"Memory DB: {db_size / 1024 / 1024:.1f}MB")

        if issues:
            return HealthCheck("maintenance", "warning", "; ".join(issues))
        return HealthCheck("maintenance", "ok", "Maintenance complete")

    def _save_status(self):
        status_file = self.data_dir / "heartbeat_status.json"
        status_file.write_text(json.dumps({
            "last_check": time.time(),
            "checks": [{"name": c.name, "status": c.status, "message": c.message} for c in self._checks],
        }, indent=2), encoding="utf-8")

    def get_status(self) -> dict[str, Any]:
        status_file = self.data_dir / "heartbeat_status.json"
        if status_file.exists():
            return json.loads(status_file.read_text(encoding="utf-8"))
        return {"last_check": 0, "checks": []}

