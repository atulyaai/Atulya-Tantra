import os
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger("BrainOrgan")

class RWKVLoader:
    """Local LLM Loader (RWKV-6-World-0.4B)."""
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "models/rwkv-6-world-0.4b.pth"
        self.model = None
        self.tokenizer = None

    def load(self) -> bool:
        if self.model is not None: return True
        try:
            # Suppress noisy prints
            import sys, io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()):
                from rwkv.model import RWKV
                from rwkv.utils import PIPELINE
                if not os.path.exists(self.model_path): return False
                self.model = RWKV(model=self.model_path, strategy='cpu fp32')
                self.tokenizer = PIPELINE(self.model, "rwkv_vocab_v20230424")
            return True
        except Exception as e:
            logger.error(f"RWKV Load Failed: {e}")
            return False

    def infer(self, prompt: str, stop_tokens: List[str] = None) -> Tuple[str, float, Dict]:
        if not self.load(): return "Simulation: JARVIS operational.", 0.2, {}
        try:
            from rwkv.utils import PIPELINE_ARGS
            # Tuned for speed and silence
            gen_args = PIPELINE_ARGS(temperature=0.2, top_p=0.8, alpha_frequency=0.2, alpha_presence=0.2, token_stop=[0]) 
            
            # Silent callback to suppress default printing
            def silent_callback(msg, x): return None

            response = self.tokenizer.generate(prompt, token_count=100, args=gen_args, callback=silent_callback)
            
            # Semantic Hard Stops
            if stop_tokens:
                for stopper in stop_tokens:
                    if stopper in response:
                        response = response.split(stopper)[0]
            
            return response.strip(), 0.1, {"model": "RWKV-6-0.4B"}
        except Exception:
            return "JARVIS: Standing by.", 0.5, {}
