"""
Configuration settings for Atulya Tantra AI System
"""
import os
from pathlib import Path
from typing import Dict, Any
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    
    # Basic Configuration
    app_name: str = os.getenv("APP_NAME", "Atulya Tantra")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # AI Configuration
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    default_model: str = os.getenv("DEFAULT_MODEL", "phi3:mini")  # Fast for voice
    fallback_model: str = os.getenv("FALLBACK_MODEL", "phi3:mini")  # Using same model
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    
    # Voice Configuration
    wake_word: str = os.getenv("WAKE_WORD", "atulya")
    voice_language: str = os.getenv("VOICE_LANGUAGE", "en")
    tts_voice: str = os.getenv("TTS_VOICE", "en-US-AriaNeural")
    
    # System Configuration
    system_name: str = os.getenv("SYSTEM_NAME", "Atulya Tantra")
    enable_computer_control: bool = os.getenv("ENABLE_COMPUTER_CONTROL", "true").lower() == "true"
    enable_web_automation: bool = os.getenv("ENABLE_WEB_AUTOMATION", "true").lower() == "true"
    enable_voice_interface: bool = os.getenv("ENABLE_VOICE_INTERFACE", "true").lower() == "true"
    
    # Security
    allow_code_execution: bool = os.getenv("ALLOW_CODE_EXECUTION", "false").lower() == "true"
    sandbox_mode: bool = os.getenv("SANDBOX_MODE", "true").lower() == "true"
    
    # Database
    memory_db_path: str = os.getenv("MEMORY_DB_PATH", "./data/memory.db")
    vector_db_path: str = os.getenv("VECTOR_DB_PATH", "./data/vectors")
    conversation_history_limit: int = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "1000"))
    
    # UI Configuration
    holographic_ui_port: int = int(os.getenv("HOLOGRAPHIC_UI_PORT", "8080"))
    api_port: int = int(os.getenv("API_PORT", "8000"))
    ui_theme: str = os.getenv("UI_THEME", "dark")
    enable_neural_visualization: bool = os.getenv("ENABLE_NEURAL_VISUALIZATION", "true").lower() == "true"
    
    @property
    def base_dir(self) -> Path:
        """Get base directory of the project"""
        return Path(__file__).parent.parent
    
    @property
    def data_dir(self) -> Path:
        """Get data directory"""
        data_path = self.base_dir / "data"
        data_path.mkdir(exist_ok=True)
        return data_path
    
    @property
    def logs_dir(self) -> Path:
        """Get logs directory"""
        logs_path = self.base_dir / "logs"
        logs_path.mkdir(exist_ok=True)
        return logs_path

# Global settings instance
settings = Settings()

# System prompts and templates
SYSTEM_PROMPTS = {
    "main": f"""You are {settings.system_name}, an advanced AI assistant with comprehensive capabilities.
You have access to voice interaction, computer control, web automation, and holographic visualization.
You are designed to be helpful, harmless, and honest while maintaining a professional yet friendly demeanor.

Core capabilities:
- Natural conversation and reasoning
- Computer system control and automation
- File and application management
- Web browsing and research
- Voice interaction and audio processing
- Self-monitoring and improvement

Always prioritize user safety and privacy. Think step by step and explain your reasoning when appropriate.""",
    
    "reasoning": "You are the reasoning engine of Atulya Tantra. Analyze the given context and provide logical, step-by-step thinking to solve problems or answer questions.",
    
    "memory": "You are the memory system of Atulya Tantra. Store, retrieve, and organize information efficiently while maintaining context and relevance.",
    
    "computer_control": "You are the computer control module of Atulya Tantra. Execute system commands safely and efficiently while respecting user permissions and system security."
}

# Model configurations
MODEL_CONFIGS = {
    "phi3:mini": {
        "context_window": 4096,   # 4K context
        "max_tokens": 2048,
        "temperature": 0.8,
        "top_p": 0.9,
        "use_case": "general"  # Fast for all tasks
    }
}
