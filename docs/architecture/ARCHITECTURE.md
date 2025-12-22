# Atulya Tantra - Architecture & Design Report (v1)

## Executive Summary
Atulya Tantra is a cognitive task-execution system designed for high determinism, safety, and observability. It operates on a closed-loop architecture where every action is governed, logged, and evaluated for future learning.

## Core Cognitive Loop
The system follows a strict sequential cycle:
`INPUT → INTENT → PLAN → ACT → CHECK → LEARN → OUTPUT`

1.  **INPUT**: Raw task string from the user.
2.  **INTENT**: Classification into logical categories (Search, File Ops, etc.).
3.  **PLAN**: Decomposition into a series of actionable steps.
4.  **ACT**: Execution of steps via specialized tools under Governor oversight.
5.  **CHECK**: Formal verification of results against initial requirements.
6.  **LEARN**: Persistence of trace data and procedural patterns for future recall.
7.  **OUTPUT**: Final status and TraceID reported to user.

## System Components

### 1. Logical Roles
- **Interpreter**: Classifies task intent using weighted keyword analysis.
- **Planner**: Generates multi-step execution strategies, consulting Procedural Memory for optimizations.
- **Executor**: Dispatches actions to tools and handles error routing.
- **Critic**: Provides a final verdict on task success/failure.
- **Governor**: Enforces safety constraints (SafePath, Forbidden Signatures).

### 2. Memory Architecture
- **Working Memory**: In-memory state for the current loop execution.
- **Episodic Memory**: JSON-based history of all past task traces.
- **Procedural Memory**: Collection of successful and failed step patterns (`SUCCESS_RECALL` / `FAILURE_AVOID`).
- **Principles Memory**: Hardcoded and earned safety rules guiding the Governor.

## Safety & Governance
- **SafePath**: All file operations are confined to the repository root. Path traversal (`..`) is explicitly blocked.
- **Forbidden Signatures**: Intent-level blocking of dangerous commands (eval, exec, subprocess, etc.).
- **TraceID**: Every task is assigned a unique 8-character ID for cross-module log correlation.

## Observability
- **System Log**: Centralized, structured record of every transition, safety check, and cognitive event.
- **Causal Traceability**: Every log line is tagged with a `TraceID`.

---

## v0.2 — The Competitive Evolution Kernel (E++)

The v0.2 phase defines the system as a **self-improving control system** governed by structural competition and mechanical stagnation refusal.

### 1. The Competitive Loop
Atulya Tantra does not wait for failure to improve. Every run follows the **Competitive Execution** pattern:
1. **DUAL PLAN**: Planner selects two structurally distinct strategy classes (e.g., SIMPLE vs. ANALYTICAL).
2. **DUAL ACT**: Both plans are executed independently in a collision-safe sandbox.
3. **CRITIQUE**: Results are scored numerically (0.0 - 1.0) based on Clarity, Structure, and Redundancy.
4. **SELECT**: The higher-scoring strategy wins. Its artifact persists; the loser is discarded.
5. **LEARN**: Strategy statistics and causal lessons are recorded in `memory/strategy_stats.json` and `evolution.log`.

### 2. Structural Strategy Classes
Evolution is driven by **Plan Shape**, not prose:
- **SIMPLE**: `[ create_file ]`
- **ANALYTICAL**: `[ read_context → analyze → create_file ]`
- **THOROUGH**: `[ read_context → analyze → outline → create_file ]`

### 3. Plateau Detection (The Law of Non-Stagnation)
The system is mechanically forbidden from resting on a plateau. A stalemate is detected if:
- The same strategy wins **3 consecutive runs**.
- Average score improvement is **< 0.05**.
In this state, the Engine **forces exploration** of higher-tier strategy classes, regardless of previous success.

### 4. Selection Criteria
| Metric | Method | Threshold |
| :--- | :--- | :--- |
| **Clarity** | Heading count analysis | Max 0.4 |
| **Structure** | Binary marker detection (Summary/Outcome) | 0.3 |
| **Integrity** | Word-frequency redundancy check | 0.3 |

---

## Roadmap: v0.3 — Granular Selection & Resource Awareness (Architecture)

v0.3 increases the **discrimination power** of the competitive evolution kernel by treating resource usage as a first-class evaluation signal. This phase improves the **lens**, not the preference.

### 1. Multi-Objective Evaluation Model
The Critic SHALL support multiple independent evaluation dimensions, including:
- **Quality**: Structural clarity and constraint satisfaction (v0.2 legacy).
- **Resource Usage**: Execution metadata such as step count and tool invocations.

Each dimension is computed and persisted independently, enabling multi-dimensional selection without hard-coding specific efficiency preferences at the architecture level.

### 2. Resource Awareness Signal
The execution engine SHALL expose **execution metadata** (e.g., step count) to the evaluation layer. This signal:
- Does not block execution or alter planning.
- Exists solely to influence selection resolution in the competitive loop.

### 3. The Boundary Rule
- **v0.3 (Selection Resolution)**: "How do we choose better?" (Signal Expansion)
- **v0.4 (Adaptation & Allocation)**: "What do we prefer?" (Policy & Preference)

---

---

## v0.4 — Adaptation & Allocation (OPERATIONAL)

v0.4 introduces the **Attention Manager**, enabling the system to allocate effort intentionally and spend resources as a first-class trade-off.

### 1. The Attention Manager
- **Confidence Escalation**: The Interpreter evaluates its own certainty. Low-confidence triggers an early escalation to high-tier strategies.
- **Risk Signaling**: The Planner reports declarative risk (e.g., file impact). Engine guardrails force structural integrity based on these signals.
- **Run-Level Escalation**: Strategies are escalated **between** execution attempts to preserve auditability and causal coherence.

### 2. Termination Guardrails
- **Step Budget**: Hard cap (20 steps) to prevent resource leakage or infinite loops.
- **Zero-Delta Rule**: Terminate if consecutive attempts yield 0.00 quality improvement (Diminishing Returns).
- **Atomic Execution**: Every execution step is atomic, ensuring safe state persistence at any boundary.

---

## Roadmap: v0.5 — Embodiment & Sensor Guardrails (Future)

v0.5 focuses on the boundary between the cognitive kernel and the real world:
- **Sensor Integration**: Controlled expansion into voice, vision, and system events.
- **Interruption Logic**: Handling asynchronous stimulus and context preemption.
- **Sensor Guardrails**: Defining strict "ignore" and "interrupt" rules for live input.
