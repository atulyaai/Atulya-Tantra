import os
import logging

class Planner:
    """Strategy generator and risk assessor."""
    def get_risk_signals(self, task: str) -> dict:
        task = task.lower()
        signals = {"file_impact": 0, "depth": 0}
        if any(kw in task for kw in ["all", "multiple", "files"]): signals["file_impact"] = 3
        elif "create" in task or "write" in task: signals["file_impact"] = 1
        signals["depth"] = task.count("/") + task.count("\\")
        return signals

    def plan(self, intent: str, task: str, lm_interface=None) -> list:
        # Default Hardcoded Strategies
        strategies = {
            "SIMPLE": [{"action": "create_file", "params": {"filename": "artifacts/response.md", "content": "System operational."}, "description": "Single-step persistence."}],
            "ANALYTICAL": [
                {"action": "list_files", "params": {"path": "."}, "description": "System discovery"},
                {"action": "create_file", "params": {"filename": "artifacts/analysis.md", "content": "Analyzing structure..."}, "description": "Structural audit"}
            ]
        }
        
        # Dynamic LLM Planning Expansion
        if lm_interface and intent == "GENERAL_TASK":
            # In a real scenario, we'd query the LM here to get steps.
            prompt = f"""Task: {task}
Create a plan using ONLY these actions: list_files, read_file, create_file, delete_file, search_files.
Format: Step X: action=NAME key=value key=value
Example: Step 1: action=list_files path=.
"""
            lm_result = lm_interface.query(prompt, [], stop_tokens=["\nStep 4", "Observation:"])
            text_plan = lm_result["text"]
            
            # Simple Parser
            dynamic_steps = []
            for line in text_plan.split('\n'):
                if "action=" in line:
                    try:
                        parts = line.split("action=")[1].split()
                        action = parts[0]
                        params = {}
                        for p in parts[1:]:
                            if "=" in p:
                                k, v = p.split("=", 1)
                                params[k] = v
                        dynamic_steps.append({"action": action, "params": params, "description": "Dynamic Step"})
                    except: pass
            
            if dynamic_steps:
                strategies["DYNAMIC"] = dynamic_steps
            else:
                 # Fallback if parsing fails
                 strategies["DYNAMIC"] = [
                    {"action": "list_files", "params": {"path": "."}, "description": "Fallback discovery"}
                ]

        selected = [("SIMPLE", strategies["SIMPLE"]), ("ANALYTICAL", strategies["ANALYTICAL"])]
        if "DYNAMIC" in strategies: selected.append(("DYNAMIC", strategies["DYNAMIC"]))
        
        return selected

class Executor:
    """Action implementation layer."""
    def __init__(self, governor):
        self.governor = governor

    def execute(self, step):
        action = step["action"]
        params = step.get("params", {})
        if not self.governor.check_permission(action): return f"Blocked: {action}"
        
        if action == "read_context" or action == "read_file":
            path = params.get("path")
            if not path or not os.path.exists(path): return "Error: File missing"
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f: content = f.read()
                return f"Read content of {path} (Len: {len(content)})"
            except Exception as e: return f"Error reading {path}: {e}"

        if action == "create_file" or action == "write_file":
            fname = params.get("filename", "output.txt")
            content = params.get("content", "")
            try:
                os.makedirs(os.path.dirname(fname), exist_ok=True)
                with open(fname, 'w', encoding='utf-8') as f: f.write(content)
                return f"Success: {fname} written"
            except Exception as e: return f"Error writing {fname}: {e}"

        if action == "list_files" or action == "ls":
            path = params.get("path", ".")
            try:
                files = os.listdir(path)
                return f"Files in {path}: {', '.join(files[:20])}" + ("..." if len(files) > 20 else "")
            except Exception as e: return f"Error listing {path}: {e}"

        if action == "search_files" or action == "grep":
            query = params.get("query", "").lower()
            path = params.get("path", ".")
            results = []
            try:
                for root, dirs, files in os.walk(path):
                    if any(x in root for x in [".git", "__pycache__"]): continue
                    for file in files:
                        if file.endswith(('.py', '.md', '.txt')):
                            fpath = os.path.join(root, file)
                            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                                if query in f.read().lower(): results.append(fpath)
                                if len(results) > 5: break
                    if len(results) > 5: break
                return f"Search results for '{query}': {', '.join(results)}" if results else "No matches found"
            except Exception as e: return f"Error searching: {e}"

        if action == "delete_file":
            path = params.get("path")
            if not path or not os.path.exists(path): return "Error: File missing"
            if not self.governor.check_permission(f"delete {path}"): return "Blocked by Governor"
            try:
                os.remove(path)
                return f"Successfully deleted {path}"
            except Exception as e: return f"Error deleting {path}: {e}"
            
        return f"Executing {action} (Unimplemented or Generic)"

class Critic:
    """Result evaluation and scoring."""
    def verify(self, task, results, metadata=None):
        headings = results.count("#")
        clarity = min(headings * 0.2, 0.4)
        structure = 0.3 if "Summary" in results else 0.0
        score = clarity + structure + 0.3 # 0.3 flat bonus for unique words simulation
        return {"quality": score, "resource": {"steps": metadata.get("step_count", 0) if metadata else 0}}
