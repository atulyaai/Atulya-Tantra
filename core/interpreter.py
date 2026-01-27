class IntentInterpreter:
    """Classifies user input into actionable intents."""
    @staticmethod
    def classify(task: str):
        task_lower = task.lower()
        confidence = 0.7 
        
        # High-confidence matches
        if any(kw in task_lower for kw in ["search", "find", "look for", "query"]):
            return "INFORMATION_SEARCH", 1.0
        if any(kw in task_lower for kw in ["create", "write", "make", "generate"]):
            return "FILE_CREATION", 1.0
        if any(kw in task_lower for kw in ["analyze", "fix", "error", "debug", "failure"]):
            return "ERROR_ANALYSIS", 1.0
        
        # Low confidence/Vague detection
        if len(task_lower.split()) < 3:
            confidence = 0.5
            
        return "GENERAL_TASK", confidence
