"""Conservative spoken-command routing through the regular, scoped Toolbox."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .tts import speakable


@dataclass(frozen=True)
class VoiceIntent:
    tool: str
    arguments: dict


@dataclass(frozen=True)
class VoiceResult:
    text: str
    tool_result: str


_MEDIA = {
    "volume up": "volume_up", "turn up the volume": "volume_up", "increase volume": "volume_up",
    "volume down": "volume_down", "turn down the volume": "volume_down", "decrease volume": "volume_down",
    "mute": "mute", "mute the volume": "mute", "toggle mute": "mute",
    "play": "play_pause", "pause": "play_pause", "play pause": "play_pause", "toggle playback": "play_pause",
    "next": "next", "next track": "next", "skip track": "next", "previous track": "previous",
    "आवाज़ बढ़ाओ": "volume_up", "आवाज़ कम करो": "volume_down", "अगला गाना": "next",
}
_TIME = {"time", "what time is it", "what's the time", "what is the time", "tell me the time",
         "date", "what's the date", "what is the date", "what day is it", "आज की तारीख", "कितने बजे हैं"}
_WEATHER = re.compile(
    r"(?:(?:what(?:'s| is)|how(?:'s| is)) (?:the )?|tell me (?:the )?)?"
    r"weather(?: (?:for )?(today|tomorrow))?(?: in ([\w ,.'-]{1,100}?))?(?: (today|tomorrow))?"
)


def match_intent(text: str, *, language: str | None = None) -> VoiceIntent | None:
    # Direct templates and native tool responses are English. Preserve all other reply languages via the model.
    if language is not None:
        language = language.lower().strip()
        if language not in {"", "auto", "en", "english"} and not language.startswith("en-"):
            return None
        if language in {"", "auto"} and any(c.isalpha() and not c.isascii() for c in text):
            return None
    text = " ".join(text.strip().replace("’", "'").split()).strip("?!।.").lower()
    text = re.sub(r"^please\s+|\s+please$", "", text)
    if text in _TIME:
        return VoiceIntent("get_time", {})
    if text in _MEDIA:
        return VoiceIntent("media_control", {"command": _MEDIA[text]})
    hindi_weather = {"आज मौसम कैसा है": "today", "कल मौसम कैसा रहेगा": "tomorrow",
                     "आज का मौसम": "today", "कल का मौसम": "tomorrow"}
    if text in hindi_weather:
        return VoiceIntent("get_weather", {"when": hindi_weather[text]})
    match = _WEATHER.fullmatch(text)
    if match:
        before, place, after = match.groups()
        if before and after:  # conflicting or duplicated dates are not a simple request
            return None
        # Never swallow a second action, a qualified trip/date, or an embedded instruction as a place.
        if place and re.search(r"\b(and|then|next|week|month|trip|tomorrow|today|ignore|instead)\b", place):
            return None
        arguments = {"when": before or after or "now"}
        if place:
            arguments["place"] = place.strip()
        return VoiceIntent("get_weather", arguments)
    app = re.fullmatch(r"(?:open|launch) ([\w .+-]{1,40})", text)
    if app and not re.search(r"\b(and|then|after|tomorrow|instead)\b", app[1]):
        return VoiceIntent("open_app", {"name": app[1]})
    return None


def _spoken_units(text: str) -> str:
    """Card symbols read aloud: '20.3–30.8°C · rain 0%' -> '20.3 to 30.8 degrees, rain 0 percent'."""
    text = re.sub(r"(\d)\s*[–-]\s*(\d)", r"\1 to \2", text)
    text = text.replace("°C", " degrees").replace(" · ", ", ").replace("·", ",").replace("%", " percent")
    return " ".join(text.split())


def weather_sentence(result: str, when: str) -> str:
    """Keep measured values, warnings and the source; never label current conditions as tomorrow's.
    Short separate sentences: the voice loop speaks the first (the answer) while the rest synthesize."""
    raw = [line.strip() for line in result.splitlines() if line.strip()]
    # Only format our known compact card. Errors, approval messages and unfamiliar responses survive intact.
    if len(raw) < 3 or not any(line.startswith("Open-Meteo ·") for line in raw):
        return speakable(result)
    label = speakable(raw[0])
    day = "Tomorrow:" if when == "tomorrow" else "Today:"
    forecast = next((speakable(line) for line in raw if speakable(line).startswith(day)), None)
    if when in {"today", "tomorrow"} and forecast is None:
        return speakable(result)  # incomplete provider data must not acquire invented numbers
    if when in {"today", "tomorrow"}:
        pieces = [f"{day[:-1]} in {label}: {_spoken_units(forecast[len(day):].strip())}"]
    else:
        pieces = [f"Now in {label}: {_spoken_units(speakable(raw[1]))}"]
        if forecast:
            pieces.append(_spoken_units(forecast))
    for line in raw:
        if line.startswith("🍃"):
            pieces.append("Air now: " + _spoken_units(speakable(line)))
        elif line.startswith("⚠"):
            pieces.append(_spoken_units(speakable(line)))
        elif line.startswith("Open-Meteo ·"):
            pieces.append("Source: " + _spoken_units(speakable(line)))
    return " ".join(piece.rstrip(".") + "." for piece in pieces)


async def execute_intent(intent: VoiceIntent, toolbox) -> VoiceResult:
    result = await toolbox.call(intent.tool, intent.arguments)
    text = weather_sentence(result, intent.arguments["when"]) if intent.tool == "get_weather" else speakable(result)
    return VoiceResult(text, result)
