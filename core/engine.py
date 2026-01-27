from core.perception import PerceptionManager
from core.interpreter import IntentInterpreter
from core.sensors import SensorManifest, SensorOrchestrator, TextSensor, SystemSensor, VoiceSensor, LocalTranscriber, VisionSensor
from core.brain import KnowledgeBrain, CoreLMInterface, JARVISAdvisor
from core.logic import Planner, Executor, Critic
from core.memory import GoalManager, ContextEngine, ConversationManager, Identity
from core.governance import ActionLedger, Governor
from core.finetuner import OfflineEvolution
from core.event_bus import bus as event_bus
import logging
import uuid
import os
import sys
import time

class Engine:
    def __init__(self, memory, governor):
        self.memory = memory
        self.governor = governor
        self.planner = Planner()
        self.executor = Executor(self.governor)
        self.critic = Critic()
        self.event_bus = event_bus
        self.logger = logging.getLogger("AtulyaEngine")
        self.presence_logger = logging.getLogger("PresenceAudit")
        
        # v0.5 Presence Scaffolding
        self.signal_buffer = []
        
        # Modularized Perception & Interpretation
        self.perception = PerceptionManager(self.governor)
        self.interpreter = IntentInterpreter()
        
        # Phase H: Controlled Agency State
        self.pending_suggestion = None  # Stores {action, params, reason} awaiting approval
        self.SAFE_WHITELIST = ["local_search", "read_file", "list_dir", "web_search", "read_context", "ask_user"]
        
        # Phase K4 Search & Knowledge
        self.knowledge_brain = KnowledgeBrain()
        self.core_lm = CoreLMInterface()
        
        # Phase E1/4: System Evolution
        self.evolution = OfflineEvolution(self.core_lm)
        
        # New Contextual Layers
        self.context_engine = ContextEngine()
        self.goal_manager = GoalManager()
        self.action_ledger = ActionLedger()
        self.advisor = JARVISAdvisor(self.goal_manager, self.planner, self.action_ledger, self.context_engine)
        self.conversation_manager = ConversationManager()
        self.identity = Identity()
        
        goals = self.goal_manager.load_goals()
        if goals:
            self.logger.info(f"[Engine] Restored {len(goals)} goals from memory")

    def receive_signal(self, signal):
        """
        ADR-006 Sensor Manifest Entry Point.
        Signals MUST be normalized before buffering.
        """
        if not signal:
            return
            
        self.signal_buffer.append(signal)
        self.presence_logger.info(f"Signal Received: {signal['sensor']} (Priority: {signal['priority']})")

    def _speak(self, text, trace_id):
        """
        SPEECH EGRESS (The Mouth).
        IMPORTANT: All user-visible system speech MUST go through _speak().
        No other component may emit SYSTEM_SAYS.
        """
        if not text: return
        log_msg = f"[SYSTEM_SAYS][{trace_id}] {text}"
        
        try:
            self.logger.info(log_msg)
        except Exception as e:
            # Fallback for log failures (e.g. encoding), ensures voice remains active
            print(f"[ENGINE] Logging Failed: {e}")
            
        print(f"\n{log_msg}")

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
        self.current_task_context = input_task
        trace_id = context.get('trace_id', str(int(time.time()))) if context else str(int(time.time()))
        
        # Update Identity
        self.identity.set_mode("TASK_EXECUTION")
        self.identity.set_responsibility(input_task)
        
        # 1. INTENT CLASSIFICATION
        start_time = time.time()
        intent, confidence = self.interpreter.classify(input_task)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log activity for context awareness (Phase J1)
        self.context_engine.log_activity(input_task, trace_id, intent)
        
        self.event_bus.emit("status", {"state": "THINKING", "task": input_task, "intent": intent})
        print(f"\n[ENGINE] [{trace_id}] Active: {input_task}")
        
        self.governor.set_trace_id(trace_id)
        
        # 1.1 GOVERNANCE CHECK (Autonomy Throttle)
        # Check against forbidden patterns first
        if not self.governor.check_permission(input_task):
             return f"Blocked: Forbidden action detected via Signatures."

        # Check against Policy Brain (Risk vs Confidence)
        decision, is_auto = self.governor.policy_brain.evaluate(input_task, {"confidence": confidence})
        if decision == "ASK":
             msg = f"Throttle: Low confidence ({confidence:.2f}) or High Risk. User approval required."
             self._speak(msg, trace_id)
             # In a real agent, we'd loop for input. For now, we block.
             # We can use the 'pending_suggestion' mechanism if we want to allow user to say 'yes' later.
             # But for strict safety:
             return f"Blocked: {msg}"
        self.logger.info(f"Starting run for task: {input_task}")

        # 1.5 VISUAL REASONING TRIGGER (Phase M1)
        # Note: Non-blocking is handled by the 800ms timeout in the adapter
        if any(kw in input_task.lower() for kw in ["see", "screen", "looking at", "active window", "visible"]):
            self.event_bus.emit("status", {"state": "LOOKING", "task": "Analyzing Screen"})
            visual_data = self.vision_reasoning.describe_screen()
            
            desc = visual_data.get('description', 'Unknown')
            self._speak(f"Exploring visual context: {desc[:100]}...", trace_id)
            
            # Inject structured visual context
            visual_str = f"\n[VISUAL_CONTEXT]: {desc}\n[VISIBLE_OBJECTS]: {', '.join(visual_data.get('objects', []))}"
            input_task = f"{input_task}\n{visual_str}"
            self.logger.info(f"[Vision] Context injected: {desc[:50]}...")

        # 1.6 CONVERSATION CONTEXT INJECTION (Phase L1)
        recent_history = self.conversation_manager.get_recent_context()
        if recent_history:
            input_task = f"[HISTORY]:\n{recent_history}\n\n[NEW_TASK]: {input_task}"
            self.logger.info("[Memory] Context injected from history")

        # 1. CHECK FOR PENDING APPROVAL (Phase H)
        if self.pending_suggestion:
            normalized = input_task.lower().strip()
            approval_triggers = ["yes", "do it", "confirm", "approve", "go ahead", "please", "sure"]
            is_approval = any(t in normalized for t in approval_triggers)
            
            if is_approval:
                # Execute Pending
                proposal = self.pending_suggestion
                self.pending_suggestion = None # Clear immediately
                
                # Check Whitelist (Double Safety)
                if proposal['action'] not in self.SAFE_WHITELIST:
                     msg = f"Safety Block: Action '{proposal['action']}' is not in the Safe Whitelist."
                     self._speak(msg, trace_id)
                     return msg
                     
                self._speak(f"Acknowledged. Executing {proposal['action']}.", trace_id)
                
                # Execute via Executor
                # Executor expects 'step' dict: {action, params}
                try:
                    result = self.executor.execute(proposal)
                    
                    # Record Outcome
                    self.action_ledger.record_outcome(
                        action_type=proposal['action'],
                        outcome="success" if "Error" not in str(result) else "failure", # Approximate
                        context=f"Approved Suggestion: {proposal['action']}",
                        trace_id=trace_id
                    )
                    return f"Executed Approved Action. Result: {result}"
                except Exception as e:
                    return f"Execution Failed: {e}"
            else:
                # Implicit Rejection: Clear State
                if self.pending_suggestion: 
                    # Only clear if it was a suggestion and user said something else
                    # Maybe user said "No" or "Wait"?
                    self.pending_suggestion = None
                    # Proceed to interpret input as new task...

        # 2. SHADOW SUGGESTION TRIGGER
        # If user asks for suggestions, provide them passively WITHOUT execution.
        normalized_task = input_task.lower().strip()
        suggestion_triggers = ["what next", "what should i do", "suggestions", "next step", "any ideas"]
        is_suggestion_request = any(trigger in normalized_task for trigger in suggestion_triggers)
        
        if is_suggestion_request:
            msg, proposal = self.advisor.generate_suggestion(self.core_lm)
            self.pending_suggestion = proposal
            self._speak(msg, trace_id)
            return msg

        event_bus.emit("status", {"state": "THINKING", "task": input_task})
        self.evolution.record_confidence(confidence) 
        
        # Phase E2/K: Grounded Knowledge Retrieval
        facts, topic = self.knowledge_brain.query_knowledge(input_task)
        lm_result = self.core_lm.query(input_task, facts, identity_info=self.identity.get_self_description())
        uncertainty = lm_result["metadata"]["perceived_uncertainty"]
        
        # VISIBILITY: Speak the CoreLM thought (The Brain)
        self._speak(lm_result["text"], trace_id)
        
        # ADR-013: Confidence-Gated Search Trigger
        if uncertainty > 0.4 or topic == "UNKNOWN":
            print(f"[ENGINE] Low Confidence / Unknown Topic: Triggering SearchGate...")
            search_data = self.search_gate.search(input_task, "Knowledge Gap Resolution")
            if search_data:
                # Accumulate new facts (E2 Exposure)
                target_topic = topic if topic != "UNKNOWN" else input_task
                for prefix in ["Research ", "What is ", "Verify ", "Search "]:
                    if target_topic.startswith(prefix):
                        target_topic = target_topic[len(prefix):]
                
                for f_content in search_data["facts"]:
                    self.knowledge_brain.add_fact(target_topic, 
                                                f_content, search_data["source"])
                   # Fallback for implicit "Wait" or general chatter
            pass

        # 3. CORE LOOP EXECUTION
        # Determine Effort/Risk
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

            strategy_pairs = self.planner.plan(intent, input_task, self.core_lm)
            
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
            self.evolution.record_strategy(winner_name) 
            
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
        
        # RECORD OUTCOME (Trust Anchor)
        self.action_ledger.record_outcome(
            action_type=intent,
            outcome="success" if success else "failure",
            context=f"Task: {input_task[:30]}... Strategy: {winner_name}",
            confidence=winner["score"],
            trace_id=trace_id
        )
        
        event_bus.emit("ledger", {
            "action": intent, 
            "outcome": "success" if success else "failure",
            "confidence": winner["score"]
        })
        event_bus.emit("status", {"state": "IDLE", "task": "Waiting for commands"})
        
        if success:
            self.memory.add_episodic(input_task, winner["actions"], winner["results"])

        # Check if we should resume a previous context
        if self.current_task_context:
            # ...
            pass
            
        # Final Status Vocalization
        final_msg = f"Done. Winner: {winner_name}, Score: {winner['score']:.2f}"
        self._speak(final_msg, trace_id)
        
        # Reset Identity
        self.identity.set_mode("STANDBY")
        self.identity.set_responsibility("Waiting for user input")
        
        # 4. SAVE TO CONVERSATION HISTORY (Phase L1)
        self.conversation_manager.add_turn(input_task, final_msg, llm_ref=self.core_lm)

        return f"Done (Winner: {winner_name}, Score: {winner['score']:.2f}, Steps: {total_steps})"

    def presence_loop(self, simulator=None):
        """
        v0.5 Always-On Loop.
        """
        print("[ENGINE] Presence Loop Active (Ctrl+C to stop)")
        event_bus.emit("status", {"state": "IDLE", "task": "Monitoring Sensors"})
        
        last_input_time = time.time()
        has_spoken_idle = False
        
        # Get threshold from context engine (Phase J1)
        IDLE_THRESHOLD = 30.0
        
        # Track goal state to detect external changes
        last_known_active_goals = len(self.goal_manager.get_active_goals())

        self.perception.start()
        
        try:
            while True:
                # 1. Non-blocking Poll
                # ADR-007: Collect and Arbitrate signals from all async channels
                signals = self.perception.collect()
                
                # Check for goal changes to reset idle pulse (Tightening #2)
                current_active_goals = self.goal_manager.get_active_goals()
                if len(current_active_goals) != last_known_active_goals:
                    has_spoken_idle = False
                    last_known_active_goals = len(current_active_goals)

                if signals:

                    has_spoken_idle = False
                    
                    for s in signals:
                        # Generate Trace ID for this interaction
                        trace_id = self.governor.generate_trace_id()
                        self.logger.info(f"[{trace_id}] Input ({s['sensor']}): {s['stimulus']}")
                        
                        # Receive signal
                        self.receive_signal(s)
                        
                        # 2. Execute Task
                        if self.signal_buffer:
                             # Sort by priority, high first
                            self.signal_buffer.sort(key=lambda x: x['priority'], reverse=True)
                            next_stimulus = self.signal_buffer.pop(0)
                            print(f"\n[ENGINE] Waking for stimulus: {next_stimulus['sensor']}")
                            result = self.run_task(next_stimulus['stimulus'], context={'trace_id': trace_id})
                            self.logger.info(f"[{trace_id}] Result: {result}")
                

                else:
                    # IDLE PULSE LOGIC (The Pulse)
                    idle_time = (time.time() - self.context_engine.last_activity)
                    
                if self.context_engine.check_idle() and not has_spoken_idle:
                    # Phase 4: Data-Driven Evolution Pulse
                    self.evolution.pulse(self.action_ledger.entries)
                    
                    # JARVIS Proactive Initiative (Phase 2)
                    self.event_bus.emit("status", {"state": "THINKING", "task": "Generating Suggestion"})
                    
                    msg, proposal = self.advisor.generate_suggestion(self.core_lm)
                    
                    if msg:
                        self._speak(msg, "PROACTIVE_INITIATIVE")
                        self.pending_suggestion = proposal
                        has_spoken_idle = True
                # ADR-007: Mandatory cycle reset for fairness/quotas
                self.perception.reset_cycle()
                
                # Save audit metrics periodically 
                if int(time.time()) % 15 == 0:
                     self.evolution._save() # Atomic background save

                # Simulation Hook (for testing)
                if simulator:
                    should_exit = simulator(self)
                    if should_exit: break

                time.sleep(0.05) # Prevent CPU spin

        except KeyboardInterrupt:
            print("\n[ENGINE] Presence Loop Stopping...")
        except Exception as e:
            self.logger.error(f"Presence Loop Error: {e}")
            time.sleep(1)
            print("\n[ENGINE] Presence Loop Stopped.")
        finally:
            self.perception.stop()
