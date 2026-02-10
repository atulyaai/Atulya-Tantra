"""Memory Management System"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages short-term and long-term memory for Atulya
    """

    def __init__(self):
        """Initialize Memory Manager"""
        self.short_term = {}  # Current session memory
        self.long_term = {}   # Persistent memory
        self.task_history = []
        self.experience_log = []
        logger.info("Memory Manager initialized")

    def store_task_result(self, task: str, result: Dict) -> None:
        """
        Store task execution result in memory
        
        Args:
            task: Task description
            result: Task result
        """
        memory_entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "result": result,
            "success": result.get("success", False)
        }
        
        self.task_history.append(memory_entry)
        self.short_term[task] = memory_entry

    def search_similar(self, query: str, threshold: float = 0.7) -> List[Dict]:
        """
        Search for similar past tasks
        
        Args:
            query: Search query
            threshold: Similarity threshold
            
        Returns:
            List of similar tasks
        """
        similar = []
        query_words = set(query.lower().split())
        
        for task, data in self.short_term.items():
            task_words = set(task.lower().split())
            similarity = len(query_words & task_words) / len(query_words | task_words)
            
            if similarity >= threshold:
                similar.append({
                    "task": task,
                    "similarity": similarity,
                    "data": data
                })
        
        return sorted(similar, key=lambda x: x["similarity"], reverse=True)

    def store_experience(self, experience: Dict) -> None:
        """
        Store learning experience
        
        Args:
            experience: Experience data
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            **experience
        }
        self.experience_log.append(entry)

    def get_experiences(self, category: Optional[str] = None) -> List[Dict]:
        """
        Retrieve experiences
        
        Args:
            category: Optional category filter
            
        Returns:
            List of experiences
        """
        if category is None:
            return self.experience_log
        
        return [e for e in self.experience_log if e.get("category") == category]

    def consolidate_memory(self) -> Dict:
        """
        Consolidate short-term to long-term memory
        
        Returns:
            Consolidation summary
        """
        consolidated_count = 0
        
        for task, data in list(self.short_term.items()):
            if data.get("success"):
                self.long_term[task] = data
                consolidated_count += 1
        
        logger.info(f"Consolidated {consolidated_count} successful tasks to long-term memory")
        
        return {
            "consolidated": consolidated_count,
            "long_term_size": len(self.long_term)
        }

    def get_size(self) -> Dict[str, int]:
        """
        Get memory usage statistics
        
        Returns:
            Memory size breakdown
        """
        return {
            "short_term": len(self.short_term),
            "long_term": len(self.long_term),
            "task_history": len(self.task_history),
            "experiences": len(self.experience_log)
        }

    def optimize(self) -> Dict:
        """
        Optimize memory usage
        
        Returns:
            Optimization results
        """
        # Remove oldest entries if memory is too large
        max_short_term = 1000
        max_history = 5000
        
        removed = 0
        
        while len(self.short_term) > max_short_term:
            oldest = min(self.short_term.items(), 
                        key=lambda x: x[1].get("timestamp", ""))
            del self.short_term[oldest[0]]
            removed += 1
        
        while len(self.task_history) > max_history:
            self.task_history.pop(0)
            removed += 1
        
        return {
            "entries_removed": removed,
            "memory_usage": self.get_size()
        }

    def clear_short_term(self) -> int:
        """
        Clear short-term memory
        
        Returns:
            Number of entries cleared
        """
        cleared = len(self.short_term)
        self.short_term.clear()
        return cleared
