from core.sensors.manifest import SensorManifest
from core.sensors.text_sensor import TextSensor
from core.sensors.orchestrator import SensorOrchestrator
from core.sensors.system_sensor import SystemSensor
from core.sensors.voice_sensor import VoiceSensor, LocalTranscriber
from core.sensors.vision_sensor import VisionSensor
from core.knowledge.search_gate import SearchGate
from core.interpreter import Interpreter
from core.planner import Planner
from core.executor import Executor
from core.critic import Critic
from core.governor import TraceIDAdapter
from core.evolution.auditor import DriftAuditor
import logging
import uuid
import os
import sys
import time

class Engine:
    def __init__(self, memory, governor):
        self.memory = memory
        self.governor = governor
        self.interpreter = Interpreter()
        self.planner = Planner()
        self.executor = Executor(governor)
        self.critic = Critic()
        self.logger = TraceIDAdapter(logging.getLogger("AtulyaEngine"), self.governor)
        self.presence_logger = TraceIDAdapter(logging.getLogger("PresenceAudit"), self.governor)
        
        # v0.5 Presence Scaffolding
        self.signal_buffer = []
        self.current_task_context = None
        
        # Phase 1.0 Embodiment
        self.manifest = SensorManifest()
        self.orchestrator = SensorOrchestrator(self.manifest)
        
        # Register Sensors
        self.text_sensor = TextSensor(self.manifest)
        self.system_sensor = SystemSensor(self.manifest)
        
        # Phase 1.0C Voice
        self.transcriber = LocalTranscriber()
        self.voice_sensor = VoiceSensor(self.manifest, self.transcriber)
        
        # Phase 1.0D Vision
        self.vision_sensor = VisionSensor(self.manifest, self.governor)
        
        # Phase K4 Search
        self.search_gate = SearchGate(governor)
        
        # Phase E1: Drift Auditor
        self.auditor = DriftAuditor()
        
        self.orchestrator.register_sensor("TEXT", self.text_sensor, poll_interval=0.1)
        self.orchestrator.register_sensor("SYSTEM", self.system_sensor, poll_interval=0.5)
        self.orchestrator.register_sensor("VOICE", self.voice_sensor, poll_interval=0.5)
        self.orchestrator.register_sensor("VISION", self.vision_sensor, poll_interval=1.0)

    def receive_signal(self, signal):
        """
        ADR-006 Sensor Manifest Entry Point.
        Signals MUST be normalized before buffering.
        """
        if not signal:
            return
            
        self.signal_buffer.append(signal)
        self.presence_logger.info(f"Signal Received: {signal['sensor']} (Priority: {signal['priority']})")

    def _detect_plateau(self):
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
        self.auditor.record_confidence_event(confidence) # Audit: Baseline Calib
        
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
            self.auditor.record_strategy_use(winner_name) # Audit: Strategy Preference
            
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
        
        if success:
            self.memory.add_episodic(input_task, winner["actions"], winner["results"])

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
        Refactored for Phase 1.0B: Fully Asynchronous Multi-Sensor Sensing.
        """
        self.presence_logger.info("Presence Loop Started (Embodiment Phase 1.0D).")
        print("[ENGINE] Presence Mode: Always-On Async Orchestration active.")
        print("[ENGINE] Listeners: TEXT, SYSTEM, VOICE (PTT), VISION (Pull).")
        print("[ENGINE] PTT Controls: 'v' (START), 's' (STOP/SEND).")
        print("[ENGINE] Vision: 'img' (Trigger Discrete Snapshot).")
        
        self.orchestrator.start()
        
        try:
            while True:
                # 1. ADR-007: Collect and Arbitrate signals from all async channels
                signals = self.orchestrator.collect()
                filtered_signals = []
                
                for s in signals:
                    # ADR-008: Intercept PTT tokens from TEXT channel
                    if s["sensor"] == "TEXT":
                        cmd = s["stimulus"].lower().strip()
                        if cmd == "v":
                            self.voice_sensor.start_ptt()
                            print("\n[VOICE] Recording... (Type 's' to stop)")
                            continue
                        elif cmd == "s":
                            stimulus = self.voice_sensor.stop_ptt()
                            if stimulus:
                                self.receive_signal(stimulus)
                            print("\n[VOICE] Stopped and Transcribed.")
                            continue
                        elif cmd == "img":
                            # ADR-012: Manual Vision Pull
                            stimulus = self.vision_sensor.capture_snapshot()
                            if stimulus:
                                self.receive_signal(stimulus)
                            print("\n[VISION] Snapshot captured and analyzed.")
                            continue
                        elif self.voice_sensor.is_capturing:
                            # ADR-008: Capture text as simulated audio during PTT window
                            self.voice_sensor.record(s["stimulus"])
                            continue
                    
                    filtered_signals.append(s)
                
                for s in filtered_signals:
                    self.receive_signal(s)
                
                # 2. Evaluation turn
                if self.signal_buffer:
                    # Sort by priority, high first
                    self.signal_buffer.sort(key=lambda x: x['priority'], reverse=True)
                    next_stimulus = self.signal_buffer.pop(0)
                    print(f"\n[ENGINE] Waking for stimulus: {next_stimulus['sensor']}")
                    self.run_task(next_stimulus['stimulus'])
                
                # ADR-007: Mandatory cycle reset for fairness/quotas
                self.manifest.reset_cycle()
                
                # Save audit metrics periodically (approx every 10 presence cycles)
                if int(time.time()) % 10 == 0:
                    self.auditor.save()
                    
                time.sleep(0.5) # Sustainable polling cycle
        except KeyboardInterrupt:
            self.presence_logger.info("Presence Loop Terminated by User.")
            print("\n[ENGINE] Presence Loop Stopped.")
        finally:
            self.orchestrator.stop()
