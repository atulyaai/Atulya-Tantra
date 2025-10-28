"""
TinyLlama provider using HuggingFace Transformers for CPU-friendly local inference.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer
    import torch
except Exception:  # Transformers optional at import time
    AutoModelForCausalLM = None
    AutoTokenizer = None
    TextStreamer = None
    torch = None

from ..base import LLMProviderBase


class TinyLlamaProvider(LLMProviderBase):
    """CPU-friendly TinyLlama provider with lazy loading."""

    def __init__(self, model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                 device: str = "cpu", dtype: str = "float16",
                 max_new_tokens: int = 200):
        self.model_name = model_name
        self.device = device
        self.dtype = dtype
        self.max_new_tokens_default = max_new_tokens
        self._model = None
        self._tokenizer = None

    def _ensure_loaded(self):
        if self._model is not None and self._tokenizer is not None:
            return
        if AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError("transformers not installed. Add to requirements and install.")

        torch_dtype = None
        if torch is not None:
            if self.dtype == "float16" and torch.cuda.is_available() and self.device != "cpu":
                torch_dtype = torch.float16
            elif self.dtype == "bfloat16" and hasattr(torch, "bfloat16"):
                torch_dtype = torch.bfloat16

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
        )
        self._model.to(self.device)

    def generate(self, message: str, context: Optional[List[Dict[str, Any]]] = None,
                 max_tokens: int = 150, temperature: float = 0.3) -> str:
        self._ensure_loaded()

        prompt_parts: List[str] = []
        prompt_parts.append("You are a helpful assistant.")
        if context:
            for msg in context[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
        prompt_parts.append(f"user: {message}")
        prompt_parts.append("assistant:")
        prompt = "\n".join(prompt_parts)

        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        generated = self._model.generate(
            **inputs,
            do_sample=True,
            temperature=max(0.1, float(temperature)),
            max_new_tokens=min(self.max_new_tokens_default, int(max_tokens)),
            pad_token_id=self._tokenizer.eos_token_id,
        )
        output_text = self._tokenizer.decode(generated[0], skip_special_tokens=True)
        if "assistant:" in output_text:
            return output_text.split("assistant:")[-1].strip()
        return output_text.strip()

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "name": self.model_name,
            "device": self.device,
            "dtype": self.dtype,
        }


