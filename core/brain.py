import json
import os
import time
import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dotenv import load_dotenv

# Import modular adapters
from core.adapters.rwkv import RWKVLoader
from core.adapters.openai import OpenAICompatibleAdapter
from core.adapters.gemini import GeminiAdapter

logger = logging.getLogger("BrainOrgan")

class KnowledgeBrain:
    """Fact storage and search gating."""
    def __init__(self, storage_path: str = "memory/knowledge_base.json"):
        self.storage_path = str(Path(storage_path).absolute())
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
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f: json.dump(self.kb, f, indent=2)

class CoreLMInterface:
    """Unified LLM Interface (Local RWKV + Local OpenAI + Global Gemini)."""
    def __init__(self):
        self.rwkv = RWKVLoader()
        self.local_openai = OpenAICompatibleAdapter()
        self.gemini = GeminiAdapter()
        # Default strategy order
        self.preferred_local = "openai" # "openai" or "rwkv"

    def query(self, query: str, facts: List, identity_info: str = None, image_data: bytes = None, stop_tokens: List[str] = None) -> Dict:
        prompt = f"IDENTITY: {identity_info}\nFACTS: {facts}\nQUERY: {query}"
        
        # 1. Vision or High-Complexity tasks go to Gemini
        if image_data or "complex" in query.lower() or "reason deeply" in query.lower():
            res = self.gemini.query(prompt, image_data)
            if res["status"] == "success": return {"text": res["text"], "source": "global-gemini"}

        # 2. Local OpenAI-compatible (Ollama/vLLM) - The modern choice
        if self.preferred_local == "openai" and self.local_openai._configured:
            res = self.local_openai.query(prompt)
            if res["status"] == "success":
                return {"text": res["text"], "source": f"local-{self.local_openai.model_name}"}

        # 3. Fallback to classic RWKV if available
        text, unc, meta = self.rwkv.infer(prompt, stop_tokens=stop_tokens)
        return {"text": text, "source": "local-rwkv", "uncertainty": unc}

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
