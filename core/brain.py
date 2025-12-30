import json
import os
import time
import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dotenv import load_dotenv

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

class GeminiAdapter:
    """Global Advisor Adapter (Gemini)."""
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._configured = False
        if self.api_key:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-flash-latest')
            self._configured = True

    def query(self, prompt: str, image_data: bytes = None) -> Dict:
        if not self._configured: return {"status": "error", "text": "No API Key"}
        try:
            content = [prompt]
            if image_data:
                import PIL.Image, io
                content.append(PIL.Image.open(io.BytesIO(image_data)))
            resp = self.model.generate_content(content)
            return {"status": "success", "text": resp.text}
        except Exception as e:
            return {"status": "error", "text": str(e)}

class KnowledgeBrain:
    """Fact storage and search gating."""
    def __init__(self, storage_path: str = "memory/knowledge_base.json"):
        self.storage_path = storage_path
        self.kb = self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f: return json.load(f)
        return {"topics": ["SYSTEM", "USER", "GENERAL"], "facts": []}

    def query_knowledge(self, query: str) -> Tuple[List, str]:
        for topic in self.kb["topics"]:
            if topic.lower() in query.lower():
                return [f for f in self.kb["facts"] if f["topic"] == topic], topic
        return [], "GENERAL"

    def add_fact(self, topic: str, content: str):
        self.kb["facts"].append({"id": str(uuid.uuid4())[:8], "topic": topic, "content": content, "timestamp": time.time()})
        with open(self.storage_path, 'w') as f: json.dump(self.kb, f, indent=2)

class CoreLMInterface:
    """Unified LLM Interface (Local + Global)."""
    def __init__(self):
        self.rwkv = RWKVLoader()
        self.gemini = GeminiAdapter()

    def query(self, query: str, facts: List, identity_info: str = None, image_data: bytes = None, stop_tokens: List[str] = None) -> Dict:
        prompt = f"IDENTITY: {identity_info}\nFACTS: {facts}\nQUERY: {query}"
        if image_data or "complex" in query.lower():
            res = self.gemini.query(prompt, image_data)
            if res["status"] == "success": return {"text": res["text"], "source": "global"}
        text, unc, meta = self.rwkv.infer(prompt, stop_tokens=stop_tokens)
        return {"text": text, "source": "local", "uncertainty": unc}

class JARVISAdvisor:
    """Reasoning Advisor for proactive suggestions."""
    def __init__(self, goal_manager, planner, ledger, context):
        self.goal_manager = goal_manager
        self.planner = planner
        self.ledger = ledger
        self.context = context

    def generate_suggestion(self, core_lm=None) -> Tuple[str, Optional[Dict]]:
        goals = self.goal_manager.get_active_goals()
        recent_log = self.context_engine.entries[-3:] if self.context_engine else []
        
        if not goals:
            return "I notice we have no active goals. Should I help you organize the project structure?", {"action": "list_files", "params": {"path": "."}, "reason": "No active goals"}

        # Proactive check based on the first goal
        goal = goals[0]
        if core_lm:
            # High-level reasoning: "What's the next logical step for this goal?"
            # For brevity in this consolidation, we use structured heuristics
            if "clean" in goal['description'].lower() or "consolidate" in goal['description'].lower():
                return f"I'm working on '{goal['description']}'. I suggest listing the core files to verify the current state.", {"action": "list_files", "params": {"path": "core"}, "reason": "Verification of consolidation"}
        
        return f"Continuing with goal: '{goal['description']}'. Shall I proceed with the next step?", {"action": "resume_goal", "id": goal["goal_id"]}
