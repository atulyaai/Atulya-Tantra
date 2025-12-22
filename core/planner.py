class Planner:
    def plan(self, intent, task, guidance=None):
        # v1 Learning: Consult procedural guidance
        stagnation_detected = False
        if guidance:
            actions, status = guidance
            if status == "SUCCESS_RECALL":
                return actions
            if status == "FAILURE_AVOID":
                stagnation_detected = True
            
        # v0.2-E+ Strategy Mutation Mapping
        # Strategies are defined by structural shapes, not semantics.
        
        # 1. Determine Strategy Level (SIMPLE -> ANALYTICAL -> THOROUGH)
        strategy_level = "SIMPLE"
        if stagnation_detected:
            strategy_level = "ANALYTICAL"
            # In a more advanced loop, we would read the previous strategy from memory
            # For this proof of concept, FAILURE_AVOID forces level-up.

        steps = []
        
        if strategy_level == "SIMPLE":
            # Strategy A: [ create_file ]
            steps.append({
                "action": "create_file", 
                "params": {
                    "filename": "artifacts/response.md",
                    "content": "Autonomous summary: System is operational."
                },
                "description": "SIMPLE: Single-step persistence."
            })
            
        elif strategy_level == "ANALYTICAL":
            # Strategy B: [ read_context -> analyze_error -> create_file ]
            steps.append({
                "action": "read_context", 
                "params": {"path": "ARCHITECTURE.md"},
                "description": "ANALYTICAL: Pre-execution context retrieval"
            })
            steps.append({
                "action": "analyze_error", 
                "params": {"context": "architecture_review"},
                "description": "ANALYTICAL: Structural evaluation"
            })
            steps.append({
                "action": "create_file", 
                "params": {
                    "filename": "artifacts/response.md",
                    "content": "## Atulya Tantra v0.2-E+\n\n### Core Summary\n- Evolution loop: ACTIVE\n- Component Health: STABLE\n- Execution Strategy: ANALYTICAL\n\n*Outcome: Multi-step strategy applied to satisfy clarity constraints.*"
                },
                "description": "ANALYTICAL: Derived content persistence"
            })

        if not steps:
            steps.append({
                "action": "default_action", 
                "params": {"task": task},
                "description": f"Standard fallback for: {task}"
            })

        return steps
