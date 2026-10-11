"""User-controlled memory command plugin."""
from __future__ import annotations

import re
from tools.plugins.registry import PluginContext


async def handle(command: str, context: PluginContext) -> str | None:
    remember = re.fullmatch(r"(?:please\s+)?remember(?:\s+that)?\s+(.+)", command, re.I)
    forget = re.fullmatch(r"(?:please\s+)?forget(?:\s+that)?\s+(.+)", command, re.I)
    if remember:
        fact = remember.group(1).strip().rstrip(".?!")
        try:
            created = context.memory.remember(context.owner_id, fact, user_id=context.user_id)
        except ValueError as exc:
            return str(exc)
        return "I'll remember that." if created else "I already have that in memory."
    if forget:
        query = forget.group(1).strip().rstrip(".?!")
        try:
            deleted = context.memory.forget(context.owner_id, query, user_id=context.user_id)
        except ValueError as exc:
            return str(exc)
        return "I've forgotten that." if deleted else "I couldn't find a matching memory."
    if re.search(r"\b(what do you remember|my memories|what have you remembered)\b", command, re.I):
        query = re.sub(
            r"(?i)^(?:what do you remember(?: about)?|what have you remembered(?: about)?|my memories)\s*",
            "", command,
        ).rstrip("?.! ")
        facts = context.memory.relevant(context.owner_id, query or command, user_id=context.user_id)
        return "I don't have any saved personal memories yet." if not facts else (
            "Here's what I remember:\n" + "\n".join(f"• {fact}" for fact in facts)
        )
    return None
