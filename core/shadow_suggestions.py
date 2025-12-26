import logging
from core.goals import GoalManager
from core.planner import Planner
from core.action_ledger import ActionLedger

class ShadowSuggester:
    """
    The Intuition Layer.
    Provides passive, read-only suggestions about next steps based on:
    1. Active Goals (Context)
    2. Planner Logic (Feasibility)
    3. Action Ledger (Confidence)
    
    CRITICAL: This module MUST NOT have access to Executor.
    """
    def __init__(self, goal_manager: GoalManager, planner: Planner, action_ledger: ActionLedger):
        self.goal_manager = goal_manager
        # Use simple assignment to avoid constructor issues. 
        # Planner is assumed to be thread-safe/stateless for planning operations.
        self.planner = planner 
        self.action_ledger = action_ledger

    def generate_suggestion(self) -> tuple[str, dict | None]:
        """
        Generates a spoken suggestion string and a structured proposal.
        Returns (msg, proposal_dict) or (msg, None) if no proposal capable.
        """
        # 1. Get Context
        active_goals = self.goal_manager.get_active_goals()
        if not active_goals:
            return "I don't have any active goals right now. Shall we start something?"

        goal = active_goals[0]
        description = goal['description']
        
        # 2. Dry-Run Plan
        # Heuristic Intent Inference since we don't have the Interpreter here (yet)
        intent = "implement" 
        research_keywords = ["find", "search", "research", "locate", "what is", "read", "verify"]
        if any(w in description.lower() for w in research_keywords):
            intent = "research"
        
        # We need to simulate 'plan' call. 
        # Planner.plan(intent, task, guidance)
        # We pass None for guidance to get raw suggestions.
        try:
            strategy_pairs = self.planner.plan(intent, description, None)
            if not strategy_pairs:
                return f"I'm working on '{description}', but I'm not sure what the next step is."
                
            # Pick the first strategy (usually highest priority/relevance)
            s_name, steps = strategy_pairs[0]
            
            if not steps:
                return f"I'm analyzing '{description}', but I haven't found a concrete step yet."

            next_step = steps[0]
            action_type = next_step["action"]
            
            # 3. Assess Confidence (Action Ledger)
            success_rate = self.action_ledger.get_success_rate(action_type)
            confidence_str = ""
            if success_rate > 0.8:
                confidence_str = f" (Confidence: High, {int(success_rate*100)}% success rate)"
            elif success_rate > 0:
                confidence_str = f" (Confidence: Moderate, {int(success_rate*100)}% success rate)"
            else:
                confidence_str = " (Confidence: Low/Unknown)"

            # 4. Formulate Suggestion and Structured Proposal
            # Format: "One possible next step is <suggestion>. <Prompt>"
            
            # Make the suggestion human-readable
            suggestion_text = f"perform {action_type}"
            if "params" in next_step:
                # E.g. "search for X" or "write file Y"
                if action_type == "local_search":
                    suggestion_text = f"search for '{next_step['params'].get('query', 'info')}'"
                elif action_type == "create_file":
                    suggestion_text = f"create the file '{next_step['params'].get('filename', 'artifact')}'"
                elif action_type == "read_context":
                    suggestion_text = f"read '{next_step['params'].get('path', 'file')}'"

            msg = (f"One possible next step is to {suggestion_text}{confidence_str}. "
                   "Would you like me to do it, explain it, or skip it?")
            
            # Construct the Pending Proposal
            proposal = {
                "action": action_type,
                "params": next_step.get("params", {}),
                "reason": f"Shadow Suggestion (Confidence: {success_rate:.2f})"
            }
            
            return msg, proposal

        except Exception as e:
            return f"I was thinking about '{description}', but got confused: {e}", None
