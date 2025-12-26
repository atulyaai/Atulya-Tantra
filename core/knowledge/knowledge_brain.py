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
    
    def get_stale_facts(self):
        """Phase E: Returns all stale facts across all topics."""
        stale_facts = []
        now = time.time()
        
        for topic_name, topic_data in self.kb["topics"].items():
            facts = topic_data.get("facts", [])
            for fact in facts:
                if now - fact.get("timestamp", 0) > fact.get("ttl", 3600*24*30):
                    stale_facts.append({
                        "topic": topic_name,
                        "fact": fact,
                        "age_days": (now - fact.get("timestamp", 0)) / (3600*24)
                    })
        
        return stale_facts
    
    def mark_fact_refreshed(self, topic_name, fact_id):
        """Phase E: Updates timestamp for a refreshed fact."""
        if topic_name in self.kb["topics"]:
            facts = self.kb["topics"][topic_name].get("facts", [])
            for fact in facts:
                if fact.get("id") == fact_id:
                    fact["timestamp"] = time.time()
                    self.save()
                    self.logger.info(f"Fact Refreshed: [{topic_name}] {fact_id}")
                    return True
        return False
    
    def get_facts_by_topic(self, topic_name):
        """Alias for get_topic_facts for compatibility."""
        return self.get_topic_facts(topic_name)
    
    def store_fact(self, fact_dict):
        """Store a fact from a dictionary (for testing compatibility)."""
        return self.add_fact(
            topic_name=fact_dict.get("topic", "UNKNOWN"),
            content=fact_dict.get("content", ""),
            source=fact_dict.get("source", "manual"),
            confidence=fact_dict.get("confidence", 1.0),
            ttl=fact_dict.get("ttl", 3600*24*30)
        )
