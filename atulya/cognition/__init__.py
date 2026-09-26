"""Atulya cognition layer — the assistant's single nervous system.

    perceive -> understand -> decide -> act -> remember -> react

  * ``toolbelt``  one tool surface for every entry point (the "hands")
  * ``safety``    which actions may run vs. need confirmation (the "conscience")
  * ``kernel``    the unified pipeline every request goes through
  * ``triggers``  event-driven proactivity on the event bus (the "reflexes")
  * ``brain``     one-setting brain tiers (tiny / balanced / power / cloud)

Submodules are imported lazily so low-level modules (e.g. ``atulya.llm``) can
depend on ``safety``/``toolbelt`` without pulling in the kernel.
"""
from __future__ import annotations

from typing import Any

__all__ = ["CognitiveKernel", "get_kernel"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import kernel

        return getattr(kernel, name)
    raise AttributeError(name)
