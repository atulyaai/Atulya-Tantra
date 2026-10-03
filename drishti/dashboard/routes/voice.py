"""Voice API Routes for High-Quality Neural TTS and STT."""
from __future__ import annotations

import logging
import os
import re

from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from atulya.config import get_config
from drishti.dashboard import chat_history
from drishti.dashboard.helpers import _require_auth, redact_for
from yantra.capabilities.voice_pipeline import VoicePipeline

logger = logging.getLogger(__name__)

router = APIRouter()

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
        result = await voice_pipeline.tts.synthesize(text=text, voice=voice, speed=speed, save=True)
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
        from atulya.cognition import get_kernel
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
            from atulya.eyes import as_context, look

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
            text=response_text, voice=voice_for_reply(response_text, voice), save=True)
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

