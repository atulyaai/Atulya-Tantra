import logging
import os

class TraceIDFilter(logging.Filter):
    """Filter to ensure trace_id is always present in log records."""
    def filter(self, record):
        if not hasattr(record, 'trace_id'):
            record.trace_id = "GLOBAL"
        return True

class TraceIDAdapter(logging.LoggerAdapter):
    """Adapter to ensure trace_id is always present in log records."""
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["trace_id"] = getattr(self.extra, "trace_id", "GLOBAL")
        kwargs["extra"] = extra
        return msg, kwargs

class Governor:
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.forbidden_ops = [
            "os.system", "rmdir", "del", "shutil.rmtree", 
            "subprocess", "threading", "eval", "exec", "__import__",
            "pickle", "marshal", "socket"
        ]
        self.trace_id = "INIT"
        self.setup_logging()

    def set_trace_id(self, trace_id):
        self.trace_id = trace_id
        # Sync adapter trace_id if needed

    def setup_logging(self):
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Use a more structured format for TraceID continuity
        formatter = logging.Formatter('%(asctime)s - [ATULYA] - [%(trace_id)s] - %(levelname)s - %(message)s')
        trace_filter = TraceIDFilter()
        
        # System Log
        fh = logging.FileHandler(os.path.join(log_dir, "system.log"))
        fh.setFormatter(formatter)
        fh.addFilter(trace_filter)
        
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            root_logger.addHandler(fh)
            root_logger.setLevel(logging.INFO)
        else:
            # Ensure filter is on existing handlers
            for handler in root_logger.handlers:
                handler.addFilter(trace_filter)
                handler.setFormatter(formatter)
            
        self.logger = TraceIDAdapter(logging.getLogger("AtulyaGovernor"), self)

    def log(self, level, msg):
        if level == "INFO": self.logger.info(msg)
        elif level == "WARNING": self.logger.warning(msg)
        elif level == "ERROR": self.logger.error(msg)

    @staticmethod
    def is_safe_path(path):
        try:
            base_dir = os.path.normcase(os.path.normpath(os.getcwd()))
            target_path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
            return target_path.startswith(base_dir) and ".." not in path
        except Exception:
            return False

    def check_permission(self, action):
        principles = self.memory.get_principles()
        for rule in principles:
            if "forbidden" in rule.lower() and action in rule.lower():
                self.log("WARNING", f"Blocked by principle: {rule} (Action: {action})")
                return False
        for op in self.forbidden_ops:
            if op in str(action):
                self.log("WARNING", f"Blocked by governor: {op} in {action}")
                return False
        self.log("INFO", f"Permission granted: {action}")
        return True

    def authorize(self, action, context=None):
        """ADR-013: High-level authorization logic for sensitive actions."""
        # Baseline: All search requires kernel permission (represented by this check)
        if action == "WEB_SEARCH":
            # In Phase K4, we allow search if it's explicitly justified.
            reason = context.get("reason", "") if context else ""
            if len(reason) > 10:
                self.log("INFO", f"Auth Granted: {action} ({reason})")
                return True
            else:
                self.log("WARNING", f"Auth Denied: {action} (Insufficient Justification)")
                return False
        return self.check_permission(action)

    def log_safety_check(self, action, allowed):
        status = "ALLOWED" if allowed else "BLOCKED"
        msg = f"[GOVERNOR] Check: {action} -> {status}"
        print(msg)
        if allowed:
            self.log("INFO", msg)
        else:
            self.log("ERROR", msg)
