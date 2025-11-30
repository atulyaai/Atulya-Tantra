"""
Fast Text-Only AI Model
Uses small language models for rapid conversation responses
"""

import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Optional, List, Dict, Any

from .base_model import BaseModel
from .constants import DEFAULT_MODELS

logger = logging.getLogger(__name__)


class TextAI(BaseModel):
    """Fast text-only conversation model"""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: str = 'cpu',
        hf_token: Optional[str] = None,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize TextAI
        
        Args:
            model_name: HuggingFace model name (default: from constants)
            device: Device to run on ('cpu' or 'cuda')
            hf_token: HuggingFace token for model access
            cache_dir: Directory to cache downloaded models
        """
        # Use default model if not specified
        if model_name is None:
            model_name = DEFAULT_MODELS["text_fast"]
        
        super().__init__(model_name, device, hf_token, cache_dir)
    
    def load_model(self):
        """Load the text model"""
        try:
            logger.info("Loading fast text model... This may take a moment.")
            
            # Configure CPU threads
            self.configure_cpu_threads()
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                token=self.hf_token,
                cache_dir=self.cache_dir,
                trust_remote_code=True
            )
            
            # Load model with float32 for better CPU compatibility/speed
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                device_map=self.device,
                token=self.hf_token,
                cache_dir=self.cache_dir,
                trust_remote_code=True
            )
            
            logger.info("✓ Fast text model loaded successfully!")
            
        except Exception as e:
            logger.error(f"Failed to load text model: {e}")
            raise
    
    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.6,
        max_tokens: int = 128,
        top_p: float = 0.85
    ) -> str:
        """
        Generate a text response
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (lower = more focused)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated text response
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        try:
            # Pre-process messages to handle multimodal format
            text_messages = []
            for msg in messages:
                content = msg['content']
                if isinstance(content, list):
                    # Extract text parts from list
                    text_content = " ".join([
                        part['text'] for part in content if part.get('type') == 'text'
                    ])
                    text_messages.append({'role': msg['role'], 'content': text_content})
                else:
                    # Already string
                    text_messages.append(msg)
            
            # Apply chat template
            text = self.tokenizer.apply_chat_template(
                text_messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=top_p,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode only the new tokens
            response = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Text generation error: {e}")
            raise
