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
