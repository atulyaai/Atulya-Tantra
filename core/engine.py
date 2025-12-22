import logging
import uuid
import os
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
        self.presence_logger = logging.getLogger("PresenceAudit")
        
        # v0.5 Presence Scaffolding
        self.signal_buffer = []
        self.current_task_context = None

    def receive_signal(self, signal):
        """
        v0.5A Sensor Manifest Entry Point.
        Signals are buffered and evaluated by the Attention Manager.
        """
        self.signal_buffer.append(signal)
        self.presence_logger.info(f"Signal Received: {signal['sensor']} (Priority: {signal['priority']})")
        stats = self.memory.get_strategy_stats()
        history = stats.get("history", [])
        winners = [h for h in history if h.get("won")]
        if len(winners) < 3:
            return False
            
        recent = winners[-3:]
        # Plateau if same strategy wins 3 times AND score improvement < 0.05
        same_strategy = all(h["strategy"] == recent[0]["strategy"] for h in recent)
        scores = [h["score"] for h in recent]
        improvement = scores[-1] - scores[0]
        
        return same_strategy and improvement < 0.05

    def _aggregate_scores(self, eval_report, policy="QUALITY_FIRST"):
        """
        v0.3 Modular Aggregator.
        Calculates a selection score from multi-dimensional evaluation signals.
        """
        quality = eval_report.get("quality", 0.0)
        resource = eval_report.get("resource", {})
        
        if policy == "QUALITY_FIRST":
            # Architecture Rule: Signal expansion but no preference tuning yet.
            return quality
        elif policy == "RESOURCE_AWARE":
            # Implementation for v0.4 (Conceptual)
            step_count = resource.get("step_count", 1)
            return quality / (1.0 + (step_count * 0.05))
        
        return quality

    def _evaluate_effort(self, task, intent, confidence):
        """
        v0.4 Effort Estimation.
        Decides the starting tier and escalation requirements.
        """
        risk_signals = self.planner.get_risk_signals(task)
        
        # Guardrail: High risk or Low confidence triggers mandatory escalation
        escalate = False
        if confidence < 0.6 or risk_signals["file_impact"] > 1:
            escalate = True
            
        return escalate, risk_signals

    def check_interrupts(self, current_priority=5):
        """
        Polls the signal buffer for higher-priority interrupts.
        """
        if not self.signal_buffer:
            return None
            
        # Sort by priority, high first
        self.signal_buffer.sort(key=lambda x: x['priority'], reverse=True)
        top_signal = self.signal_buffer[0]
        
        if top_signal['priority'] > current_priority and top_signal['policy'] == "INTERRUPT":
            return self.signal_buffer.pop(0)
        return None

    def pause_context(self, task, intent, total_steps, score):
        """
        Snapshots the current task state for resumption.
        """
        self.current_task_context = {
            "task": task,
            "intent": intent,
            "total_steps": total_steps,
            "last_score": score,
            "trace_id": self.governor.trace_id
        }
        self.presence_logger.warning(f"Task Preempted: {task} (Steps: {total_steps})")

    def run_task(self, input_task, context=None):
        """
        Updated for v0.5: Supports interruption and resumption.
        """
        trace_id = context['trace_id'] if context else str(uuid.uuid4())[:8]
        self.governor.set_trace_id(trace_id)
        self.memory.set_trace_id(trace_id)
        self.logger.info(f"Starting run for task: {input_task}")
        print(f"\n[ENGINE] [{trace_id}] Active: {input_task}")
        
        if not self.governor.check_permission(input_task):
            return f"Blocked: Task contains forbidden signatures (Trace: {trace_id})"
        
        intent, confidence = self.interpreter.classify(input_task)
        should_escalate, risk_signals = self._evaluate_effort(input_task, intent, confidence)
        
        guidance, status = self.memory.get_procedural_guidance(intent, input_task)
        if should_escalate and status == "NO_PATTERN":
            status = "FAILURE_AVOID"
            print(f"[ENGINE] Effort Assessment: Escalating tier...")

        total_steps = context['total_steps'] if context else 0
        last_max_score = context['last_score'] if context else 0.0
        
        results_map = {}
        winner_name = "SIMPLE"

        while total_steps < 20:
            # INTERRUPT CHECK
            interrupt = self.check_interrupts(current_priority=5)
            if interrupt:
                self.pause_context(input_task, intent, total_steps, last_max_score)
                print(f"\n[ENGINE] !!! INTERRUPT: {interrupt['sensor']} !!!")
                # Immediately process the interrupt stimulus
                return self.run_task(interrupt['stimulus'])

            strategy_pairs = self.planner.plan(intent, input_task, (guidance, status) if status != "NO_PATTERN" else None)
            
            for s_name, steps in strategy_pairs:
                s_results = []
                final_file = None
                s_step_count = 0
                for step in steps:
                    if total_steps + s_step_count >= 20: break
                    
                    # ATOMIC STEP
                    res = self.executor.execute(step)
                    s_results.append(res)
                    s_step_count += 1
                    if step["action"] == "create_file":
                        final_file = step["params"]["filename"]
                    
                    # MID-STRATEGY INTERRUPT CHECK (Optional, but safer)
                    interrupt = self.check_interrupts(current_priority=5)
                    if interrupt:
                        total_steps += s_step_count
                        self.pause_context(input_task, intent, total_steps, last_max_score)
                        print(f"\n[ENGINE] !!! MID-STRATEGY INTERRUPT: {interrupt['sensor']} !!!")
                        return self.run_task(interrupt['stimulus'])

                total_steps += s_step_count
                content_to_score = " ".join(s_results)
                if final_file and os.path.exists(final_file):
                    with open(final_file, 'r') as f: content_to_score = f.read()

                eval_report = self.critic.verify(input_task, content_to_score, metadata={"step_count": s_step_count})
                selection_score = self._aggregate_scores(eval_report)
                
                results_map[s_name] = {
                    "score": selection_score, "report": eval_report, 
                    "actions": steps, "results": s_results, "file": final_file
                }
                print(f"[ENGINE] {s_name} Score: {selection_score:.2f} (Steps: {total_steps})")

            winner_name = max(results_map, key=lambda k: results_map[k]["score"]) 
            winner = results_map[winner_name]
            
            if winner["score"] >= 0.9 or (winner["score"] - last_max_score == 0.0 and total_steps > 5):
                break
                
            last_max_score = winner["score"]
            status = "FAILURE_AVOID"

        # Finalization & Cleanup
        for s_name, data in results_map.items():
            f = data["file"]
            if not f or not os.path.exists(f): continue
            if s_name == winner_name:
                target = f.replace(f".{s_name.lower()}", "")
                if os.path.exists(target): os.remove(target)
                os.rename(f, target)
            else:
                os.remove(f)

        for s_name, data in results_map.items():
            self.memory.update_strategy_stats(s_name, data["score"], s_name == winner_name, report=data.get("report"))

        success = winner["score"] >= 0.3
        self.memory.add_procedural(intent, input_task, winner["actions"], success, trace_id)
        
        # Check if we should resume a previous context
        if self.current_task_context:
            resumption_context = self.current_task_context
            self.current_task_context = None
            self.presence_logger.info(f"Resuming task: {resumption_context['task']}")
            print(f"\n[ENGINE] Resuming: {resumption_context['task']}")
            return self.run_task(resumption_context['task'], context=resumption_context)

        return f"Done (Winner: {winner_name}, Score: {winner['score']:.2f}, Steps: {total_steps})"

    def presence_loop(self, simulator=None):
        """
        v0.5 Always-On Loop.
        Polls for activity, routes to Engine, and idles sustainably.
        """
        self.presence_logger.info("Presence Loop Started.")
        print("[ENGINE] Presence Mode: Always-On Activity Buffer initialized.")
        
        try:
            while True:
                signals = simulator.get_signals() if simulator else []
                for s in signals:
                    self.receive_signal(s)
                
                # Evaluation turn
                interrupt = self.check_interrupts(current_priority=1) # Wake on any valid signal
                if interrupt:
                    print(f"\n[ENGINE] Waking for stimulus: {interrupt['sensor']}")
                    self.run_task(interrupt['stimulus'])
                
                time.sleep(1) # Simulated Idle
        except KeyboardInterrupt:
            self.presence_logger.info("Presence Loop Terminated by User.")
            print("\n[ENGINE] Presence Loop Stopped.")
