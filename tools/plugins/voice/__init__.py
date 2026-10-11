"""Speech provider contracts used by Atulya voice integrations."""
from .providers import SpeechInput, SpeechOutput, VoiceError
from .local import LocalVoice
from .tts import LocalSupertonicTTS

__all__ = ["LocalSupertonicTTS", "LocalVoice", "SpeechInput", "SpeechOutput", "VoiceError"]
