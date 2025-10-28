"""
Compatibility shim over the new Core.llm router. TinyLlama is default primary.
"""

from typing import Any, Dict, List, Optional

from Core.llm.base import LLMProviderBase
from Core.llm.router import LLMRouter
from Core.llm.providers.tinyllama_provider import TinyLlamaProvider


def _build_router(provider: str = "tinyllama", config: Dict[str, Any] = None) -> LLMRouter:
    providers: Dict[str, LLMProviderBase] = {
        "tinyllama": TinyLlamaProvider(),
    }
    category_map = {"chat": provider}
    return LLMRouter(primary=provider, providers=providers, category_map=category_map)


def get_llm_router(provider: str = "tinyllama", config: Dict[str, Any] = None) -> LLMRouter:
    return _build_router(provider, config or {})


def generate_response(message: str, provider: str = "tinyllama", config: Dict[str, Any] = None,
                     max_tokens: int = 150, context: Optional[List[Dict[str, Any]]] = None) -> str:
    router = get_llm_router(provider, config)
    return router.generate(message, category="chat", context=context, max_tokens=max_tokens)


def count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def get_provider_status(provider: str = "tinyllama") -> Dict[str, Any]:
    try:
        router = get_llm_router(provider)
        is_connected = router.test_connection()
        return {
            "provider": provider,
            "status": "connected" if is_connected else "disconnected",
            "available": is_connected
        }
    except Exception as e:
        return {
            "provider": provider,
            "status": "error",
            "available": False,
            "error": str(e)
        }
