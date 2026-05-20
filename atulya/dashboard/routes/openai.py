"""OpenAI-compatible chat completions endpoint for Atulya Tantra.

Allows any app built for GPT to work with Atulya immediately.
Supports: POST /v1/chat/completions and POST /v1/completions
"""
from __future__ import annotations
import json
import logging
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from atulya.dashboard.state import OUTPUTS_DIR, MAX_CHAT_TOKENS
from atulya.dashboard.helpers import (
    _require_admin,
    _check_request_origin,
    _checkpoint_index,
    _read_metadata,
    _model_readiness,
    _load_cached_model,
    _clamp_int,
    _clamp_float,
)

logger = logging.getLogger("atulya.dashboard.routes.openai")
router = APIRouter()


def _messages_to_prompt(messages: list[dict]) -> str:
    """Convert OpenAI messages format to Atulya prompt format."""
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            lines.append(f"System: {content}")
        elif role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
    if not lines or lines[-1].startswith("User:"):
        lines.append("Assistant:")
    return "\n".join(lines)


def _make_completion_id():
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


@router.post("/v1/chat/completions")
def openai_chat_completions(
    body: dict,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """OpenAI-compatible chat completions endpoint."""
    _check_request_origin(request)
    # Accept either dashboard token or OpenAI-style Bearer token
    token = authorization
    if token and token.startswith("Bearer "):
        token = token[7:]
    _require_admin(token)

    messages = body.get("messages", [])
    if not messages:
        return {"error": {"message": "messages is required", "type": "invalid_request_error"}}

    model_id = str(body.get("model") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        candidate = Path(model_id)
        from atulya.dashboard.helpers import _is_within
        if candidate.exists() and _is_within(candidate, [OUTPUTS_DIR.resolve()]):
            model_path = candidate.resolve()

    if not model_path or not (Path(model_path) / "metadata.json").exists():
        return {"error": {"message": "No trained model found", "type": "model_not_found"}}

    try:
        core = _load_cached_model(Path(model_path))
        max_tokens = _clamp_int(body.get("max_tokens"), 40, 1, MAX_CHAT_TOKENS)
        temperature = _clamp_float(body.get("temperature"), 0.35, 0.0, 2.0)
        top_p = _clamp_float(body.get("top_p"), 1.0, 0.0, 1.0)

        prompt = _messages_to_prompt(messages)
        stream = body.get("stream", False)

        if stream:
            completion_id = _make_completion_id()

            def generate():
                for token in core.generate_stream(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                ):
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_id,
                        "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                done_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_id,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(done_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            response = core.generate(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            completion_id = _make_completion_id()
            return {
                "id": completion_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(core.encode(prompt)),
                    "completion_tokens": len(core.encode(response)),
                    "total_tokens": len(core.encode(prompt + response)),
                },
            }
    except Exception as e:
        return {"error": {"message": str(e), "type": "server_error"}}


@router.post("/v1/completions")
def openai_completions(
    body: dict,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """OpenAI-compatible completions endpoint (legacy)."""
    _check_request_origin(request)
    token = authorization
    if token and token.startswith("Bearer "):
        token = token[7:]
    _require_admin(token)

    prompt = body.get("prompt", "")
    if not prompt:
        return {"error": {"message": "prompt is required", "type": "invalid_request_error"}}

    model_id = str(body.get("model") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        candidate = Path(model_id)
        from atulya.dashboard.helpers import _is_within
        if candidate.exists() and _is_within(candidate, [OUTPUTS_DIR.resolve()]):
            model_path = candidate.resolve()

    if not model_path or not (Path(model_path) / "metadata.json").exists():
        return {"error": {"message": "No trained model found", "type": "model_not_found"}}

    try:
        core = _load_cached_model(Path(model_path))
        max_tokens = _clamp_int(body.get("max_tokens"), 40, 1, MAX_CHAT_TOKENS)
        temperature = _clamp_float(body.get("temperature"), 0.35, 0.0, 2.0)

        response = core.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        completion_id = _make_completion_id()
        return {
            "id": completion_id,
            "object": "text_completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [
                {
                    "text": response,
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(core.encode(prompt)),
                "completion_tokens": len(core.encode(response)),
                "total_tokens": len(core.encode(prompt + response)),
            },
        }
    except Exception as e:
        return {"error": {"message": str(e), "type": "server_error"}}
