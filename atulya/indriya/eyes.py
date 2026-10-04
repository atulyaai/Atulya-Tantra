"""Eyes: what Atulya sees in a camera frame or screenshot.

Local and free first: RapidOCR reads any text in the picture (labels, screens,
documents). Describing a scene uses a local Ollama vision model (default
``moondream``, ``ATULYA_OLLAMA_VISION_MODEL``) and only escalates to Gemini's
free tier when that gives nothing and GEMINI_API_KEY is set.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 6 * 1024 * 1024
_ocr = None


def decode_image(data: str) -> bytes:
    """Accept a data URL or bare base64; reject anything that isn't a sane image."""
    raw = re.sub(r"^data:image/[\w.+-]+;base64,", "", (data or "").strip())
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Image is not valid base64") from exc
    if not blob or len(blob) > MAX_IMAGE_BYTES:
        raise ValueError("Image is empty or too large")
    if not (blob[:3] == b"\xff\xd8\xff" or blob[:8] == b"\x89PNG\r\n\x1a\n" or blob[8:12] == b"WEBP"):
        raise ValueError("Only JPEG, PNG or WebP images are supported")
    return blob


def read_text(image: bytes) -> str:
    """OCR on this machine. Empty string when nothing is readable or OCR isn't installed."""
    global _ocr
    try:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            _ocr = RapidOCR()
        result, _ = _ocr(image)
    except ImportError:
        logger.info("rapidocr_onnxruntime not installed; skipping OCR")
        return ""
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""
    return "\n".join(item[1] for item in (result or []) if float(item[2]) >= 0.5)


def local_describe(image: bytes, question: str) -> str:
    """Scene description through a local Ollama vision model (moondream, llava…). Empty if unavailable."""
    host = os.environ.get("ATULYA_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.environ.get("ATULYA_OLLAMA_VISION_MODEL", "moondream")
    body = {"model": model, "stream": False,
            "prompt": question or "Describe what you see in one or two sentences.",
            "images": [base64.b64encode(image).decode()]}
    req = urllib.request.Request(f"{host}/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return str(json.loads(resp.read()).get("response", "")).strip()
    except Exception as exc:  # noqa: BLE001 - not installed / not running is normal
        logger.debug("Local vision unavailable: %s", exc)
        return ""


def describe_scene(image: bytes, question: str) -> str:
    """Local vision model first (private, free); Gemini only if configured and local gave nothing."""
    return local_describe(image, question) or cloud_describe(image, question)


def cloud_describe(image: bytes, question: str) -> str:
    """Scene description via Gemini (free tier). Empty string when not configured."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    model = os.environ.get("ATULYA_VISION_MODEL", "gemini-2.0-flash")
    mime = "image/png" if image[:4] == b"\x89PNG" else "image/webp" if image[8:12] == b"WEBP" else "image/jpeg"
    body = {"contents": [{"parts": [
        {"text": question or "Describe what you see in one or two sentences."},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}},
    ]}]}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning("Cloud vision failed: %s", exc)
        return ""


async def look(image_data: str, question: str = "") -> dict[str, Any]:
    image = decode_image(image_data)
    text, description = await asyncio.gather(
        asyncio.to_thread(read_text, image),
        asyncio.to_thread(describe_scene, image, question),
    )
    return {"text": text, "description": description, "can_describe": bool(description or os.environ.get("GEMINI_API_KEY"))}


def as_context(seen: dict[str, Any]) -> str:
    """What the camera saw, phrased for the brain."""
    parts = []
    if seen.get("description"):
        parts.append(f"The camera shows: {seen['description']}")
    if seen.get("text"):
        parts.append(f"Text visible in the picture:\n{seen['text']}")
    if not parts:
        parts.append("The user shared a picture, but no text was readable in it"
                     + ("" if seen.get("can_describe") else " and scene description is not set up (run `ollama pull moondream` or set GEMINI_API_KEY)")
                     + ". Say so honestly rather than guessing what it shows.")
    return "[What I see]\n" + "\n".join(parts) + "\n\n"
