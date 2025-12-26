"""
Phase C: Vision Model Interface
Discrete image understanding with grounded captions.

Features:
- Lazy model loading
- Image preprocessing (resize, normalize)
- Grounded caption generation
- Privacy guardrails (no persistent storage)
- TraceID logging
"""

import logging
import uuid
from typing import Tuple, Dict, Optional
from pathlib import Path

logger = logging.getLogger("VisionInterface")


class VisionInterface:
    """
    Production vision interface using CLIP for lightweight image understanding.
    For more complex reasoning, can be upgraded to Qwen2.5-VL.
    """
    
    def __init__(self, model_name: str = "clip"):
        """
        Initialize vision interface.
        
        Args:
            model_name: 'clip' for lightweight, 'qwen2.5-vl' for advanced reasoning
        """
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.logger = logger
        
    def load(self) -> bool:
        """
        Load vision model with lazy initialization.
        Returns True if successful, False otherwise.
        """
        if self.model is not None:
            return True
            
        try:
            trace_id = self._generate_trace_id()
            self.logger.info(f"[{trace_id}] Loading vision model: {self.model_name}...")
            
            if self.model_name == "clip":
                return self._load_clip(trace_id)
            elif self.model_name == "qwen2.5-vl":
                return self._load_qwen_vl(trace_id)
            else:
                self.logger.error(f"[{trace_id}] Unknown model: {self.model_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"[{trace_id}] Vision model loading failed: {str(e)}")
            return False
    
    def _load_clip(self, trace_id: str) -> bool:
        """Load CLIP model for lightweight image-text alignment."""
        try:
            from transformers import CLIPProcessor, CLIPModel
            import time
            
            start_time = time.time()
            model_id = "openai/clip-vit-large-patch14"
            
            self.processor = CLIPProcessor.from_pretrained(model_id)
            self.model = CLIPModel.from_pretrained(model_id)
            
            load_time = time.time() - start_time
            self.logger.info(f"[{trace_id}] CLIP loaded in {load_time:.2f}s")
            return True
            
        except ImportError:
            self.logger.error(f"[{trace_id}] transformers not installed. Run: pip install transformers")
            return False
        except Exception as e:
            self.logger.error(f"[{trace_id}] CLIP loading failed: {str(e)}")
            return False
    
    def _load_qwen_vl(self, trace_id: str) -> bool:
        """Load Qwen2.5-VL for advanced multimodal reasoning."""
        try:
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
            import time
            
            start_time = time.time()
            model_id = "Qwen/Qwen2-VL-2B-Instruct"
            
            self.processor = AutoProcessor.from_pretrained(model_id)
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                model_id,
                torch_dtype="auto",
                device_map="cpu"
            )
            
            load_time = time.time() - start_time
            self.logger.info(f"[{trace_id}] Qwen2.5-VL loaded in {load_time:.2f}s")
            return True
            
        except ImportError:
            self.logger.error(f"[{trace_id}] transformers not installed")
            return False
        except Exception as e:
            self.logger.error(f"[{trace_id}] Qwen2.5-VL loading failed: {str(e)}")
            return False
    
    def understand(
        self,
        image_path: str,
        query: Optional[str] = None
    ) -> Tuple[str, float, Dict]:
        """
        Understand image content with optional query.
        
        Args:
            image_path: Path to image file
            query: Optional text query about the image
            
        Returns:
            (description, confidence, metadata)
        """
        trace_id = self._generate_trace_id()
        
        if not self.load():
            return "ERROR: Vision model not loaded", 0.0, {"trace_id": trace_id, "error": "load_failed"}
        
        if not Path(image_path).exists():
            return f"ERROR: Image not found: {image_path}", 0.0, {"trace_id": trace_id, "error": "file_not_found"}
        
        try:
            import time
            from PIL import Image
            
            start_time = time.time()
            image = Image.open(image_path).convert("RGB")
            
            if self.model_name == "clip":
                description, confidence = self._understand_clip(image, query, trace_id)
            elif self.model_name == "qwen2.5-vl":
                description, confidence = self._understand_qwen_vl(image, query, trace_id)
            else:
                return "ERROR: Unknown model", 0.0, {"trace_id": trace_id}
            
            inference_time = time.time() - start_time
            
            metadata = {
                "trace_id": trace_id,
                "inference_time_ms": int(inference_time * 1000),
                "model": self.model_name,
                "image_size": image.size
            }
            
            self.logger.info(
                f"[{trace_id}] Vision understanding complete: '{description[:50]}...', "
                f"{inference_time*1000:.0f}ms, confidence={confidence:.3f}"
            )
            
            return description, confidence, metadata
            
        except Exception as e:
            self.logger.error(f"[{trace_id}] Vision understanding failed: {str(e)}")
            return f"ERROR: {str(e)}", 0.0, {"trace_id": trace_id, "error": str(e)}
    
    def _understand_clip(self, image, query, trace_id) -> Tuple[str, float]:
        """Use CLIP for image-text alignment."""
        import torch
        
        # Default queries if none provided
        if not query:
            candidate_labels = [
                "a photo of a person",
                "a photo of an object",
                "a photo of a scene",
                "a photo of text or document",
                "a photo of nature",
                "a screenshot or diagram"
            ]
        else:
            candidate_labels = [query]
        
        # Process inputs
        inputs = self.processor(
            text=candidate_labels,
            images=image,
            return_tensors="pt",
            padding=True
        )
        
        # Get similarity scores
        outputs = self.model(**inputs)
        logits_per_image = outputs.logits_per_image
        probs = logits_per_image.softmax(dim=1)
        
        # Get best match
        best_idx = probs.argmax().item()
        confidence = probs[0][best_idx].item()
        description = candidate_labels[best_idx]
        
        return description, confidence
    
    def _understand_qwen_vl(self, image, query, trace_id) -> Tuple[str, float]:
        """Use Qwen2.5-VL for advanced reasoning."""
        # Prepare prompt
        if not query:
            query = "Describe this image in detail."
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": query}
                ]
            }
        ]
        
        # Process
        text_prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(
            text=[text_prompt],
            images=[image],
            return_tensors="pt"
        )
        
        # Generate
        output_ids = self.model.generate(**inputs, max_new_tokens=128)
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(inputs.input_ids, output_ids)
        ]
        description = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True
        )[0]
        
        # Confidence estimation (simplified)
        confidence = 0.8  # Qwen2.5-VL is generally high-confidence
        
        return description, confidence
    
    def _generate_trace_id(self) -> str:
        """Generate 8-char TraceID for auditability."""
        return uuid.uuid4().hex[:8]
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Get current memory footprint."""
        import sys
        
        model_size = sys.getsizeof(self.model) if self.model else 0
        processor_size = sys.getsizeof(self.processor) if self.processor else 0
        
        return {
            "model_mb": model_size // (1024 * 1024),
            "processor_mb": processor_size // (1024 * 1024),
            "total_mb": (model_size + processor_size) // (1024 * 1024)
        }
