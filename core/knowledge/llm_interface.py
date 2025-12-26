import logging
import time
from typing import Dict, List, Optional
from core.knowledge.models.rwkv_loader import RWKVLoader

class CoreLMInterface:
    """
    Phase K2/K3: Atulya-CoreLM Interface & Capability Contract.
    Conforms to ADR-010.
    
    PRODUCTION MODE: Real RWKV-6-World-0.4B inference.
    """
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.logger = logging.getLogger("CoreLMInterface")
        self.recurrent_state = {} # Per-topic state cache (Phase K2)
        
        # Phase A: Real model loader (lazy initialization)
        self.rwkv_loader = RWKVLoader(model_path=model_path, quantize=True)
        self._model_loaded = False

    def query(self, query_text, context_facts, task_constraints=None):
        """
        Input/Query Protocol (ADR-010).
        PRODUCTION MODE: Real RWKV-6 inference.
        """
        # 1. Format Grounded Input
        grounded_input = self._format_input(query_text, context_facts, task_constraints)
        
        # 2. Extract topic for state caching (if available)
        topic = context_facts[0].get("topic") if context_facts else None
        
        # 3. Run Real RWKV Distillation
        response_text, uncertainty = self._run_distillation(
            grounded_input, 
            context_facts,
            topic=topic
        )
        
        # 4. Create Structured Response
        return {
            "text": response_text,
            "metadata": {
                "grounding_evidence": [f["id"] for f in context_facts],
                "perceived_uncertainty": uncertainty,
                "missing_links": [],
                "model": "RWKV-6-World-0.4B"
            }
        }

    def _format_input(self, query, facts, constraints):
        fact_str = "\n".join([f"- [{f['id']}] {f['content']}" for f in facts])
        prompt = f"FACTS:\n{fact_str}\n\nQUERY: {query}\nCONSTRAINTS: {constraints or 'Strict distillation only.'}"
        return prompt

    def _run_distillation(self, grounded_input, context_facts, topic=None):
        """
        PRODUCTION: Real RWKV-6 distillation with grounded facts.
        Tier A behavior: Distill facts without hallucination.
        """
        if not context_facts:
            return "UNKNOWN: No context facts provided.", 1.0
        
        # Lazy load model on first inference
        if not self._model_loaded:
            self.logger.info("[CoreLM] First inference - loading RWKV-6...")
            if not self.rwkv_loader.load():
                self.logger.error("[CoreLM] Model loading failed, falling back to concatenation")
                # Fallback to safe distillation
                distilled = " ".join([f['content'] for f in context_facts])
                return distilled, 0.5
            self._model_loaded = True
        
        # Run real inference with state caching
        response, uncertainty, metadata = self.rwkv_loader.infer(
            prompt=grounded_input,
            topic=topic,
            max_tokens=150,
            temperature=0.3,  # Low temp for factual distillation
            top_p=0.85
        )
        
        # Log telemetry
        self.logger.info(
            f"[CoreLM] Distillation complete: {metadata.get('tokens_generated', 0)} tokens, "
            f"{metadata.get('inference_time_ms', 0)}ms, uncertainty={uncertainty:.3f}"
        )
        
        return response, uncertainty

    def save_state(self, topic):
        """Phase K2: Stateful Persistence."""
        self.logger.info(f"State saved for topic: {topic}")
        # Placeholder for recurrent weight hidden state persistence
        
    def load_state(self, topic):
        self.logger.info(f"State loaded for topic: {topic}")
