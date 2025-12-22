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

    def run_task(self, input_task):
        trace_id = str(uuid.uuid4())[:8]
        self.governor.set_trace_id(trace_id)
        self.memory.set_trace_id(trace_id)
        extra = {'trace_id': trace_id}
        
        self.logger.info(f"Starting competitive run for task: {input_task}", extra=extra)
        print(f"\n[ENGINE] [{trace_id}] Starting Competitive Evolution...")
        
        if not self.governor.check_permission(input_task):
            return f"Blocked: Task contains forbidden signatures (Trace: {trace_id})"
        
        intent = self.interpreter.classify(input_task)
        guidance, status = self.memory.get_procedural_guidance(intent, input_task)

        # 1. Strategy Plateau Detection
        is_plateau = self._detect_plateau()
        if is_plateau:
            self.logger.warning("PLATEAU DETECTED. Forcing strategy exploration.", extra=extra)
            print("[ENGINE] Plateau Detected! Forcing Mutation.")
            status = "FAILURE_AVOID" # Force exploration in Planner

        # 2. Get Competing Strategy Pairs
        strategy_pairs = self.planner.plan(intent, input_task, (guidance, status) if status != "NO_PATTERN" else None)
        
        results_map = {}
        for s_name, steps in strategy_pairs:
            self.logger.info(f"Executing Strategy: {s_name}", extra=extra)
            print(f"[ENGINE] Evaluating {s_name} strategy...")
            
            s_results = []
            final_file = None
            step_count = 0
            for step in steps:
                res = self.executor.execute(step)
                s_results.append(res)
                step_count += 1
                if step["action"] == "create_file":
                    final_file = step["params"]["filename"]
            
            # Read the actual content produced for scoring
            content_to_score = " ".join(s_results)
            if final_file and os.path.exists(final_file):
                with open(final_file, 'r') as f:
                    content_to_score = f.read()

            # v0.3 Multi-Objective Critique
            eval_report = self.critic.verify(input_task, content_to_score, metadata={"step_count": step_count})
            
            # v0.3 Use the Modular Aggregator (Configured for QUALITY_FIRST by default)
            selection_score = self._aggregate_scores(eval_report, policy="QUALITY_FIRST")
            
            results_map[s_name] = {
                "score": selection_score, # Used for selection
                "report": eval_report,
                "actions": steps,
                "results": s_results,
                "file": final_file
            }
            self.logger.info(f"Strategy {s_name} Selection Score: {selection_score:.2f} (Steps: {step_count})", extra=extra)
            print(f"[ENGINE] Strategy {s_name} Selection Score: {selection_score:.2f} (Steps: {step_count})")

        # 3. Selection & Artifact Management
        winner_name = max(results_map, key=lambda k: (results_map[k]["score"], k == "THOROUGH")) 
        winner = results_map[winner_name]
        
        print(f"[ENGINE] Selection: {winner_name} WINS.")

        # Cleanup: Persist winner, discard loser
        for s_name, data in results_map.items():
            f = data["file"]
            if not f or not os.path.exists(f):
                continue
            if s_name == winner_name:
                # Rename winner to canonical response.md
                target = f.replace(f".{s_name.lower()}", "")
                if os.path.exists(target):
                    os.remove(target)
                os.rename(f, target)
                self.logger.info(f"Artifact Finalized: {target}", extra=extra)
            else:
                # Discard loser
                os.remove(f)
                self.logger.info(f"Artifact Discarded: {f}", extra=extra)

        # 4. Learning & Persistence
        for s_name, data in results_map.items():
            # Persist multi-dimensional report to memory
            self.memory.update_strategy_stats(s_name, data["score"], s_name == winner_name, report=data.get("report"))

        if winner["score"] >= 0.3: # Threshold check (>=)
            self.memory.add_procedural(intent, input_task, winner["actions"], True, trace_id)
            self.memory.add_episodic(input_task, winner["actions"], winner["results"])
            print(f"[ENGINE] Learned from winning strategy {winner_name}.")
        else:
            self.memory.add_procedural(intent, input_task, winner["actions"], False, trace_id)
            print(f"[ENGINE] Learning failure: Score {winner['score']:.2f} below threshold.")

        return f"Completed (Winner: {winner_name}, Score: {winner['score']:.2f})"
