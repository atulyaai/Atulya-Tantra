"""PC control has no instant text commands; the model proposes actions and the user approves them."""
from __future__ import annotations

from tools.plugins.registry import PluginContext


async def handle(_command: str, _context: PluginContext) -> None:
    return None
