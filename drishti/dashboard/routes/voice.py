"""Voice API Routes for High-Quality Neural TTS and STT."""
from __future__ import annotations

import base64
import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse

from atulya.config import get_config
from drishti.dashboard import chat_history
from drishti.dashboard.helpers import _checkpoint_index, _load_cached_model, _require_auth
from yantra.capabilities.voice_pipeline import VoicePipeline, TextToSpeech, SpeechToText

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize voice pipeline components
# We save to the configured Atulya data directory inside the workspace by default.
assets_dir = get_config().data_dir
tts_dir = assets_dir / "audio" / "tts"
stt_dir = assets_dir / "audio" / "stt"

voice_pipeline = VoicePipeline(tts_dir=str(tts_dir), stt_dir=str(stt_dir))


@router.get("/api/voice/voices")
def get_voices():
    """Get the available voice profiles for high-quality edge-tts."""
    return {
        "voices": [
            {"id": "en_male", "name": "Atulya Neural (Male)", "lang": "en", "voice_id": "en-US-GuyNeural"},
            {"id": "en_female", "name": "Atulya Neural (Female)", "lang": "en", "voice_id": "en-US-JennyNeural"},
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
    
    # 1. Load Persona and build system guidelines
    system_prompt = ""
    try:
        from atulya.persona import Persona
        system_prompt = Persona().get_system_prompt()
    except Exception as e:
        logger.warning(f"Failed to load system persona: {e}")
        system_prompt = "You are Atulya, a helpful local AI assistant."

    # 2. Query Pluggable Provider Router
    response_text = ""
    provider_name = "Atulya Fallback"
    try:
        from atulya.llm import get_default_llm
        response = await get_default_llm().ask(
            prompt,
            history=body.get("history") or [],
            tools_enabled=True,
            provider=str(body.get("provider") or body.get("model_id") or ""),
        )
        response_text, provider_name = response.text, response.provider
    except Exception as exc:
        logger.error(f"Intelligence router failure: {exc}")
        from atulya.persona import get_atulya_fallback_response
        response_text = get_atulya_fallback_response(prompt, voice)
        provider_name = "Diagnostics Fallback"

    # 3. Synthesize generated text into premium audio
    try:
        tts_result = await voice_pipeline.tts.synthesize(text=response_text, voice=voice, save=True)
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface="live")
        return {
            "prompt": prompt,
            "response_text": response_text,
            "audio_base64": tts_result.audio_base64,
            "format": tts_result.format.value,
            "provider": tts_result.provider,
            "provider_name": provider_name
        }
    except Exception as e:
        logger.error(f"Voice chat TTS synthesis failed: {e}")
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface="live")
        return {
            "prompt": prompt,
            "response_text": response_text,
            "provider_name": provider_name,
            "error": f"Audio synthesis failed: {e}"
        }

