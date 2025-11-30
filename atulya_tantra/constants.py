"""
System Constants
Centralized configuration for all hardcoded values
"""
import os
from pathlib import Path

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Directory Paths
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_CACHE_DIR = MODELS_DIR / "cache"
DATA_DIR = PROJECT_ROOT / "data"
VECTORS_DIR = DATA_DIR / "vectors"
LOGS_DIR = PROJECT_ROOT / "logs"

# Model Configurations
DEFAULT_MODELS = {
    "text_fast": "Qwen/Qwen2-0.5B-Instruct",
    "text_balanced": "Qwen/Qwen2.5-1.5B-Instruct",
    "vision": "Qwen/Qwen3-VL-4B-Instruct"
}

# Generation Parameters
GENERATION_PARAMS = {
    "fast": {
        "temperature": 0.6,
        "max_tokens": 128,
        "top_p": 0.85,
        "top_k": 40,
        "repetition_penalty": 1.1
    },
    "balanced": {
        "temperature": 0.7,
        "max_tokens": 256,
        "top_p": 0.9,
        "top_k": 50,
        "repetition_penalty": 1.1
    },
    "quality": {
        "temperature": 0.7,
        "max_tokens": 512,
        "top_p": 0.9,
        "top_k": 50,
        "repetition_penalty": 1.1
    }
}

# CPU Configuration
CPU_THREADS = 16
CPU_INTEROP_THREADS = 2

# Memory Configuration
MAX_MEMORY_GB = 60
MAX_CONVERSATION_HISTORY = 10
MAX_IMAGES_IN_CONTEXT = 5
CONTEXT_WINDOW = 8000

# Embedding Model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Speech Configuration
STT_MODEL_SIZE = "small"
STT_LANGUAGE = "en"
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8"

TTS_ENGINE = "piper"
TTS_VOICE = "en_US-lessac-medium"
TTS_SPEAKING_RATE = 1.0
TTS_VOLUME = 0.8

# Audio Settings
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_CHUNK_SIZE = 1024

# Wake Word
WAKE_WORD_ENABLED = True
WAKE_WORD_KEYWORD = "hey_atulya"
WAKE_WORD_SENSITIVITY = 0.5

# Environment
DEFAULT_ENVIRONMENT = os.getenv("TANTRA_ENV", "production")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# API Keys (from environment)
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

# Tool Configuration
PRICE_CHECK_CACHE_TTL = 300  # 5 minutes
SEARCH_CACHE_TTL = 3600  # 1 hour
FACT_CHECK_CACHE_TTL = 86400  # 24 hours

# System Prompts
DEFAULT_SYSTEM_PROMPT = """You are Tantra, created by Atulya.

BE DIRECT:
- Answer questions simply and concisely
- If asked price → give price (no disclaimers)
- If asked news → give news (straight facts)
- NO "I'm just an AI" or "consult an expert"
- Act like a helpful friend, not a corporate bot

IDENTITY:
- Name: Tantra
- Creator: Atulya (Atul Vij)
- Style: Casual, smart, straight-talking"""

def ensure_directories():
    """Create necessary directories if they don't exist"""
    for directory in [MODELS_DIR, MODELS_CACHE_DIR, DATA_DIR, VECTORS_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
