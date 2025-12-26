"""
Phase A: RWKV-6-World-0.4B Loader
Conforms to ADR-010: Local LLM Contract (CoreLM)

Features:
- Auto-download from HuggingFace
- CPU-optimized int8 quantization
- Recurrent state caching (per-topic)
- TraceID logging for all inferences
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import uuid

logger = logging.getLogger("RWKVLoader")


class RWKVLoader:
    """
    Production RWKV-6-World-0.4B loader with CPU optimization.
    """
    
    def __init__(self, model_path: Optional[str] = None, quantize: bool = True):
        """
        Initialize RWKV loader.
        
        Args:
            model_path: Path to local model, or None to auto-download
            quantize: Enable int8 quantization for CPU efficiency
        """
        self.model_path = model_path or self._get_default_path()
        self.quantize = quantize
        self.model = None
        self.tokenizer = None
        self.state_cache: Dict[str, any] = {}  # Per-topic recurrent states
        self.logger = logger
        
    def _get_default_path(self) -> str:
        """Get default model cache path."""
        cache_dir = Path.home() / ".cache" / "atulya_tantra" / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return str(cache_dir / "rwkv-6-world-0.4b")
    
    def load(self) -> bool:
        """
        Load RWKV model with lazy initialization.
        Returns True if successful, False otherwise.
        """
        if self.model is not None:
            return True
            
        try:
            trace_id = self._generate_trace_id()
            self.logger.info(f"[{trace_id}] Loading RWKV-6-World-0.4B...")
            
            # Check if model exists locally
            if not self._model_exists():
                self.logger.info(f"[{trace_id}] Model not found, downloading...")
                self._download_model(trace_id)
            
            # Import RWKV (lazy to avoid dependency issues)
            try:
                from rwkv.model import RWKV
                from rwkv.utils import PIPELINE
            except ImportError:
                self.logger.error(f"[{trace_id}] RWKV library not installed. Run: pip install rwkv")
                return False
            
            # Load model with CPU optimization
            start_time = time.time()
            self.model = RWKV(
                model=self.model_path,
                strategy='cpu fp32' if not self.quantize else 'cpu int8'
            )
            self.tokenizer = PIPELINE(self.model, "rwkv_vocab_v20230424")
            
            load_time = time.time() - start_time
            self.logger.info(f"[{trace_id}] Model loaded in {load_time:.2f}s")
            return True
            
        except Exception as e:
            self.logger.error(f"[{trace_id}] Model loading failed: {str(e)}")
            return False
    
    def _model_exists(self) -> bool:
        """Check if model files exist locally."""
        return os.path.exists(self.model_path)
    
    def _download_model(self, trace_id: str):
        """
        Download RWKV-World-0.4B from HuggingFace.
        Tries RWKV-7 first, falls back to RWKV-4 if unavailable.
        """
        try:
            from huggingface_hub import hf_hub_download
            
            # Try RWKV-7 first (latest)
            models_to_try = [
                ("BlinkDL/rwkv-7-world", "RWKV-x070-World-0.4B-v2.9-20250107-ctx4096.pth"),
                ("BlinkDL/rwkv-4-world", "RWKV-4-World-0.4B-v1-20230529-ctx4096.pth"),
            ]
            
            downloaded_path = None
            for model_id, filename in models_to_try:
                try:
                    self.logger.info(f"[{trace_id}] Trying {model_id}/{filename}...")
                    self.logger.info(f"[{trace_id}] This may take several minutes (~800MB download)...")
                    
                    downloaded_path = hf_hub_download(
                        repo_id=model_id,
                        filename=filename,
                        cache_dir=str(Path(self.model_path).parent),
                        resume_download=True
                    )
                    self.logger.info(f"[{trace_id}] Successfully downloaded {model_id}")
                    break
                except Exception as e:
                    self.logger.warning(f"[{trace_id}] {model_id} failed: {str(e)}")
                    continue
            
            if not downloaded_path:
                raise RuntimeError("All model download attempts failed")
            
            # Create copy for consistent path (Windows-compatible)
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            if not os.path.exists(self.model_path):
                import shutil
                shutil.copy2(downloaded_path, self.model_path)
            
            self.logger.info(f"[{trace_id}] Download complete: {self.model_path}")
            
        except ImportError:
            self.logger.error(f"[{trace_id}] huggingface_hub not installed. Run: pip install huggingface_hub")
            raise
        except Exception as e:
            self.logger.error(f"[{trace_id}] Download failed: {str(e)}")
            raise
    
    def infer(
        self,
        prompt: str,
        topic: Optional[str] = None,
        max_tokens: int = 200,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Tuple[str, float, Dict]:
        """
        Run inference with grounded distillation protocol.
        
        Args:
            prompt: Grounded input (formatted with facts)
            topic: Topic key for state caching
            max_tokens: Maximum generation length
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            
        Returns:
            (response_text, uncertainty, metadata)
        """
        trace_id = self._generate_trace_id()
        
        if not self.load():
            return "ERROR: Model not loaded", 1.0, {"trace_id": trace_id, "error": "load_failed"}
        
        try:
            start_time = time.time()
            
            # Load cached state if available
            state = self.state_cache.get(topic) if topic else None
            
            # Tokenize input
            tokens = self.tokenizer.encode(prompt)
            
            # Run forward pass with recurrent state
            output_tokens = []
            logit_entropies = []
            
            for i in range(max_tokens):
                out, state = self.model.forward(tokens if i == 0 else [output_tokens[-1]], state)
                
                # Calculate entropy for uncertainty estimation
                import numpy as np
                probs = np.exp(out) / np.sum(np.exp(out))
                entropy = -np.sum(probs * np.log(probs + 1e-10))
                logit_entropies.append(entropy)
                
                # Sample next token
                token = self._sample_token(out, temperature, top_p)
                output_tokens.append(token)
                
                # Stop on EOS
                if token == 0:
                    break
            
            # Decode response
            response = self.tokenizer.decode(output_tokens)
            
            # Cache state for topic
            if topic:
                self.state_cache[topic] = state
            
            # Calculate uncertainty (normalized mean entropy)
            uncertainty = min(1.0, np.mean(logit_entropies) / 10.0)
            
            inference_time = time.time() - start_time
            
            metadata = {
                "trace_id": trace_id,
                "inference_time_ms": int(inference_time * 1000),
                "tokens_generated": len(output_tokens),
                "mean_entropy": float(np.mean(logit_entropies)),
                "state_cached": topic is not None
            }
            
            self.logger.info(
                f"[{trace_id}] Inference complete: {len(output_tokens)} tokens, "
                f"{inference_time*1000:.0f}ms, uncertainty={uncertainty:.3f}"
            )
            
            return response.strip(), uncertainty, metadata
            
        except Exception as e:
            self.logger.error(f"[{trace_id}] Inference failed: {str(e)}")
            return f"ERROR: {str(e)}", 1.0, {"trace_id": trace_id, "error": str(e)}
    
    def _sample_token(self, logits, temperature: float, top_p: float) -> int:
        """Sample next token with temperature and nucleus sampling."""
        import numpy as np
        
        # Apply temperature
        logits = np.array(logits) / temperature
        probs = np.exp(logits) / np.sum(np.exp(logits))
        
        # Nucleus sampling
        sorted_indices = np.argsort(probs)[::-1]
        sorted_probs = probs[sorted_indices]
        cumsum = np.cumsum(sorted_probs)
        
        cutoff_idx = np.searchsorted(cumsum, top_p)
        nucleus_indices = sorted_indices[:cutoff_idx + 1]
        nucleus_probs = sorted_probs[:cutoff_idx + 1]
        nucleus_probs /= nucleus_probs.sum()
        
        # Sample
        token_idx = np.random.choice(nucleus_indices, p=nucleus_probs)
        return int(token_idx)
    
    def clear_state(self, topic: Optional[str] = None):
        """Clear cached recurrent state."""
        if topic:
            self.state_cache.pop(topic, None)
        else:
            self.state_cache.clear()
    
    def _generate_trace_id(self) -> str:
        """Generate 8-char TraceID for auditability."""
        return uuid.uuid4().hex[:8]
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Get current memory footprint."""
        import sys
        
        model_size = sys.getsizeof(self.model) if self.model else 0
        state_size = sum(sys.getsizeof(s) for s in self.state_cache.values())
        
        return {
            "model_mb": model_size // (1024 * 1024),
            "state_cache_mb": state_size // (1024 * 1024),
            "total_mb": (model_size + state_size) // (1024 * 1024)
        }
