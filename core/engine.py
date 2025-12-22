import logging
import uuid
from core.interpreter import Interpreter
from core.planner import Planner
from core.executor import Executor
from core.critic import Critic

class Engine:
    def __init__(self, memory, governor):
        self.memory = memory
        self.governor = governor
        self.interpreter = Interpreter()
        self.planner = Planner()
        self.executor = Executor(governor)
        self.critic = Critic()
        self.logger = logging.getLogger("AtulyaEngine")

    def run_task(self, input_task):
        # v0.1 TraceID Generation
        trace_id = str(uuid.uuid4())[:8]
        self.governor.set_trace_id(trace_id)
        self.memory.set_trace_id(trace_id)
        extra = {'trace_id': trace_id}
        
        self.logger.info(f"Starting loop for task: {input_task}", extra=extra)
        print(f"\n[ENGINE] [{trace_id}] Starting loop for: {input_task}")
        
        # v0.1 Early Threat Detection
        if not self.governor.check_permission(input_task):
            self.logger.error(f"Threat detected in input: {input_task}", extra=extra)
            return f"Blocked: Task contains forbidden signatures (Trace: {trace_id})"
        
        # 1. INPUT -> INTENT
        intent = self.interpreter.classify(input_task)
        self.memory.update_working("intent", intent)
        self.logger.info(f"Classified intent: {intent}", extra=extra)
        print(f"[ENGINE] Intent: {intent}")

        # v1 Learning: Fetch procedural guidance
        guidance, status = self.memory.get_procedural_guidance(intent, input_task)
        if status == "SUCCESS_RECALL":
            self.logger.info(f"Learning Insight: SUCCESS_RECALL pattern applied for '{input_task[:30]}...'", extra=extra)
            print(f"[ENGINE] Learning Insight: Applying previously successful pattern.")
        elif status == "FAILURE_AVOID":
            self.logger.info(f"Learning Insight: FAILURE_AVOID detected. Generating alternative plan.", extra=extra)
            print(f"[ENGINE] Learning Insight: Avoiding previously failed pattern.")
        else:
            self.logger.info(f"Learning Status: NO_PATTERN exists for '{input_task[:30]}...'", extra=extra)

        # 2. INTENT -> PLAN
        steps = self.planner.plan(intent, input_task, (guidance, status) if status != "NO_PATTERN" else None)
        self.memory.update_working("plan", steps)
        self.logger.info(f"Generated steps: {steps}", extra=extra)
        print(f"[ENGINE] Plan: {steps}")

        # 3. PLAN -> ACT
        results = []
        for step in steps:
            res = self.executor.execute(step)
            results.append(res)
            self.logger.info(f"Execution result for {step['action']}: {res}", extra=extra)
        self.memory.update_working("results", results)

        # 4. ACT -> CHECK
        is_valid, feedback = self.critic.verify(input_task, " ".join(results))
        self.logger.info(f"Critique outcome: {is_valid} - {feedback}", extra=extra)
        print(f"[ENGINE] Check result: {feedback}")

        # 5. CHECK -> LEARN
        if is_valid:
            self.memory.add_episodic(input_task, steps, results)
            # v1 Learning: Record success
            self.memory.add_procedural(intent, input_task, steps, True, trace_id)
            self.logger.info("Task successful. Learned and stored in procedural memory.", extra=extra)
            print("[ENGINE] Learned from success")
        else:
            # v1 Learning: Record failure
            self.memory.add_procedural(intent, input_task, steps, False, trace_id)
            self.logger.error(f"Task failed verification: {feedback}", extra=extra)
            print("[ENGINE] Failed to learn - non-deterministic outcome")

        # 6. LEARN -> OUTPUT
        return f"Task Completed (Trace: {trace_id})" if is_valid else f"Task Failed (Trace: {trace_id})"
