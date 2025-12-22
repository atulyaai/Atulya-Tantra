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
