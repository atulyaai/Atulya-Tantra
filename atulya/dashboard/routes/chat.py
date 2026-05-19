"""NP-DNA Dashboard Chat Routes.
"""
from __future__ import annotations
import logging
import re
import time
from pathlib import Path
from fastapi import APIRouter, Header, Request

from atulya.dashboard.state import OUTPUTS_DIR, MAX_PROMPT_CHARS, MAX_CHAT_TOKENS
from atulya.dashboard.helpers import (
    _require_admin,
    _check_request_origin,
    _checkpoint_index,
    _read_metadata,
    _model_readiness,
    _load_cached_model,
    _clamp_int,
    _clamp_float,
    _format_mode_prompt,
    _clean_chat_response,
    _is_within,
)

logger = logging.getLogger("atulya.dashboard.routes.chat")
router = APIRouter()


@router.post("/api/chat")
def api_chat(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """Generate text from the trained model."""
    _check_request_origin(request)
    _require_admin(_admin)
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return {"error": "Empty prompt"}
    if len(prompt) > MAX_PROMPT_CHARS:
        return {"error": f"Prompt too long. Max {MAX_PROMPT_CHARS} characters."}
        
    model_id = str(body.get("model_id") or body.get("model_path") or "latest")
    model_path = _checkpoint_index().get(model_id)
    if not model_path:
        candidate = Path(model_id)
        if candidate.exists() and _is_within(candidate, [OUTPUTS_DIR.resolve()]):
            model_path = candidate.resolve()
            
    if not model_path:
        return {"error": "Model path not allowed"}
    if not (Path(model_path) / "metadata.json").exists():
        return {"error": "No trained model found. Train first."}
        
    try:
        meta = _read_metadata(Path(model_path))
        readiness = _model_readiness(meta)
        core = _load_cached_model(Path(model_path))
        max_tokens = _clamp_int(body.get("max_tokens"), 40, 1, MAX_CHAT_TOKENS)
        temperature = _clamp_float(body.get("temperature"), 0.15, 0.0, 2.0)
        top_k = _clamp_int(body.get("top_k"), 5, 0, 100)
        chat_prompt = _format_mode_prompt(prompt, str(body.get("mode") or "chat"), body.get("system"))
        
        import base64
        import torch
        import io
        
        audio_inputs = None
        image_inputs = None
        device = core.model.embedding.weight.device
        
        # 1. Decode Audio base64
        audio_b64 = body.get("audio")
        if audio_b64:
            if len(audio_b64) > 10 * 1024 * 1024:
                return {"error": "Audio payload too large. Max 10MB."}
            try:
                if "," in audio_b64:
                    audio_b64 = audio_b64.split(",", 1)[1]
                decoded_audio = base64.b64decode(audio_b64)
                
                import wave
                import array
                try:
                    with wave.open(io.BytesIO(decoded_audio), "rb") as wav:
                        raw_data = wav.readframes(wav.getnframes())
                        if wav.getsampwidth() == 2:
                            arr = array.array("h", raw_data)
                            audio_tensor = torch.tensor(arr, dtype=torch.float32) / 32768.0
                        else:
                            audio_tensor = torch.tensor(list(raw_data), dtype=torch.float32) / 255.0
                        audio_inputs = audio_tensor.unsqueeze(0).to(device)
                except Exception:
                    audio_inputs = torch.zeros(1, 1600, device=device)
            except Exception as ae:
                logger.warning("Failed decoding audio input: %s", ae)
                
        # 2. Decode Image base64
        image_b64 = body.get("image")
        if image_b64:
            if len(image_b64) > 10 * 1024 * 1024:
                return {"error": "Image payload too large. Max 10MB."}
            try:
                if "," in image_b64:
                    image_b64 = image_b64.split(",", 1)[1]
                decoded_image = base64.b64decode(image_b64)
                
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(decoded_image)).convert("RGB")
                    img = img.resize((32, 32))
                    img_data = list(img.getdata())
                    t = torch.tensor(img_data, dtype=torch.float32).view(32, 32, 3).permute(2, 0, 1).unsqueeze(0)
                    image_inputs = (t / 255.0).to(device)
                except Exception:
                    image_inputs = torch.zeros(1, 3, 32, 32, device=device)
            except Exception as ie:
                logger.warning("Failed decoding image input: %s", ie)

        t0 = time.time()
        use_agent = bool(body.get("use_agent") or body.get("mode") == "agent")
        
        agent_steps = None
        if use_agent:
            from atulya.core.npdna.autonomy import NpDnaAgent
            agent = NpDnaAgent(core)
            response, agent_steps = agent.run_with_telemetry(prompt, max_iterations=5)
        else:
            response = core.generate(
                chat_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                audio_inputs=audio_inputs,
                image_inputs=image_inputs
            )
            
        response = _clean_chat_response(response)
        
        write_backs = [
            match.strip()
            for match in re.findall(r"<memory_start>(.*?)<memory_end>", response, re.DOTALL)
            if match.strip()
        ]
        response_clean = re.sub(r"<memory_start>.*?<memory_end>", "", response, flags=re.DOTALL)
        response_clean = _clean_chat_response(response_clean)
        response_clean = re.sub(r"\n\s*\n", "\n", response_clean).strip()

        elapsed = time.time() - t0
        payload = {
            "response": response_clean or "[empty response]",
            "raw_response": response,
            "cortex_write_backs": write_backs,
            "time_sec": round(elapsed, 2),
            "model": model_id,
            "vocab_used": core.tokenizer.size,
            "readiness": readiness,
        }
        if agent_steps is not None:
            payload["agent_steps"] = agent_steps
        if hasattr(core, "get_routing_telemetry"):
            payload["routing_telemetry"] = core.get_routing_telemetry()
        if not readiness.get("ready"):
            payload["not_ready"] = True
            payload["warning"] = (
                "Raw checkpoint: "
                f"loss {readiness.get('loss', 'unknown')}, "
                f"train PPL {readiness.get('train_ppl', 'unknown')}. "
                "Output may be incoherent."
            )
        return payload
    except Exception as e:
        return {"error": str(e)}
