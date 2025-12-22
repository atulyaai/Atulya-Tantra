# ADR-005A: Sensor Manifest & Interrupt Policy

## Status
Proposed (v0.5 Embodiment Preparation)

## Context
v0.5 introduces "presence" to Atulya Tantra. This requires a formal contract for how external signals are classified and prioritized to prevent sensory overflow or unauthorized execution triggers.

## Sensor Manifest

| Sensor Class | Channel | Default State | Interrupt Policy | Attention Budget |
| :--- | :--- | :--- | :--- | :--- |
| **USER_DIRECT** | Text Terminal | BUFFER | INTERRUPT | High |
| **USER_VOICE** | Audio Stream | IGNORED | IGNORED (Default) | Medium |
| **SYSTEM_EVENT** | File Watcher | BUFFER | IGNORED | Low |
| **VISION_FEED** | Camera Frame | IGNORED | IGNORED | Low |
| **SYSTEM_TIMER** | Pulse | BUFFER | IGNORED | Ultra-Low |

### State Definitions:
- **IGNORED**: Signal is discarded at the sensor edge. Costs 0 cognition.
- **BUFFER**: Signal is queued for the next Attention Evaluator turn.
- **INTERRUPT**: Signal can trigger immediate pre-plan evaluation (Emergency/Direct Command).

## Global Architectural Invariants
1. **No Direct Path**: No sensor may directly invoke the `Planner` or `Executor`.
2. **Unified Edge**: Every signal MUST pass through the `Attention Manager` (Engine) to be assigned an effort tier.
3. **Budget Precedence**: Global attention budgets (v0.4) supersede all sensor interrupt requests. If the budget is exhausted, even INTERRUPT signals are held in BUFFER.

## Interrupt Protocol
When an INTERRUPT signal is received:
1. **Step-Boundary Wait**: The current `Executor` step is allowed to finish (Atomicity).
2. **Context Persistence**: Current task state is serialized.
3. **Re-Evaluation**: Entry to `Engine._evaluate_effort()` with the new stimulus.
4. **Resume/Preempt**: Decision to persist the current task or switch contexts based on priority weights.

## Consequences
- Protects the cognitive kernel from noisy environments.
- Ensures every external action remains governed and auditable.
- Establishes the foundation for asynchronous behavior without losing deterministic trace logs.
