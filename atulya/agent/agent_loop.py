"""Generic Agent Loop — ReAct (Reason + Act) / TAO (Thought-Action-Observation).

This loop is model-agnostic. It feeds tool schemas to any LLM;
the LLM decides whether to respond or call a tool.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .tools import get_tool_schemas, execute_tool

logger = logging.getLogger(__name__)

MAX_STEPS = 10
MODEL = "auto"


async def agent_loop(
    user_input: str,
    llm: Any,
    system_prompt: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Run the ReAct agent loop.

    Args:
        user_input: The user's message.
        llm: An object with a .chat(prompt, system_prompt, tools) method.
        system_prompt: Override default system prompt.
        conversation_history: Previous messages [{role, content}].

    Returns:
        The final assistant reply as a string.
    """
    tools = get_tool_schemas()
    tool_map = {t["function"]["name"]: t for t in tools}

    messages = list(conversation_history or [])
    messages.append({"role": "user", "content": user_input})

    system = system_prompt or _default_system_prompt(tools)

    for step in range(1, MAX_STEPS + 1):
        resp = await llm.chat(
            prompt=_format_messages(messages),
            system_prompt=system,
            tools=tools if tools else None,
        )

        # The response could be text or a tool_call. We handle both.
        text, tool_calls = _parse_response(resp)

        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                logger.info("Step %d: calling tool '%s' with args %s", step, name, args)
                result = await execute_tool(name, **args)
                messages.append({"role": "assistant", "content": f"Called {name}"})
                messages.append({"role": "tool", "name": name, "content": result})
            # Continue loop — LLM sees tool results and decides next step
            continue

        if text:
            return text

        # Fallback: if nothing produced, return last known good text
        return "I'm not sure how to respond to that."

    return "I've reached the maximum number of reasoning steps. Please ask me something simpler."


def _default_system_prompt(tools: list[dict]) -> str:
    names = [t["function"]["name"] for t in tools]
    descs = "\n".join(f"  - {t['function']['name']}: {t['function']['description']}" for t in tools)
    return (
        "You are Atulya, a proactive AI assistant.\n\n"
        "You have access to these tools:\n"
        f"{descs}\n\n"
        "When a user asks for something, decide whether to:\n"
        "1. Call a tool (if you need data or to perform an action)\n"
        "2. Answer directly (if you already know the answer)\n\n"
        "If you call a tool, the result will be fed back to you so you can continue.\n"
        "Always respond conversationally and helpfully."
    )


def _format_messages(messages: list[dict]) -> str:
    """Simple formatting for providers that take a prompt string."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "tool":
            parts.append(f"[Tool result: {content}]")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    return "\n".join(parts)


def _parse_response(resp: Any) -> tuple[str | None, list[dict] | None]:
    """Parse LLM response into (text, tool_calls).

    Supports multiple response formats:
    - Tuple[str, str] from our ProviderRouter
    - Dict with 'choices' (OpenAI format)
    - Plain string
    - Object with .tool_calls attribute
    """
    text = None
    tool_calls = []

    # Handle tuple (response_text, provider_name) from our router
    if isinstance(resp, tuple):
        text = resp[0]

    # Handle dict with choices (OpenAI-compatible format)
    elif isinstance(resp, dict):
        choices = resp.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            text = msg.get("content", "")
            tc_list = msg.get("tool_calls", [])
            if tc_list:
                for tc in tc_list:
                    fn = tc.get("function", {})
                    args_str = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append({"name": fn.get("name", ""), "arguments": args})

    # Handle plain string
    elif isinstance(resp, str):
        text = resp

    # Handle object with tool_calls attribute
    elif hasattr(resp, "tool_calls"):
        text = getattr(resp, "content", str(resp))
        for tc in resp.tool_calls:
            tool_calls.append({"name": tc.function.name, "arguments": json.loads(tc.function.arguments)})

    return text, tool_calls if tool_calls else None
