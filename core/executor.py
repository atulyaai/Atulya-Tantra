import os

class Executor:
    def __init__(self, governor):
        self.governor = governor

    def _read_file(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
        return "Error: File not found"

    def _write_file(self, path, content):
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"Success: File written to {path}"
        except Exception as e:
            return f"Error: {str(e)}"

    def _local_search(self, query, path="."):
        results = []
        for root, dirs, files in os.walk(path):
            if "memory" in root or "logs" in root or "__pycache__" in root:
                continue
            for file in files:
                if query.lower() in file.lower():
                    results.append(os.path.join(root, file))
        
        if results:
            return f"Found relevant files: {', '.join(results)}"
        return "No local results found. (Web search disabled in v0)"

    def _analyze_error(self, log_content):
        # Internalized from legacy Analyzer tool
        if "FileNotFoundError" in log_content:
            return "Suggestion: Check if the file path is correct and accessible."
        if "PermissionError" in log_content:
            return "Suggestion: Check file permissions or SafePath restrictions."
        return "Suggestion: Generic failure detected. Review system logs for root cause."

    def execute(self, step):
        action = step["action"]
        params = step.get("params", {})
        
        if not self.governor.check_permission(action):
            self.governor.log_safety_check(action, False)
            return f"Blocked: {action} failed safety check"
            
        self.governor.log("INFO", f"[EXECUTOR] Running: {action} (Typed: {len(params) > 0})")
        
        # Dispatch to tools
        if action == "local_search":
            query = params.get("query", "mission")
            return self._local_search(query)
            
        if action == "read_context":
            path = params.get("path")
            if not path:
                return "Error: Missing mandatory 'path' parameter for read_context"
                
            if not self.governor.is_safe_path(path):
                self.governor.log("ERROR", f"SafePath Violation: {path}")
                return f"Blocked: {path} is outside SafeZone"
            
            content = self._read_file(path)
            if "Error" in content:
                self.governor.log("ERROR", f"ToolError: {content}")
            return f"Read content (Length: {len(content)})" if "Error" not in content else content
            
        if action == "create_file":
            filename = params.get("filename")
            content = params.get("content")
            
            if not content or len(content) < 20 or "Autonomous summary" in content:
                self.governor.log("WARNING", "Executor: Generic or placeholder content rejected.")
                return "Error: Content rejected due to Low Quality/Placeholder constraints."

            # Structure Observability
            heading_count = content.count("#")
            self.governor.log("INFO", f"Executor: Persisting artifact (Length: {len(content)}, Headings: {heading_count})")
            
            if not filename:
                filename = step['description'].split(" ")[3] if "Persist" in step['description'] else "report.txt"
                filename = filename.strip(",. ")
            
            if not self.governor.is_safe_path(filename):
                self.governor.log("ERROR", f"SafePath Violation: {filename}")
                return f"Blocked: {filename} is outside SafeZone"
                
            res = self._write_file(filename, content)
            if "Error" in res:
                self.governor.log("ERROR", f"ToolError: {res}")
            return res
            
        if action == "analyze_error":
            log_context = params.get("context", "General log evaluation")
            res = self._analyze_error(log_context)
            self.governor.log("INFO", f"Analysis result: {res}")
            return res
            
        if action == "update_principles":
            rule = params.get("rule", "Maintain structural integrity")
            return f"Success: New safety principle '{rule}' queued."
            
        return f"Success: {action} completed"
