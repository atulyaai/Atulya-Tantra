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
