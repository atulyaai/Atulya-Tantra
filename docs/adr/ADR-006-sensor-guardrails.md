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
