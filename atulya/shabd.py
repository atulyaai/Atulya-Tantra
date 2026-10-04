"""Small text helpers shared by every way Atulya speaks."""
from __future__ import annotations

import re

# Emoji, pictographs, dingbats, flags, skin tones, variation selectors and joiners.
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoticons, symbols, transport, supplemental pictographs
    "\U00002600-\U000027BF"   # misc symbols and dingbats
    "\U00002B00-\U00002BFF"   # arrows and stars
    "\U00002300-\U000023FF"   # misc technical (watch, hourglass...)
    "\U0001F1E6-\U0001F1FF"   # flags
    "\uFE0E\uFE0F\u200D\u20E3"  # variation selectors, zero-width joiner, keycap
    "]+"
)


def strip_emoji(text: str) -> str:
    """Remove emoji so a voice never reads out "smiling face with smiling eyes"."""
    cleaned = _EMOJI.sub("", text or "")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()
