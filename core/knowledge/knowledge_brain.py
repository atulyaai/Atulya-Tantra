import json
import os
import time
import logging

class KnowledgeBrain:
    """
    Phase K1: Knowledge Brain Architecture.
    A persistent, versioned fact store that separates Truth from Weights.
    """
    def __init__(self, storage_path="memory/knowledge_base.json"):
        self.storage_path = storage_path
        self.logger = logging.getLogger("KnowledgeBrain")
        self.kb = self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {"topics": {}}
        return {"topics": {}}

    def save(self):
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.kb, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save KnowledgeBase: {str(e)}")

    def get_topic_facts(self, topic_name):
        """Retrieves facts for a given topic, filtered by TTL."""
        if topic_name not in self.kb["topics"]:
            return []
            
        now = time.time()
        facts = self.kb["topics"][topic_name].get("facts", [])
        
        # Filter stale facts (Simple TTL decay for Phase K)
        active_facts = [f for f in facts if now - f.get("timestamp", 0) < f.get("ttl", 3600*24*30)]
        return active_facts

    def get_all_topics(self):
        return list(self.kb["topics"].keys())

    def add_fact(self, topic_name, content, source, confidence=1.0, ttl=3600*24*30):
        """Adds a verified fact to a topic."""
        if topic_name not in self.kb["topics"]:
            self.kb["topics"][topic_name] = {"facts": []}
        
        fact = {
            "id": f"fact_{int(time.time())}_{len(self.kb['topics'][topic_name]['facts'])}",
            "content": content,
            "source": source,
            "confidence": confidence,
            "timestamp": time.time(),
            "ttl": ttl
        }
        self.kb["topics"][topic_name]["facts"].append(fact)
        self.save()
        self.logger.info(f"Fact Added: [{topic_name}] {content[:50]}...")
        return fact

    def query_knowledge(self, query):
        """Basic topic-based lookup for Phase K."""
        # Simple keyword match for topic selection
        for topic in self.kb["topics"]:
            if topic.lower() in query.lower():
                return self.get_topic_facts(topic), topic
        return [], "UNKNOWN"
