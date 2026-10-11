"""Atulya identity and response instructions."""
from __future__ import annotations


def build_system_prompt(assistant_name: str, extra_instructions: str = "") -> str:
    """Build the trusted identity prompt used by the reasoning layer."""
    name = assistant_name.strip()
    if not name:
        raise ValueError("Assistant name must not be empty")
    parts = [
        f"You are {name}, a helpful personal assistant. "
        "Answer clearly and honestly. Do not claim to have performed actions "
        "unless a connected tool confirms that they were completed."
    ]
    extra = extra_instructions.strip()
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)
