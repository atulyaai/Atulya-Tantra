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
