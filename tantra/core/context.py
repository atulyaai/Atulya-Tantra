"""Context management - window guard, TokenJuice compression, prompt cache."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextMessage:
    role: str
    content: str
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextWindowGuard:
    def __init__(self, max_tokens: int = 8192, max_messages: int = 50):
        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self.messages: list[ContextMessage] = []
        self.total_tokens = 0

    def add(self, message: ContextMessage) -> bool:
        # Enforce max_messages - remove oldest when at capacity
        if message.token_count <= 0:
            message.token_count = max(1, len(message.content) // 4 + 1)
        if message.token_count > self.max_tokens:
            return False
        if len(self.messages) >= self.max_messages:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.token_count
        if self.total_tokens + message.token_count > self.max_tokens:
            self._compact()
        while self.total_tokens + message.token_count > self.max_tokens and self.messages:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.token_count
        self.messages.append(message)
        self.total_tokens += message.token_count
        return True

    def _compact(self):
        while self.total_tokens > self.max_tokens * 0.8 and len(self.messages) > 2:
            removed = self.messages.pop(0)
            self.total_tokens -= removed.token_count

    def get_messages(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def stats(self) -> dict[str, Any]:
        return {"messages": len(self.messages), "tokens": self.total_tokens, "max_tokens": self.max_tokens}


class ContextCompressor:
    def __init__(self):
        self._tool_rules: dict[str, dict[str, Any]] = {}
        self._builtin_rules = {
            "blank_lines": True,
            "deduplicate": True,
            "url_shorten": True,
            "html_strip": True,
        }
        self._user_rules: dict[str, str] = {}
        self._project_rules: dict[str, str] = {}

    def add_tool_rule(self, tool_name: str, rules: dict[str, Any]):
        self._tool_rules[tool_name] = rules

    def add_user_rule(self, pattern: str, action: str):
        self._user_rules[pattern] = action

    def add_project_rule(self, pattern: str, action: str):
        self._project_rules[pattern] = action

    def compress(self, text: str, tool_name: str | None = None) -> str:
        lines = text.split("\n")
        result = []
        seen = set()

        rules = dict(self._builtin_rules)

        for line in lines:
            original_stripped = line.strip()
            custom = self._apply_pattern_rules(original_stripped)
            if custom is None:
                continue
            stripped = custom

            # Blank line compression
            if rules.get("blank_lines") and not stripped:
                if result and result[-1] != "":
                    result.append("")
                continue

            # Deduplicate (use original_stripped to avoid false positives when
            # pattern rules redact different lines to the same "[REDACTED]" string)
            if rules.get("deduplicate") and original_stripped in seen:
                continue
            seen.add(original_stripped)

            # HTML stripping
            if rules.get("html_strip"):
                stripped = re.sub(r'<[^>]+>', '', stripped)

            # URL shortening
            if rules.get("url_shorten"):
                stripped = re.sub(r'https?://[^\s]+', '[URL]', stripped)

            # Tool-specific rules
            if tool_name and tool_name in self._tool_rules:
                tool_rule = self._tool_rules[tool_name]
                if "drop_patterns" in tool_rule:
                    if any(re.search(p, stripped) for p in tool_rule["drop_patterns"]):
                        continue

            result.append(stripped)

        return "\n".join(result)

    def _apply_pattern_rules(self, line: str) -> str | None:
        for pattern, action in [*self._user_rules.items(), *self._project_rules.items()]:
            if not re.search(pattern, line):
                continue
            normalized = action.lower().strip()
            if normalized in {"drop", "remove", "omit", "exclude"}:
                return None
            if normalized in {"mask", "redact"}:
                return re.sub(pattern, "[REDACTED]", line)
        return line

    def collapse_blank_lines(self, text: str) -> str:
        return re.sub(r'\n{3,}', '\n\n', text)

    def deduplicate_lines(self, text: str) -> str:
        """Deduplicate lines while preserving order."""
        lines = text.split("\n")
        seen: set[str] = set()
        deduped: list[str] = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                deduped.append(line)
        return "\n".join(deduped)


class PromptCache:
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
        self._invalidation_queue: list[str] = []

    def get(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry and time.time() < entry.get("expires", 0):
            return entry.get("value")
        return None

    def set(self, key: str, value: str, ttl: int = 3600):
        self._cache[key] = {"value": value, "expires": time.time() + ttl}

    def invalidate(self, key: str):
        self._invalidation_queue.append(key)
        self._cache.pop(key, None)

    def process_invalidation(self):
        while self._invalidation_queue:
            self._cache.pop(self._invalidation_queue.pop(0), None)
