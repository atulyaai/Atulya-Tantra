"""
Base Model Class
Abstract base for all AI models with shared functionality
"""
import torch
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path

from .constants import CPU_THREADS, CPU_INTEROP_THREADS
from .utils import format_error

logger = logging.getLogger(__name__)


class BaseModel(ABC):
    """Abstract base class for AI models"""
    
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        hf_token: Optional[str] = None,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize base model
        
        Args:
            model_name: HuggingFace model name
            device: Device to run on ('cpu' or 'cuda')
            hf_token: HuggingFace token for model access
            cache_dir: Directory to cache downloaded models
        """
        self.model_name = model_name
        self.device = device
        self.hf_token = hf_token
        self.cache_dir = cache_dir
        self.model = None
        self.tokenizer = None
        
        logger.info(f"Initializing {self.__class__.__name__} with model: {model_name}")
        logger.info(f"Device: {device}")
        if cache_dir:
            logger.info(f"Model cache directory: {cache_dir}")
    
    def configure_cpu_threads(self):
        """Configure CPU threads for optimal performance"""
        try:
            torch.set_num_threads(CPU_THREADS)
            torch.set_num_interop_threads(CPU_INTEROP_THREADS)
            logger.info(f"✓ Configured for {CPU_THREADS} CPU threads")
        except RuntimeError as e:
            # Already configured or parallel work started
            logger.warning(f"Could not set thread configuration: {e}")
            torch.set_num_threads(CPU_THREADS)  # This one usually works
    
    @abstractmethod
    def load_model(self):
        """Load the model and tokenizer (must be implemented by subclass)"""
        pass
    
    @abstractmethod
    def generate_response(self, *args, **kwargs):
        """Generate response (must be implemented by subclass)"""
        pass
    
    def unload_model(self):
        """Unload model to free memory"""
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("Model unloaded")
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None and self.tokenizer is not None
    
    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model_name}, device={self.device})"
