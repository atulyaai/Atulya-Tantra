"""
Server Configuration
"""

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Server settings
    app_name: str = "Atulya Tantra Server"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # AI settings
    default_model: str = "phi3:mini"
    ollama_host: str = "http://localhost:11434"
    
    # Memory settings
    memory_dir: str = "data/conversations"
    vector_db_path: str = "data/vector_db"
    
    # Voice settings
    tts_voice: str = "en-US-AriaNeural"
    stt_model: str = "base"
    
    # WebSocket settings
    ws_heartbeat_interval: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()

