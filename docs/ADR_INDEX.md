## ADR-003: Granular Selection & Resource Awareness

**Status:** Accepted
**Phase:** v0.3
**Decision Type:** Architectural Capability Expansion

### Context

Atulya Tantra v0.2-E++ demonstrated stable competitive evolution but showed early signs of **score saturation** and **strategy dominance** due to single-objective evaluation.

Long-run evolutionary stability requires finer discrimination between behaviors that meet baseline quality thresholds.

---

### Decision

Introduce **multi-objective evaluation capability** and **resource-awareness signals** into the selection process.

This decision:

* expands *what is observable* to the evolution kernel
* does not define behavioral preferences
* does not alter learning, safety, or tools

---

### Architectural Commitments

1. The evaluation layer shall support **multiple independent fitness dimensions**.
2. Execution metadata (e.g., step count) shall be exposed as **non-blocking signals**.
3. Strategy pairing shall support **dynamic selection models**.
4. Aggregation logic shall remain **configurable and policy-neutral**.

---

### Explicit Non-Goals

This decision does not:

* define scoring weights
* optimize for efficiency or minimality
* bias strategy selection
* alter memory semantics
* introduce cost budgets

---

### Consequences

**Positive**

* Increased discrimination between strategies
* Reduced score saturation
* Improved long-run evolvability

**Risks**

* Potential efficiency bias if aggregation is misconfigured
* Increased evaluation complexity

**Mitigations**

* Forced exploration remains binding
* Aggregation policies deferred to later phases

---

### Relationship to Future Phases

v0.3 enables v0.4 by:

* exposing necessary signals
* preserving architectural flexibility

v0.4 will address **resource allocation and preference policy**, not v0.3.

---

## ADR-004: v0.4 Adaptation & Allocation Guardrails (Jarvis Mode)

**Status:** Proposed
**Phase:** v0.4
**Decision Type:** Architectural Boundary Definition

### Context
Atulya Tantra v0.3 provided the **selection resolution** (the "lens") to see quality vs. resources. v0.4 must now provide the **attention manager**—the decision layer for *how much* to spend on a task. 

Jarvis Mode requires "always-on" readiness where effort must be intentional, not just exhaustive.

---

### 1. Decision Boundaries

#### 1.1 When is SIMPLE enough?
The system SHALL default to and prefer **SIMPLE** (Tier-1) execution if:
- Input matches a high-confidence `SUCCESS_RECALL` pattern.
- Task is defined as "Pure State Retrieval" (e.g., "What is the current version?").
- Predicted quality delta between SIMPLE and higher tiers is **< 0.1** (based on historical `strategy_stats`).

#### 1.2 When to Escalate (ANALYTICAL / THOROUGH)?
The system SHALL escalate strategy tier if:
- **Ambiguity**: Classification confidence of `Interpreter` is below a defined threshold.
- **Risk**: Task signature involves high-impact file operations (multiple files, deep directory changes).
- **Failure Feedback**: The previous attempt resulted in a `FAILURE_AVOID` status.
- **Stagnation**: The current tier has reached a Quality Plateau (v0.2-E++ rule), yet requirements remain unmet.

#### 1.3 When to Stop (Capping Effort)?
The system SHALL terminate a task attempt and report a "Budget Exhausted" status if:
- **Diminishing Returns**: Multiple runs show 0.00 Quality improvement despite strategy escalation.
- **Complexity Cap**: Total execution steps across the sequence exceed a hard-coded "Safety Budget" (e.g., 20 steps).
- **Circular Conflict**: The system is alternating between two strategies without reaching the success threshold.

---

### 2. Operational Guardrails

#### 2.1 Interruption Handling
In an always-on "Jarvis" state, new inputs may arrive mid-run.
- **Atomic Execution**: Once a strategy run begins, it SHALL complete its current step (atomic action) before context-switching.
- **Preemption**: High-priority safety signals SHALL preempt any current strategy execution.
- **Context Persistence**: Mid-run interruptions MUST be logged as "Preempted" in `episodic.json` to allow later resumption.

#### 2.2 System Invariants
Specific core attributes are **immutable** and cannot be altered by adaptive allocation policies:
- **Safety**: Governor rules and SafePath enforcement are non-negotiable.
- **Learning Integrity**: Every run, regardless of tier or budget, MUST be recorded in `memory/`.
- **Contracts**: The Typed Action Schema (v0.2) is the ONLY way for Planner and Executor to communicate.

---

### Consequences

**Positive**
- **Intentionality**: Effort is spent where most needed, preserving resources for simple requests.
- **Resilience**: The system gracefully handles vague or high-risk requests through escalation.
- **Verifiability**: Allocation decisions are logged and traceable.

**Risks**
- **Under-estimation**: The system might incorrectly stick to SIMPLE for tasks with hidden complexity. (Mitigation: Failure-driven escalation).
- **Latency**: Escalation logic adds a slight overhead to the planning transition.

---

### Relationship to Future Phases
v0.4 guardrails enable safe **Embodiment** (v0.5) by ensuring the system won't spiral into infinite loops or resource-heavy hallucinations when real-world sensors are added.

---

# ADR-005: v0.5 Embodiment & Sensor Guardrails

## Status
Proposed (v0.5 Design Phase)

## Context
Atulya Tantra has a stable cognitive kernel and attention manager. v0.5 aims to extend the system into real-world interaction (sensing and continuous execution).

## Decision
- **Sensor Manifest**: Define a strict permission manifest for external inputs (voice, vision, filesystem events).
- **Asynchronous Execution**: Implement an interruption-safe loop capable of prioritizing real-time sensors over background cognition.
- **Sensor Guardrails**: Establishing "Ignore" and "Interrupt" policies to protect the kernel from sensory noise.

## Consequences
- Increased complexity in the Control Loop.
- Necessity for sophisticated context preemption.
- Transition from "Turn-Based" to "Always-On" behavior.

---

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

---

# ADR-006: Phase 1.0 Real-World Sensor Integration Guardrails

## Status
Accepted / Locked (Phase 1.0 Phase Gate)

## Context
Atulya Tantra has passed the Presence Simulation gate. Phase 1.0 introduces real-world sensors. To prevent the "Fragile Agency" problem in a noisy, real-world environment, strict architectural guardrails must be defined before any external drivers are integrated.

## 1. Sensor Priority & Ordering
Real-world sensors SHALL be integrated in a sequential, low-entropy to high-entropy order:
1. **TEXT** (Terminal/Standard Input) - *Lower Noise*
2. **VOICE** (Audio Sampling) - *Medium Noise*
3. **VISION** (Camera Frames) - *High Noise*

**Vision Policy**: VISION sensors SHALL be disabled by default at startup and may only be enabled via an explicit, session-scoped `USER_DIRECT` authorization. Vision state MUST reset to disabled on process restart.

## 2. Sampling & Duration Limits
To prevent cognitive flooding:
- **Rate-Limiting**: Every sensor MUST have a hard-coded sampling period (e.g., 1fps for Vision, 16kHz for Voice).
- **Episodic Buffering**: Data must be buffered into discrete "Episodes." No continuous, unbounded streams are allowed to reach the Planner directly.
- **Cognitive Decay**: Signals older than T (e.g., 5 seconds) are automatically dropped if they haven't been evaluated.
- **Normalization Invariant**: No real-world sensor may enqueue stimuli directly. All sensor output MUST pass through the Sensor Manifest and be normalized into a synthetic stimulus format identical to Phase 0.5 signals.

## 3. Privacy & Safety Boundaries
- **Ephemeral-by-Default**: Raw sensor data (audio frames, bitmaps) SHALL NOT be stored in `memory/` or the `episodic.json` history. Only the *extracted semantic summary* (intent/context) is stored.
- **Local-Only**: No sensor data shall be transmitted to external services without an explicit, task-scoped USER_DIRECT authorization.

## 4. Failure & Noise Modes
- **Sensor Flooding**: If a sensor submits more than N signals per second, the channel is automatically set to **IGNORED** for a cooldown period.
- **Signal Hallucination**: If sensor confidence (from the driver) is below 0.4, the signal is discarded before reaching the Attention Manager.

## 5. Global Embodiment Kill-Switch
- A system-level `EMBODIMENT_ACTIVE = False` flag shall exist.
- When set to `False`, all non-terminal sensors are forced into the **IGNORED** state at the hardware driver boundary.
- Terminal commands (`USER_DIRECT`) with "KILL EMBODIMENT" signature override all current task budgets and execute the switch immediately.

## Consequences
- Protects the kernel from real-world entropy.
- Ensures the system remains "calm" even in busy environments.
- Maintains the strict logical separation between raw sensing and cognitive planning.

---

# ADR-007: Phase 1.0B Asynchronous Sensor Orchestration & Fairness Guardrails

## Status
Accepted / Locked (Phase 1.0B Initiation)

## Context
Phase 1.0A established a sequential STDIN sensor. Phase 1.0B introduces the complexity of concurrent, asynchronous sensing. To maintain kernel stability and "calm," we must define how multiple sensors share the limited "attention budget" of the cognitive kernel without starving each other or causing resource exhaustion.

## 1. Orchestration Model
- **Non-blocking Polling**: The main `PresenceLoop` SHALL remain the single point of entry for cognition.
- **Sensor Isolation**: Individual sensors (Voice, Text, System) SHALL operate in isolated, non-blocking threads or processes to prevent a slow sensor from hanging the Presence Loop.
- **Normalized Invariant**: All asynchronous sensor logic MUST produce the same normalized `Stimulus` format defined in ADR-006.

## 2. Arbitration & Quotas
To prevent a high-frequency sensor (e.g., Vision) from drowning out intentional input (e.g., Text):
- **Per-Sensor Quota**: Each sensor is allocated a maximum of N stimuli per cognitive cycle (e.g., 1 per cycle for Text, 1 per cycle for System).
- **Priority-Weighted Fairness**: The `SensorManifest` SHALL use weighted round-robin or priority queueing to ensure that a stream of LOW priority signals never completely blocks a single MEDIUM or HIGH priority signal.
- **Starvation Prevention**: If a sensor has been skipped for X cycles, its next valid stimulus is automatically promoted one priority tier (capped at HIGH).

## 3. Failure Isolation
- **Sensor Hang Recovery**: If a sensor's worker thread does not respond or produce data for T (e.g., 5 seconds), it is automatically marked as **ERROR** in the `SensorManifest` and disconnected until the next system heartbeat.
- **Buffer Backpressure**: If the global `signal_buffer` exceeds M items (e.g., 50), the system SHALL drop incoming signals based on priority (LOW first) and log a `[CONGESTION]` warning.

## 4. Ordering Guarantees
- **Causal Ordering**: Within a single sensor channel, stimuli MUST be enqueued and processed in chronological order.
- **Cross-Sensor Ordering**: Determinism is NOT guaranteed across sensors; only the priority-weighted arrivals in the `signal_buffer` dictate cognitive execution order.

## 5. Budget Interaction
- **Shared Step Budget**: All tasks triggered by sensors share the global session budget (20 steps). Asynchronous arrivals do NOT reset the budget. This forces the system to prioritize its "last remaining energy" correctly.

## Consequences
- Prevents cognitive starvation as complexity grows.
- Maintains the "sit quietly" behavior even when multiple sensors are noisy.
- Provides a scalable template for future high-noise sensors (Voice/Vision).

---

# ADR-008: Phase 1.0C Voice Integration Guardrails

## Status
Accepted / Locked (Phase 1.0C Phase Gate)

## Context
Voice is a high-entropy sensory channel that significantly increases the risk of cognitive flooding and privacy breaches. Unlike text, voice is often unintentional or background noise. ADR-008 defines the safety envelope for audio sensing to ensure it remains a disciplined, interrupt-safe channel.

## 1. Intentionality Model (Activation Options)
To prevent accidental activation and cognitive leakage, the system SHALL support three distinct activation tiers:

1. **PUSH-TO-TALK (PTT)**:
   - *Mechanism*: Mechanical or explicit binary trigger (e.g., keyboard hold, UI button).
   - *Discipline*: Highest. Captures audio ONLY while the trigger is active.
   - *Default*: The preferred mode for Phase 1.0C baseline.

2. **WAKE-WORD DETECTION (WWD)**:
   - *Mechanism*: Local, low-power model listens for a specific trigger phrase (e.g., "Atulya").
   - *Discipline*: Medium. DISCARDS all audio at the driver boundary unless confidence >= 0.8.
   - *Behavior*: Opens a fixed-duration sampling window (3-5 seconds).

3. **GATED VOICE ACTIVITY DETECTION (VAD)**:
   - *Mechanism*: Continuous sensing gated by the v0.4 Attention Manager.
   - *Discipline*: Strict. Stimulus is only enqueued if high-priority situational context exists.
   - *Restriction*: Windowed episodes only (max 10s); continuous "listening" is forbidden even in this mode.

## 2. Audio Sampling & Decay
- **Windowed Episodes**: Audio MUST be captured in discrete, task-scoped chunks (e.g., 2-10 seconds max). Unbounded streams are forbidden.
- **Transcription Decay**: If transcription results are not evaluated within T (e.g., 3 seconds) of arrival at the `signal_buffer`, the stimulus is automatically dropped to prevent "ghost responses" from stale conversation.

## 3. Privacy & Raw Data Guardrails
- **No Raw Storage**: Raw audio frames (PCM/WAV) SHALL NOT be stored on disk. Only the text transcription is allowed into the `signal_buffer` and memory layer.
- **Local Transcription**: Transcription (inference) MUST happen locally. No audio data shall be sent to external APIs (e.g., Google/OpenAI) for transcription without session-level authorization.

## 4. Transcription Failure & Noise
- **Confidence Rejection**: If the STT (Speech-to-Text) engine reports a confidence score < 0.5, the episode is discarded.
- **Noise Dampening**: Audio stimuli that do not resolve to meaningful intent (e.g., [Music], [Laughter]) are filtered at the `VoiceSensor` boundary and never enqueued.

## 5. Interaction & Budget
- **Budget Parity**: Voice-triggered tasks consume the same 20-step budget as Text tasks.
- **Preemption Rule**: Incoming HIGH priority voice (e.g., an emergency command) behaviorally follows the same preemption rules as text interrupts.

## Consequences
- Protects the system from being "always-listening" in an invasive way.
- Ensures voice input is as reliable and intentional as text.
- Maintains the kernel's "calm" by treating audio as a source of discrete, semantic events.

---

# ADR-009: Phase K1 Knowledge Brain & Local LLM Integration

## Status
Proposed (Phase K Initiation)

## Context
Atulya Tantra requires a persistent, factual knowledge base that is distinct from its cognitive kernel. Current LLMs are used as reasoning engines, but they lack stable, versioned knowledge and are prone to hallucinations. ADR-009 defines the "Knowledge Brain"—a system-level organ responsible for knowledge storage, compression, and confidence-gated retrieval.

## 1. The Organ Principle
The LLM (`Atulya-CoreLM`) is an **organ**, not the brain.
- The Kernel (Engine) remains the authority for planning and execution.
- The Knowledge Brain provides curated facts, summaries, and confidence scores.
- Model weights represent a **lossy compression** of the Knowledge Brain.

## 2. Knowledge Brain Architecture (K1)
The Knowledge Brain operates on two tracks:

### A. Topic Hierarchy & Fact Store
- **Topics**: Knowledge is partitioned into versioned topics (e.g., `Tech/Systems`, `History/Philosophy`).
- **Atomic Facts**: Data is stored as structured objects with timestamps and source lineage.
- **Time Decay**: Facts are assigned a "TTL" or a decay rate based on topic volatility.

### B. The Confidence Model
Every retrieval must return a triplet:
1. `answer`: The semantic content.
2. `confidence`: A float (0.0 to 1.0) derived from internal consistency and source reliability.
3. `status`: [VERIFIED | PROBABLE | UNKNOWN | CONTRADICTION].

## 3. Contradiction Handling
- If incoming knowledge contradicts the existing store, the system SHALL NOT automatically overwrite.
- The Kernel MUST be notified of a `COGNITIVE_FRICTION` event.
- Friction is resolved through either:
  - **Governed Web Search** (Phase K4)
  - **Manual Kernel Review**

## 4. Local LLM (Atulya-CoreLM) Contract
- **Architecture**: RWKV/Mamba-style (Linear attention, stateful).
- **Responsibility**: Summarization, factual recall, and confidence estimation.
- **Independence**: The model MUST run locally on CPU; it is for knowledge retrieval, not high-speed creative chat.

## 5. Web Search Gate (The "I Don't Know" Mode)
- Web search is triggered ONLY when confidence < 0.4.
- Results are ingested as raw knowledge objects first, filtered, and then promoted to the Knowledge Brain.

## Consequences
- The system "knows what it knows" and "knows when it is guessing."
- Knowledge is decoupled from model weights, allowing for cheap updates.
- CPU-first design ensures sustainable, always-on operation.

---

# ADR-010: Phase K2 Atulya-CoreLM Interface & Capability Contract

## Status
Proposed (Phase K2 Initiation)

## Context
Phase K1 established the Knowledge Brain as a factual repository. Phase K2 defines the interface contract for `Atulya-CoreLM`, the local model responsible for distilling that knowledge. To prevent drift and ensure system-level safety, we must define exactly what the model can see, say, and do.

## 1. Input/Query Protocol
`Atulya-CoreLM` SHALL NOT receive raw, unstructured system prompts. All queries pass through the `KnowledgeManager` gateway.
- **Input Components**:
  - `query`: The semantic request.
  - `context_facts`: A sorted list of relevant, atomic fact objects (Topic, Timestamp, Content).
  - `task_constraints`: Explicit bounds on the response format (e.g., "Summarize only", "Compare facts").
- **Focus**: The model is a **distiller**. It processes provided facts; it does not "hallucinate" external knowledge into the response.

## 2. Uncertainty & Confidence Output
The model MUST return a structured response object:
- `text`: The generated summary or answer.
- `metadata`:
  - `grounding_evidence`: IDs of the `context_facts` used.
  - `perceived_uncertainty`: Float (0.0 to 1.0) representing model's internal entropy.
  - `missing_links`: List of information gaps detected during synthesis.

## 3. Persistent State Management
Inspired by the stateful nature of RWKV/Mamba:
- **State Objects**: The model's recurrent state is persisted per-topic or per-session.
- **Handoff**: State can be cached and re-loaded to provide "long-context" continuity without the quadratic cost of Transformers.
- **Safety**: State SHALL NOT contain kernel-level intents or executor traces. It is strictly for knowledge context.

## 4. Operational Boundaries (Forbidden Actions)
`Atulya-CoreLM` is EXPLICITLY FORBIDDEN from:
- Generating `run_command` or any tool-execution syntax.
- Managing its own memory or file system.
- Altering the `SensorManifest` or `Governor` policies.
- Direct interaction with the `signal_buffer`.

## 5. Benchmarking "Knowledge Usefulness"
Usefulness is measured by:
- **Retrieval Accuracy**: Does the `text` match the `grounding_evidence`?
- **Compression Ratio**: Can it distill 10 facts into a 3-sentence summary without loss of semantic intent?
- **Conflict Accuracy**: Does it correctly identify contradictions in the `context_facts`?

## 6. Swap & Grow Safety
- **Interface Versioning**: The contract (ADR-010) is invariant.
- **Model Agnosticism**: The engine can swap 300M, 600M, or 1B+ parameter models as long as they adhere to the same IO schema.

## Consequences
- The model becomes a modular, replaceable utility.
- Hallucinations are mitigated by strict context-grounding.
- System stability is preserved by isolating model "creativity" from kernel control.

---

# ADR-011: Phase K3 CoreLM Data Curriculum & Evaluation Protocol

## Status
Proposed (Phase K3 Initiation)

## Context
Phase K1 and K2 defined the "where" and "how" of knowledge interaction. Phase K3 defines the "what"—the specific data curriculum and internal evaluation metrics that allow `Atulya-CoreLM` to grow into a disciplined knowledge organ. This ADR ensures that training is not a random ingestion of text, but a controlled compression of verified truth.

## 1. Data Curriculum Strategy
Training data is treated as a **Curriculum**, not a scrape.
- **Track 1: Foundations (Permanent)**: High-quality, slow-decay knowledge (e.g., core logic, architecture, immutable history).
- **Track 2: Domain-Specific (Delta)**: Specialized partitions (e.g., tool API specs, internal system logs, specific tech docs).
- **Track 3: Summarization Pairs**: Synthetic datasets consisting of (Atomic Facts list) -> (Compressed Summary) to reinforce the distillery function.

## 2. Chunking & Tokenization
- **Semantic Chunking**: Knowledge is not chunked by token count alone, but by "Topic Boundaries" defined in the Knowledge Brain.
- **Tokenization Persistence**: The tokenizer MUST be stable. Changing tokenizers is a breaking change for the Knowledge Brain state.

## 3. Leakage Prevention
To prevent "hallucinated spills" from noisy sources:
- **Source Labeling**: Every token window in the curriculum is tagged with a `SOURCE_RELIABILITY` score.
- **Differential Weighting**: High-reliability sources (Internal Docs) exert more "gradient pressure" than lower-reliability sources (External News).

## 4. Parameter Growth Path (Scalability)
- **Modular Expansion**: We start with 300M parameters.
- **Transition Gate**: Growth to 600M or 1.2B is authorized only when the smaller model saturates its evaluation metrics (i.e., further training on the same curriculum yields < 1% improvement).

## 5. Evaluation Protocol (Internal Benchmarking)
We do NOT use external benchmarks (e.g., MMLU). We use **System-Level Delta Metrics**:
- **Semantic Loss**: Measure the model's ability to reconstruct Atomic Facts from its weights.
- **Confidence Calibration**: Does the model's uncertainty triplet (ADR-010) correlate with actual errors? (Self-Awareness score).
- **Distillation Fidelity**: A BLEU/ROUGE comparison of model summaries vs. Ground-Truth summaries in the Knowledge Brain.
- **Cognitive Friction Score**: How well does the model detect contradictions injected into its context?

## 6. Training Safety
- **Offline Only**: Training occurs on isolated hardware (CPU/GPU) without direct bridge to the active Kernel.
- **Binary Deploy**: Only the final resulting weights (compressed knowledge) are transferred to the active Atulya-CoreLM directory after passing ALL evaluation gates.

## Consequences
- Training becomes predictable and verifiable.
- The model's "IQ" is measured by its utility to Atulya Tantra, not by general trivia.
- Avoids the "bloat" of unnecessary parameters.

---

# ADR-012: Phase 1.0D Vision Integration Guardrails

## Status
Proposed (Phase 1.0D Initiation)

## Context
Vision is the highest-bandwidth sensory channel in Atulya Tantra. To prevent cognitive flooding and privacy breaches (leakage of the user's environment), strict guardrails are required. ADR-012 defines the "Discrete Vision" principle.

## 1. Discrete Vision Principle
- **No Continuous Streaming**: The system SHALL NOT maintain a permanent video feed.
- **On-Demand Sampling**: Vision is a "Pull" sensor. The kernel or user must explicitly trigger a capture event (e.g., "Look at this").
- **Thumbnail Economy**: Raw high-res data is processed locally into a low-res semantic description (text) immediately.

## 2. Privacy & Persistence
- **Local-Only Processing**: Images must be processed on the local machine (CPU/GPU).
- **Zero Persistence**: Raw image files SHALL NOT be stored in `memory/` or `logs/`. They are ephemeral and exist only in RAM during the capture cycle.
- **Opt-In Session**: Vision is disabled by default and must be authorized per session.

## 3. Sampling Limits
- **Episode Duration**: A single vision episode (capture + description) is treated as a single discrete stimulus.
- **Frequency Cap**: Max 1 capture per 5 seconds to prevent budget starvation.

## 4. Normalization
- The `VisionSensor` MUST output a text-based stimulus (e.g., "Visible: [Description]") to maintain parity with the engine's interactive core.

## Consequences
- The system remains calm and privacy-safe.
- Vision data is converted into a low-bandwidth, symbolic format for the core brain.

---

# ADR-013: Phase K4 Governed Search Gate

## Status
Proposed (Phase K4 Initiation)

## Context
Atulya Tantra requires the ability to update its internal knowledge when confidence is low. ADR-013 defines the "Governed Search Gate"—a system-level lock on web access.

## 1. Trigger Discipline
- **Confidence-Gated**: Search is triggered ONLY when `CoreLMInterface` reports confidence < 0.4 and the `KnowledgeBrain` confirms the topic is `UNKNOWN`.
- **Kernel Authorization**: The Engine MUST explicitly authorize a search event after weighing the task risk.

## 2. Access Constraints
- **Read-Only**: Web access is strictly for information retrieval. No account logins, no form submissions, no state-altering actions.
- **Source Filtering**: Preference is given to high-authority domains (docs, official repositories).

## 3. Ingestion Protocol
- **Raw Fact Filter**: Search results do NOT enter the Knowledge Brain directly.
- **Stage 1 (Ephemeral)**: Results are stored in a temporary buffer.
- **Stage 2 (Filtering)**: The `KnowledgeManager` deduplicates and filters for contradictions.
- **Stage 3 (Promotion)**: Verified facts are promoted to the Topic Store (Phase K1/K3).

## 4. Rate-Limiting & Budget
- Search counts as a high-cost action (Priority 10).
- Max 3 search queries per high-level task to prevent "research rabbit-holes".

## Consequences
- The system prevents news poisoning and auto-belief loops.
- Web access is a surgical tool, not a default behavior.

---

# Architectural Decision Records (ADR) Index

This directory contains the formal record of all structural and cognitive design commitments for Atulya Tantra.

| ID | Title | Status | Scope |
| :--- | :--- | :--- | :--- |
| **ADR-003** | [v0.3 Resource Awareness](ADR-003-v0.3.md) | Locked | Engine |
| **ADR-004** | [v0.4 Attention Manager](ADR-004-v0.4.md) | Locked | Engine |
| **ADR-005** | [v0.5 Presence Simulation](ADR-005-v0.5.md) | Locked | Embodiment |
| **ADR-005A**| [Sensor Manifest & State](ADR-005A-sensor-manifest.md) | Locked | Embodiment |
| **ADR-006** | [Real-World Sensor Integration](ADR-006-sensor-guardrails.md) | Locked | Embodiment |
| **ADR-007** | [Async Orchestration & Fairness](ADR-007-asynchronous-orchestration.md) | Locked | Embodiment |
| **ADR-008** | [Voice Integration Guardrails](ADR-008-voice-guardrails.md) | Locked | Embodiment |
| **ADR-009** | [Knowledge Brain Guardrails](ADR-009-knowledge-brain-guardrails.md) | Locked | Knowledge |
| **ADR-010** | [Local LLM Contract (CoreLM)](ADR-010-local-llm-contract.md) | Locked | Knowledge |
| **ADR-011** | [Data Curriculum & Eval Protocol](ADR-011-data-curriculum-eval.md) | Locked | Knowledge |
| **ADR-012** | [Vision Integration Guardrails](ADR-012-vision-guardrails.md) | Locked | Embodiment |
| **ADR-013** | [Governed Search Gate](ADR-013-search-gate.md) | Locked | Knowledge |

---
*Archival Record Policy: Decisions once locked may not be modified. New decisions require a sequential ADR.*

---

