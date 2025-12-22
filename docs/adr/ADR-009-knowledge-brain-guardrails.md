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
