"""Plugin system with lifecycle hooks and SDK."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


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
                if isinstance(p.get("trust_level"), str):
                    p["trust_level"] = TrustLevel(p["trust_level"])
                if isinstance(p.get("state"), str):
                    p["state"] = PluginState(p["state"])
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
                result = callback(**kwargs)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error("Hook '%s' callback %s failed: %s", hook_name, getattr(callback, "__name__", callback), e)

    def scan_plugin(self, plugin_path: Path) -> dict[str, Any]:
        """Scan plugin for security before install."""
        result = {"safe": True, "warnings": [], "permissions": []}
        if not plugin_path.exists():
            result["safe"] = False
            result["warnings"].append("Plugin file not found")
            return result
        content = plugin_path.read_text()
        dangerous_patterns = ["os.system(", "subprocess.call(", "eval(", "exec(", "compile(", "execfile("]
        for pattern in dangerous_patterns:
            if pattern in content:
                result["warnings"].append(f"Found dangerous pattern: {pattern}")
                result["safe"] = False
        return result

    def install_skill(self, skill_path: str | Path) -> PluginInfo:
        """Install a local SKILL.md-style skill as metadata only."""
        path = Path(skill_path)
        if path.is_dir():
            path = path / "SKILL.md"
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")
        text = path.read_text(encoding="utf-8")
        name = _extract_heading(text) or path.parent.name or path.stem
        description = _extract_description(text)
        info = PluginInfo(
            name=name,
            version="0.1.0",
            description=description,
            author="local",
            trust_level=TrustLevel.COMMUNITY,
            state=PluginState.LOADED,
            hooks=["skill"],
            tools=[],
        )
        self._plugins[info.name] = info
        self._save_manifest()
        return info

    def get_skill(self, name: str) -> PluginInfo | None:
        """Get a plugin/skill by name."""
        return self._plugins.get(name)

    def enable_skill(self, name: str) -> bool:
        """Set a plugin state to ACTIVE."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        plugin.state = PluginState.ACTIVE
        self._save_manifest()
        return True

    def disable_skill(self, name: str) -> bool:
        """Set a plugin state to DISABLED."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        plugin.state = PluginState.DISABLED
        self._save_manifest()
        return True

    def uninstall_skill(self, name: str) -> bool:
        """Remove a plugin/skill from the registry and manifest."""
        if name not in self._plugins:
            return False
        del self._plugins[name]
        self._save_manifest()
        return True

    def search_skills(self, query: str) -> list[PluginInfo]:
        """Search plugins by name or description substring."""
        q = query.lower()
        return [p for p in self._plugins.values() if q in p.name.lower() or q in p.description.lower()]

    def sync_to_harness(self, harness_registry) -> list[str]:
        """Bridge: install all PluginRegistry skills into a HarnessRegistry as SkillSpecs.

        Returns a list of skill names that were newly registered.
        """
        from yantra.harness import RiskLevel, SkillSpec
        added = []
        for name, plugin in self._plugins.items():
            if plugin.state == PluginState.DISABLED:
                continue
            if harness_registry.get_skill(name) is not None:
                continue
            risk = RiskLevel.LOW if plugin.trust_level.value in ("verified", "community") else RiskLevel.HIGH
            spec = SkillSpec(name, plugin.description, tool_name="", risk=risk)
            harness_registry.register_skill(spec)
            added.append(name)
        if added:
            self._save_manifest()
        return added

    def route_skill(self, prompt: str) -> PluginInfo | None:
        text = prompt.lower()
        for plugin in self._plugins.values():
            haystack = f"{plugin.name} {plugin.description}".lower()
            if plugin.name.lower() in text or _skills_intersect(text.split(), haystack.split()):
                return plugin
        return None

    def _save_manifest(self) -> None:
        manifest = self.plugins_dir / "plugins.json"
        manifest.write_text(
            json.dumps({"plugins": [_plugin_to_json(plugin) for plugin in self._plugins.values()]}, indent=2),
            encoding="utf-8",
        )


def _plugin_to_json(plugin: PluginInfo) -> dict[str, Any]:
    data = vars(plugin).copy()
    data["trust_level"] = plugin.trust_level.value
    data["state"] = plugin.state.value
    return data


def _skills_intersect(words: list[str], haystack_words: list[str]) -> bool:
    return len(set(words) & set(haystack_words)) >= 2


def _extract_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _extract_description(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:240]
    return "Local Atulya skill"
