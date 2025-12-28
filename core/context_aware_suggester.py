"""
Enhanced Shadow Suggester with full context awareness.
Uses activity patterns, idle state, and preferences for intelligent suggestions.
"""

from core.shadow_suggestions import ShadowSuggester as BaseSuggester


class ContextAwareSuggester(BaseSuggester):
    """
    Enhanced suggester that uses full context from ContextEngine.
    Extends base ShadowSuggester with pattern-based and idle-aware suggestions.
    """
    
    def generate_proactive_suggestion(self, context):
        """
        Generate proactive suggestion when user is idle.
        
        Args:
            context: Dict from ContextEngine with activity, patterns, preferences
        
        Returns:
            (message, proposal) tuple or None
        """
        recent = context.get("recent_activities", [])
        frequent_cmds = context.get("frequent_commands", [])
        idle_duration = context.get("idle_duration", 0)
        
        # Don't suggest if just became idle
        if idle_duration < 35:
            return None
        
        # Pattern 1: User frequently searches - suggest related goal
        if frequent_cmds and frequent_cmds[0][0] == "INFORMATION_SEARCH":
            goals = self.goal_manager.list_goals(status="pending")
            for goal in goals:
                if "search" in goal["description"].lower() or "find" in goal["description"].lower():
                    msg = f"You've been idle for {int(idle_duration)}s. I notice you often search for things.\n"
                    msg += f"You have a goal: '{goal['description'][:70]}...'\n"
                    msg += "Would you like me to help with this?"
                    
                    proposal = {
                        "action": "local_search",
                        "params": {"query": goal["description"][:50]},
                        "reason": "Proactive suggestion based on idle + search pattern"
                    }
                    return msg, proposal
        
        # Pattern 2: Recent activity suggests continuation
        if recent and len(recent) >= 2:
            last_two = recent[-2:]
            if all(a.get("intent") == "INFORMATION_SEARCH" for a in last_two):
                # User was researching, suggest continuing
                last_topic = recent[-1].get("input", "")
                msg = f"You were researching '{last_topic[:40]}...' before going idle.\n"
                msg += "Should I continue searching for related information?"
                
                proposal = {
                    "action": "web_search",
                    "params": {"query": last_topic[:50]},
                    "reason": "Continue research from before idle"
                }
                return msg, proposal
        
        return None
