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
