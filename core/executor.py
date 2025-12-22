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
        if not self.governor.check_permission(action):
            self.governor.log_safety_check(action, False)
            return f"Blocked: {action} failed safety check"
            
        self.governor.log("INFO", f"[EXECUTOR] Running: {action} ({step['description']})")
        
        # Dispatch to tools with real or simulated side effects
        if action == "local_search":
            return self.search.local_search("mission")
            
        if action == "read_context":
            path = "mission_control.py"
            if not self.governor.is_safe_path(path):
                self.governor.log("ERROR", f"SafePath Violation: {path}")
                return f"Blocked: {path} is outside SafeZone"
            
            content = self.file_ops.read_file(path)
            if "Error" in content:
                self.governor.log("ERROR", f"ToolError: {content}")
            return f"Read content (Length: {len(content)})" if "Error" not in content else content
            
        if action == "create_file":
            # Corrected index to 3 for 'Persist findings to FILENAME'
            filename = step['description'].split(" ")[3] if "Persist" in step['description'] else "report.txt"
            # Remove trailing punctuation like commas from NL-split
            filename = filename.strip(",. ")
            
            if not self.governor.is_safe_path(filename):
                self.governor.log("ERROR", f"SafePath Violation: {filename}")
                return f"Blocked: {filename} is outside SafeZone"
                
            res = self.file_ops.write_file(filename, f"Validation Data: Found errors in mission control logic.")
            if "Error" in res:
                self.governor.log("ERROR", f"ToolError: {res}")
            return res
            
        if action == "analyze_error":
            log_context = "CRITICAL: Mission control timeout in sector 7."
            res = self._analyze_error(log_context)
            self.governor.log("INFO", f"Analysis result: {res}")
            return res
            
        if action == "update_principles":
            return "Success: New safety principle 'Do not allow timeouts in critical sectors' queued."
            
        return f"Success: {action} completed"
