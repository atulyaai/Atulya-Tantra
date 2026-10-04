"""Voice API Routes for High-Quality Neural TTS and STT."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from atulya.config import get_config
from atulya.sevak import chat_history, helpers
from atulya.sevak.helpers import _require_auth, redact_for
from atulya.sevak.state import MAX_CHAT_TOKENS, MAX_PROMPT_CHARS
from atulya.vani import VoicePipeline

# ── chat ────────────────────────────────────────────────────────────
router = APIRouter()


def _merge_history(frontend_history: list[dict], server_history: list[dict], limit: int = 10) -> list[dict]:
    """Merge frontend-provided history with server-persisted history, deduplicating by content."""
    seen = set()
    merged = []
    for msg in server_history + frontend_history:
        content = (msg.get("content") or msg.get("text") or "").strip()
        role = msg.get("role", "user")
        if not content:
            continue
        key = f"{role}:{content[:80]}"
        if key in seen:
            continue
        seen.add(key)
        merged.append({"role": role, "content": content})
    return merged[-limit:]


@router.post("/api/chat")
async def api_chat(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    if "\\" in model_id or "/" in model_id:
        return {"error": "Model path not allowed"}
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    if not prompt.strip() and not body.get("approved_tool"):
        return {"error": "Say or type something first."}
    from atulya.buddhi import get_kernel
    from atulya.buddhi.llm import get_default_llm

    server_messages = chat_history.list_messages(user, limit=20)
    server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
    frontend_hist = body.get("history") or []
    history = _merge_history(frontend_hist, server_hist)

    # Every request goes through the cognitive kernel: intent -> safety -> action,
    # or the brain for open conversation.
    kernel = get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())
    response = await kernel.handle(
        prompt,
        user=user,
        history=history,
        approved_tool=body.get("approved_tool") or None,
        provider=str(body.get("provider") or model_id),
        source="chat",
    )
    chat_history.append_exchange(user, prompt, response.text, provider=response.provider)
    return redact_for(user, {
        "response": response.text[:MAX_CHAT_TOKENS * 8],
        "model_id": model_id,
        "provider": response.provider,
        "steps": response.tool_steps,
        "needs_approval": response.needs_approval,
        "pending_tool": response.pending_tool,
        "trace": getattr(response, "trace", []),
    })


@router.post("/api/chat/stream")
async def api_chat_stream(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    if "\\" in model_id or "/" in model_id:
        error = {"error": "Model path not allowed"}
        async def error_events():
            yield f"data: {json.dumps(error)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(error_events(), media_type="text/event-stream")

    async def events():
        from atulya.buddhi import get_kernel
        from atulya.buddhi.llm import get_default_llm

        try:
            server_messages = chat_history.list_messages(user, limit=20)
            server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
            frontend_hist = body.get("history") or []
            history = _merge_history(frontend_hist, server_hist)

            kernel = get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())
            response_parts: list[str] = []
            async for event in kernel.stream(
                prompt,
                user=user,
                history=history,
                approved_tool=body.get("approved_tool") or None,
                provider=str(body.get("provider") or model_id),
                source="chat",
            ):
                if event.type == "token":
                    response_parts.append(event.content)
                    yield f"data: {json.dumps({'token': event.content})}\n\n"
                elif event.type == "tool":
                    yield f"data: {json.dumps({'tool': event.metadata})}\n\n"
                elif event.type == "done":
                    chat_history.append_exchange(
                        user,
                        prompt,
                        "".join(response_parts),
                        provider=str(event.metadata.get("provider") or ""),
                    )
                    payload = {"done": True, "model_id": model_id, **event.metadata}
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/api/chat/history")
async def api_chat_history(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    return {"messages": chat_history.list_messages(user)}


@router.delete("/api/chat/history")
async def api_chat_history_clear(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    chat_history.clear_messages(user)
    return {"ok": True}


# ── openai ────────────────────────────────────────────────────────────
def _model_registry() -> list[dict]:
    """The assistant is exposed as a single model; the brain routes behind it."""
    return [{"id": "atulya", "label": "Atulya", "owned_by": "atulya"}]


def _require_bearer(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    parts = authorization.split(" ")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = parts[1]
    if token == helpers.ADMIN_TOKEN:
        return
    from atulya.sevak import users
    session = users.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if session.get("role") != "admin":  # which models are configured is admin business
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None, alias="Authorization")):
    _require_bearer(authorization)
    return {"object": "list", "data": [{"id": item["id"], "object": "model", **item} for item in _model_registry()]}


# ── voice ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


# Initialize voice pipeline components
# We save to the configured Atulya data directory inside the workspace by default.
assets_dir = get_config().data_dir
tts_dir = assets_dir / "audio" / "tts"
stt_dir = assets_dir / "audio" / "stt"

voice_pipeline = VoicePipeline(tts_dir=str(tts_dir), stt_dir=str(stt_dir))


_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def voice_for_reply(text: str, voice: str) -> str:
    """Keep the chosen gender but speak Hindi replies with a Hindi voice (and back)."""
    lang, _, gender = voice.partition("_")
    if gender not in ("male", "female") or lang not in ("en", "hi"):
        return voice
    return f"{'hi' if _DEVANAGARI.search(text or '') else 'en'}_{gender}"


@router.get("/api/voice/voices")
def get_voices():
    """Get the available voice profiles for high-quality edge-tts."""
    return {
        "voices": [
            {"id": "en_male", "name": "Atulya Neural (Male)", "lang": "en", "voice_id": "en-GB-RyanNeural"},
            {"id": "en_female", "name": "Atulya Neural (Female)", "lang": "en", "voice_id": "en-GB-SoniaNeural"},
            {"id": "hi_male", "name": "Madhur Neural (Hindi Male)", "lang": "hi", "voice_id": "hi-IN-MadhurNeural"},
            {"id": "hi_female", "name": "Swara Neural (Hindi Female)", "lang": "hi", "voice_id": "hi-IN-SwaraNeural"},
            {"id": "sa_male", "name": "Sanskrit Neural (Male)", "lang": "sa", "voice_id": "sa-IN-Neural"},
            {"id": "sa_female", "name": "Sanskrit Neural (Female)", "lang": "sa", "voice_id": "sa-IN-Neural"},
        ]
    }


@router.post("/api/voice/tts")
async def api_voice_tts(
    body: dict, 
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    """Text to Speech using high quality edge-tts."""
    _require_auth(token)
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text parameter is required")
    
    voice = str(body.get("voice") or "en_male")
    speed = float(body.get("speed") or 1.0)
    
    try:
        result = await voice_pipeline.tts.synthesize(text=text, voice=voice, speed=speed, save=False)
        if result.provider == "fallback":
            return JSONResponse(
                status_code=200,
                content={
                    "error": "edge-tts is not installed. Using local fallback.",
                    "text": text,
                    "provider": "fallback"
                }
            )
        return {
            "audio_base64": result.audio_base64,
            "format": result.format.value,
            "duration": result.duration,
            "id": result.id,
            "provider": result.provider
        }
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/voice/stt")
async def api_voice_stt(
    file: UploadFile = File(...),
    language: str = Form("en"),
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    """Speech to Text by uploading audio file."""
    _require_auth(token)
    try:
        # Create temp audio file
        temp_dir = assets_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_filepath = temp_dir / f"upload_{os.urandom(8).hex()}.wav"
        
        with open(temp_filepath, "wb") as f:
            f.write(await file.read())
            
        result = await voice_pipeline.stt.transcribe(
            audio_path=str(temp_filepath),
            language=language
        )
        
        # Clean up temp file
        if temp_filepath.exists():
            temp_filepath.unlink()
            
        return {
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "provider": result.provider,
            "error": result.error
        }
    except Exception as e:
        logger.error(f"STT transcription failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/voice/chat")
async def api_voice_chat(
    body: dict,
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    """Full voice chat round-trip using the Atulya Pluggable Provider Router."""
    user = _require_auth(token)
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
        
    voice = str(body.get("voice") or "en_male")
    # The always-listening app speaks for itself; only these two surfaces are
    # accepted, so a client can never claim a pre-authorized source.
    source = "ambient" if body.get("source") == "ambient" else "voice"
    surface = "ambient" if source == "ambient" else "live"

    # Route through the cognitive kernel (intent -> safety -> action, or the
    # brain). A risky action is answered with a spoken confirmation question;
    # the user's next utterance ("yes" / "no") resolves it.
    response_text = ""
    provider_name = "Atulya Fallback"
    needs_approval = False
    pending_tool = None
    trace: list = []
    try:
        from atulya.buddhi import get_kernel
        server_messages = chat_history.list_messages(user, limit=20)
        server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
        frontend_hist = body.get("history") or []
        seen = set()
        history = []
        for msg in server_hist + frontend_hist:
            content = (msg.get("content") or msg.get("text") or "").strip()
            role = msg.get("role", "user")
            if not content:
                continue
            key = f"{role}:{content[:80]}"
            if key in seen:
                continue
            seen.add(key)
            history.append({"role": role, "content": content})
        history = history[-10:]

        # A camera frame or screenshot rides along: read it first, then let
        # the brain answer with what was seen.
        brain_prompt = prompt
        if body.get("image"):
            from atulya.indriya import as_context, look

            try:
                seen = await look(str(body["image"]), prompt)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            brain_prompt = as_context(seen) + prompt
        response = await get_kernel().handle(
            brain_prompt,
            user=user,
            history=history,
            provider=str(body.get("provider") or body.get("model_id") or ""),
            source=source,
        )
        response_text, provider_name = response.text, response.provider
        needs_approval, pending_tool = response.needs_approval, response.pending_tool
        trace = getattr(response, "trace", [])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Intelligence router failure: {exc}")
        response_text = "Sorry, something went wrong while I was thinking. The details are in the server window."
        provider_name = "Diagnostics Fallback"

    reply = {
        "prompt": prompt,
        "response_text": response_text,
        "provider_name": provider_name,
        "needs_approval": needs_approval,
        "pending_tool": pending_tool,
        "trace": trace,
    }
    if body.get("tts") is False:  # the device speaks with its own voice
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface=surface)
        return redact_for(user, reply)

    # 3. Synthesize generated text into premium audio
    try:
        tts_result = await voice_pipeline.tts.synthesize(
            text=response_text, voice=voice_for_reply(response_text, voice), save=False)
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface=surface)
        return redact_for(user, {
            "prompt": prompt,
            "response_text": response_text,
            "audio_base64": tts_result.audio_base64,
            "format": tts_result.format.value,
            "provider": tts_result.provider,
            "provider_name": provider_name,
            "needs_approval": needs_approval,
            "pending_tool": pending_tool,
            "trace": trace,
        })
    except Exception as e:
        logger.error(f"Voice chat TTS synthesis failed: {e}")
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface=surface)
        return redact_for(user, {
            "prompt": prompt,
            "response_text": response_text,
            "provider_name": provider_name,
            "needs_approval": needs_approval,
            "pending_tool": pending_tool,
            "trace": trace,
            "error": f"Audio synthesis failed: {e}"
        })


# ── ws ────────────────────────────────────────────────────────────
_active_connections: set[WebSocket] = set()
_broadcast_history: list[dict[str, Any]] = []


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Authenticate the WebSocket connection via a token query parameter
    # (browsers cannot set arbitrary headers on a WebSocket handshake),
    # falling back to the X-Atulya-Token header if present. The connection is
    # rejected (4401 -> 1008 policy violation) before accept() when unauthenticated.
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.headers.get("x-atulya-token")

    try:
        user = _require_auth(token)
    except Exception:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    _active_connections.add(websocket)

    await websocket.send_json({"type": "welcome", "user": user.get("username"), "role": user.get("role")})

    # Send recent history, flagged so clients can show it without re-alerting.
    for msg in _broadcast_history[-20:]:
        await websocket.send_json({**msg, "replay": True})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            # Handle ping/pong
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)


async def broadcast(event_type: str, data: dict[str, Any]) -> None:
    payload = {"type": event_type, "data": data, "timestamp": time.time()}
    _broadcast_history.append(payload)
    if len(_broadcast_history) > 200:
        _broadcast_history[:] = _broadcast_history[-200:]

    disconnected = set()
    for ws in _active_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    _active_connections.difference_update(disconnected)


async def broadcast_training(status: dict) -> None:
    await broadcast("training_status", status)


async def broadcast_telemetry(telemetry: dict) -> None:
    await broadcast("telemetry", telemetry)


async def broadcast_event(title: str, desc: str, event_type: str = "info") -> None:
    await broadcast("event", {"title": title, "desc": desc, "type": event_type})

