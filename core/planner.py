class Planner:
    def plan(self, intent, task, guidance=None):
        # v1 Learning: Consult procedural guidance first
        if guidance:
            actions, status = guidance
            if status == "SUCCESS_RECALL":
                # Inject a marker for logging
                # self.logger is not in Planner, so we'll handle logging in Engine
                return actions
            # If FAILURE_AVOID, we fall through to generate a fresh/default plan
            
        # Multi-step composite plan logic
        steps = []
        task_lower = task.lower()

        # 1. Information Retrieval Phase
        if any(kw in task_lower for kw in ["search", "find", "read", "analyze"]):
            steps.append({"action": "local_search", "description": "Locate relevant source files"})
            steps.append({"action": "read_context", "description": "Extract file contents for analysis"})

        # 2. Analysis Phase
        if any(kw in task_lower for kw in ["analyze", "error", "check"]):
            steps.append({"action": "analyze_error", "description": "Scan contents for logical failures"})

        # 3. Action / Persistence Phase
        if any(kw in task_lower for kw in ["create", "write", "report", "save"]):
            filename = "validation_report.txt"
            if "named" in task_lower:
                filename = task_lower.split("named")[1].strip().split(" ")[0]
            steps.append({"action": "create_file", "description": f"Persist findings to {filename}"})

        # 4. Principle Update Phase
        if "safety" in task_lower or "principle" in task_lower:
            steps.append({"action": "update_principles", "description": "Update safety principles based on findings"})

        if not steps:
            steps.append({"action": "default_action", "description": f"Execute general task: {task}"})

        return steps
