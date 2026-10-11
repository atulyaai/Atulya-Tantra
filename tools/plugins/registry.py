"""Manifest-backed registry for deterministic assistant command plugins."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Dependencies and authenticated principal for one command dispatch."""

    owner_id: str
    memory: object
    calendar: object
    user_id: str = "admin"
    # Approval queue for side-effecting tools (WebUI only); None disables them.
    actions: object | None = None
    # Searchable chat archive for this principal; None disables past-chat recall.
    history: object | None = None


CommandHandler = Callable[[str, PluginContext], Awaitable[str | None]]


class PluginExecutionError(RuntimeError):
    """A plugin failed; callers should return a safe channel-specific message."""


@dataclass(frozen=True, slots=True)
class Plugin:
    manifest: dict
    handler: CommandHandler


class PluginRegistry:
    """Dispatch exact supported command patterns to explicitly registered plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._enabled: set[str] = set()

    def register(self, manifest_path: Path, handler: CommandHandler) -> None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {"id", "name", "version", "category", "commands", "permissions", "enabled"}
        if not isinstance(manifest, dict) or not required.issubset(manifest):
            raise ValueError(f"Invalid plugin manifest: {manifest_path.name}")
        if not isinstance(manifest["enabled"], bool):
            raise ValueError(f"Invalid plugin enabled state: {manifest_path.name}")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", str(manifest["id"])):
            raise ValueError(f"Invalid plugin id: {manifest_path.name}")
        if not isinstance(manifest["commands"], list) or not all(isinstance(item, str) for item in manifest["commands"]):
            raise ValueError(f"Invalid plugin commands: {manifest_path.name}")
        if not isinstance(manifest["permissions"], list) or not all(
            isinstance(item, str) for item in manifest["permissions"]
        ):
            raise ValueError(f"Invalid plugin permissions: {manifest_path.name}")
        if manifest["id"] in self._plugins:
            raise ValueError(f"Duplicate plugin id: {manifest['id']}")
        plugin_id = manifest["id"]
        self._plugins[plugin_id] = Plugin(manifest, handler)
        if manifest["enabled"]:
            self._enabled.add(plugin_id)

    async def dispatch(self, text: str, context: PluginContext) -> str | None:
        command = text.strip()
        if not command:
            return None
        for plugin_id, plugin in self._plugins.items():
            if plugin_id not in self._enabled:
                continue
            try:
                result = await plugin.handler(command, context)
            except Exception as exc:
                raise PluginExecutionError(plugin.manifest["id"]) from exc
            if result is not None:
                return result
        return None

    @property
    def manifests(self) -> list[dict]:
        return [dict(plugin.manifest, enabled=plugin_id in self._enabled)
                for plugin_id, plugin in self._plugins.items()]

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        if plugin_id not in self._plugins:
            raise ValueError("Unknown built-in plugin")
        if not isinstance(enabled, bool):
            raise ValueError("Plugin state must be boolean")
        if enabled:
            self._enabled.add(plugin_id)
        else:
            self._enabled.discard(plugin_id)


def build_default_registry() -> PluginRegistry:
    """Register shipped built-ins explicitly; no filesystem auto-execution."""
    from tools.plugins.information.commands import handle as information
    from tools.plugins.personal.commands import handle as personal
    from tools.plugins.productivity.commands import handle as productivity
    from tools.plugins.system.commands import handle as system
    from tools.plugins.utilities.commands import handle as utilities

    root = Path(__file__).parent
    registry = PluginRegistry()
    for relative, handler in (
        ("personal/plugin.json", personal),
        ("system/plugin.json", system),
        ("productivity/plugin.json", productivity),
        ("information/plugin.json", information),
        ("utilities/plugin.json", utilities),
    ):
        registry.register(root / relative, handler)
    return registry
