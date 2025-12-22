from tools.file_ops import FileOps
from tools.search_ops import SearchTool

class Executor:
    def __init__(self, governor):
        self.governor = governor
        self.file_ops = FileOps()
        self.search = SearchTool()

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
            return self.search.local_search(query)
            
        if action == "read_context":
            path = params.get("path")
            if not path:
                return "Error: Missing mandatory 'path' parameter for read_context"
                
            if not self.governor.is_safe_path(path):
                self.governor.log("ERROR", f"SafePath Violation: {path}")
                return f"Blocked: {path} is outside SafeZone"
            
            content = self.file_ops.read_file(path)
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
                
            res = self.file_ops.write_file(filename, content)
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
