"""Plugin system with lifecycle hooks and SDK."""
from __future__ import annotations

import importlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class PluginState(Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class TrustLevel(Enum):
    VERIFIED = "verified"
    COMMUNITY = "community"
    UNTRUSTED = "untrusted"


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    state: PluginState = PluginState.DISCOVERED
    hooks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class PluginRegistry:
    def __init__(self, plugins_dir: str | Path = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, PluginInfo] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._discover()

    def _discover(self):
        manifest = self.plugins_dir / "plugins.json"
        if manifest.exists():
            data = json.loads(manifest.read_text())
            for p in data.get("plugins", []):
                info = PluginInfo(**p)
                self._plugins[info.name] = info

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {"name": p.name, "version": p.version, "description": p.description,
             "trust": p.trust_level.value, "state": p.state.value}
            for p in self._plugins.values()
        ]

    def status(self) -> dict[str, str]:
        return {name: p.state.value for name, p in self._plugins.items()}

    def register_hook(self, hook_name: str, callback: Callable):
        self._hooks.setdefault(hook_name, []).append(callback)

    async def run_hook(self, hook_name: str, **kwargs: Any):
        for callback in self._hooks.get(hook_name, []):
            try:
                await callback(**kwargs) if hasattr(callback, "__await__") else callback(**kwargs)
            except Exception as e:
                pass

    def scan_plugin(self, plugin_path: Path) -> dict[str, Any]:
        """Scan plugin for security before install."""
        result = {"safe": True, "warnings": [], "permissions": []}
        if not plugin_path.exists():
            result["safe"] = False
            result["warnings"].append("Plugin file not found")
            return result
        content = plugin_path.read_text()
        dangerous_patterns = ["os.system(", "subprocess.call(", "__import__('os'", "eval(", "exec("]
        for pattern in dangerous_patterns:
            if pattern in content:
                result["warnings"].append(f"Found dangerous pattern: {pattern}")
                result["safe"] = False
        return result
