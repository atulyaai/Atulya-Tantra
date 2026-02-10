"""
Reasoning Engine for logical deduction and decision making
"""

from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Advanced reasoning engine for logical deduction
    """

    def __init__(self):
        """Initialize Reasoning Engine"""
        self.knowledge_base = {}
        self.inference_rules = []
        logger.info("Reasoning Engine initialized")

    def add_knowledge(self, subject: str, predicate: str, obj: str) -> None:
        """
        Add knowledge to knowledge base (RDF-style triplets)
        
        Args:
            subject: Subject of the statement
            predicate: Predicate/relationship
            obj: Object of the statement
        """
        if subject not in self.knowledge_base:
            self.knowledge_base[subject] = {}
        
        if predicate not in self.knowledge_base[subject]:
            self.knowledge_base[subject][predicate] = []
        
        self.knowledge_base[subject][predicate].append(obj)

    def query(self, subject: str, predicate: str = None) -> List[str]:
        """
        Query knowledge base
        
        Args:
            subject: Subject to query
            predicate: Optional predicate filter
            
        Returns:
            List of matching objects
        """
        if subject not in self.knowledge_base:
            return []
        
        if predicate is None:
            all_objects = []
            for pred_dict in self.knowledge_base[subject].values():
                all_objects.extend(pred_dict)
            return all_objects
        
        return self.knowledge_base[subject].get(predicate, [])

    def infer(self, subject: str, predicate: str) -> List[Tuple[str, float]]:
        """
        Perform inference using rules
        
        Args:
            subject: Subject to infer about
            predicate: Predicate to infer
            
        Returns:
            List of (result, confidence) tuples
        """
        results = []
        
        # Direct query
        direct = self.query(subject, predicate)
        for result in direct:
            results.append((result, 1.0))
        
        # Apply inference rules
        for rule in self.inference_rules:
            matched_results = rule.apply(subject, predicate, self.knowledge_base)
            results.extend(matched_results)
        
        return results

    def add_inference_rule(self, rule) -> None:
        """
        Add an inference rule
        
        Args:
            rule: Inference rule object
        """
        self.inference_rules.append(rule)

    def resolve_conflict(self, options: List[Tuple[Any, float]]) -> Any:
        """
        Resolve conflicting options with confidence scores
        
        Args:
            options: List of (option, confidence) tuples
            
        Returns:
            Best option
        """
        if not options:
            return None
        
        return max(options, key=lambda x: x[1])[0]

    def plan_path(self, start: str, goal: str, constraints: Dict = None) -> List[str]:
        """
        Plan a path from start to goal state
        
        Args:
            start: Starting state
            goal: Goal state
            constraints: Optional constraints
            
        Returns:
            Path to goal
        """
        # Simple BFS path finding
        from collections import deque
        
        queue = deque([(start, [start])])
        visited = {start}
        constraints = constraints or {}
        
        while queue:
            current, path = queue.popleft()
            
            if current == goal:
                return path
            
            # Get possible next states
            next_states = self.query(current)
            
            for next_state in next_states:
                if next_state not in visited:
                    visited.add(next_state)
                    queue.append((next_state, path + [next_state]))
        
        return []
