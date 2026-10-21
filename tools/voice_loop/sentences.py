"""Cut streamed reply text into speakable pieces as early as possible."""
from __future__ import annotations

import re

# A '.' right before a digit may be a decimal (20.5), so an end needs whitespace after it.
_END = re.compile(r"[.!?।]\s|\n")
MAX_CHARS = 120
FIRST_MIN_CHARS = 20


def split_ready(buffer: str, *, first: bool = False) -> tuple[list[str], str]:
    """(complete sentences, remaining text). Cuts on . ! ? । followed by space, or newline; a piece
    longer than MAX_CHARS is cut at its last space. The first piece of a reply waits for
    FIRST_MIN_CHARS so we do not synthesize a lone 'So.'."""
    out: list[str] = []
    while True:
        start = FIRST_MIN_CHARS if first and not out else 0
        match = _END.search(buffer, min(start, len(buffer)))
        if match:
            piece, buffer = buffer[:match.end()].strip(), buffer[match.end():]
        elif len(buffer) > MAX_CHARS:
            cut = buffer.rfind(" ", 0, MAX_CHARS)
            cut = cut if cut > 0 else MAX_CHARS
            piece, buffer = buffer[:cut].strip(), buffer[cut:]
        else:
            return out, buffer
        if piece:
            out.append(piece)
