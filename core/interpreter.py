class Interpreter:
    def classify(self, task):
        # Keyword-based classification with weights
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["search", "find", "look for", "query"]):
            return "INFORMATION_SEARCH"
        if any(kw in task_lower for kw in ["create", "write", "make", "generate"]):
            return "FILE_CREATION"
        if any(kw in task_lower for kw in ["analyze", "fix", "error", "debug", "failure"]):
            return "ERROR_ANALYSIS"
        return "GENERAL_TASK"
