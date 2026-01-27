import logging
from typing import Dict

logger = logging.getLogger("BrainOrgan")

class OpenAICompatibleAdapter:
    """Adapter for Ollama, vLLM, or LM Studio (Local OpenAI-compatible APIs)."""
    def __init__(self, base_url: str = "http://localhost:11434/v1", api_key: str = "ollama", model: str = "qwen2.5-coder:7b"):
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model
        self._configured = False
        try:
            from langchain_openai import ChatOpenAI
            self.client = ChatOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                model=self.model_name,
                temperature=0.2
            )
            self._configured = True
        except ImportError:
            logger.warning("langchain-openai not installed. OpenAICompatibleAdapter disabled.")

    def query(self, prompt: str) -> Dict:
        if not self._configured: return {"status": "error", "text": "Adapter not configured"}
        try:
            response = self.client.invoke(prompt)
            return {"status": "success", "text": response.content}
        except Exception as e:
            return {"status": "error", "text": str(e)}
