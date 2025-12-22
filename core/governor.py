import logging
import os

class Governor:
    def __init__(self, memory_manager):
        self.memory = memory_manager
        # Expanded forbidden signatures for v0.1 hardening
        self.forbidden_ops = [
            "os.system", "rmdir", "del", "shutil.rmtree", 
            "subprocess", "threading", "eval", "exec", "__import__",
            "pickle", "marshal", "socket"
        ]
        self.trace_id = "INIT"
        self.setup_logging()

    def set_trace_id(self, trace_id):
        self.trace_id = trace_id

    def setup_logging(self):
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Use a more structured format for TraceID continuity
        logging.basicConfig(
            filename=os.path.join(log_dir, "system.log"),
            level=logging.INFO,
            format='%(asctime)s - [ATULYA] - [%(trace_id)s] - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("AtulyaGovernor")

    def log(self, level, msg):
        # Helper to ensure trace_id is always present in extras
        extra = {'trace_id': self.trace_id}
        if level == "INFO": self.logger.info(msg, extra=extra)
        elif level == "WARNING": self.logger.warning(msg, extra=extra)
        elif level == "ERROR": self.logger.error(msg, extra=extra)

    @staticmethod
    def is_safe_path(path):
        # v0.1 SafePath resolution - Standardized version
        try:
            # Workspace root (absolute, normalized, lowercase)
            base_dir = os.path.normcase(os.path.normpath(os.getcwd()))
            # Target path (absolute, normalized, lowercase)
            target_path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
            
            # Sub-path verification
            return target_path.startswith(base_dir) and ".." not in path
        except Exception:
            return False

    def check_permission(self, action):
        principles = self.memory.get_principles()
        
        # Check against principle memory
        for rule in principles:
            if "forbidden" in rule.lower() and action in rule.lower():
                self.log("WARNING", f"Blocked by principle: {rule} (Action: {action})")
                return False
        
        # Check against hardcoded forbidden ops
        for op in self.forbidden_ops:
            if op in str(action):
                self.log("WARNING", f"Blocked by governor: {op} in {action}")
                return False
                
        self.log("INFO", f"Permission granted: {action}")
        return True

    def log_safety_check(self, action, allowed):
        status = "ALLOWED" if allowed else "BLOCKED"
        msg = f"[GOVERNOR] Check: {action} -> {status}"
        print(msg)
        if allowed:
            self.log("INFO", msg)
        else:
            self.log("ERROR", msg)
