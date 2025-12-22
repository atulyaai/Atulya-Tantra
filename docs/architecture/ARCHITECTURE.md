# Atulya Tantra: The System Architecture (v1.0)

> "A system without a constitution is just a script waiting to break."

This document defines the **Technical Truth** of Atulya Tantra. It describes the laws, the organs, and the connections that make up the "Constrained Knowledge Organ."

---

## 🏗️ System Schematics

The system is not a stack; it is a **Loop**.

```ascii
      [ REALITY ] 
           ↓
    ( Sensory Manifold ) 
      [ TEXT | VOICE | VISION ]
           ↓
    +-----------------------+
    |  Sensor Orchestrator  |  (Thread-Safe Buffer)
    +-----------+-----------+
                ↓
          [ Normalized Stimulus ]
                ↓
    +-----------v-----------+         +------------------+
    |   COMPETITIVE KERNEL   | <-----> |  Knowledge Brain |
    |  (Engine + Governor)   |         | (Facts + CoreLM) |
    +-----------+-----------+         +------------------+
                ↓
           [ ACTION ]
                ↓
      ( Artifacts & Outcomes )
```

---

## 🏛️ The Three Organs

### 1. The Kernel (The Will)
The **Competitive Kernel** is the decision-making engine. It does not "think" in a stream of consciousness; it **competes**.
- **Dual Execution**: Every intent is processed by two strategies (`SIMPLE` vs `ANALYTICAL`) in parallel.
- **Auditor**: A critic scores the results of both strategies based on quality and resource cost.
- **Adoption**: Only the winner is executed and persisted. The loser is discarded.
- **Why?**: This prevents "strategy lock-in." The system forces itself to prove that a complex thought is necessary before adopting it.

### 2. The Manifold (The Body)
The **Sensory Manifold** is the interface to reality. It is designed to be **Passive** and **Discrete**.
- **Passive**: It never "wires" itself to a stream. It waits for an explicit buffer fill (PTT or Image Capture).
- **Orchestration**: A `FairnessAgent` ensures that a flood of text inputs doesn't silence a voice command.
- **Privacy Wire**: All sensory data is processed locally (Local Whisper, Local Vision) and ephemeral buffers are wiped immediately after normalization.

### 3. The Brain (The Intellect)
The **Knowledge Brain** is the seat of memory. It is **Not the Model**.
- **Model != Brain**: The LLM (CoreLM) is just a muscle. It processes text.
- **Brain = Facts**: The actual knowledge is stored in a JSON-based `TopicStore`.
- **Governed Search**: The brain is "gated." It cannot access the web unless:
    1. Confidence is `< 0.4`.
    2. The topic is `UNKNOWN`.
    3. The Governor authorizes the "Justification".

---

## 📜 The Governance Layer

The **Governor** is the immune system. It intercepts every call the Kernel makes.

### The "No" List
The Governor has absolute authority to block:
- **Shell Access**: `os.system`, `subprocess` (unless strictly whitelisted).
- **File Destruction**: `rm`, `del` outside of temp.
- **Infinite Loops**: The `PresenceLoop` has a hard `watchdog` timer.

### The TraceID Law
**Law**: *"No atom moves without a TraceID."*
- Every log, every memory entry, every search result must rely on a unique 8-char `TraceID`.
- This ensures that if the system fails, we can replay the *exact* cognitive sequence that led to the fault.

---

## 🧬 Evolution Lifecycle (Phase E)

Atulya Tantra is finished building. It is now growing.

| Phase | State | Description |
| :--- | :--- | :--- |
| **E1** | **Audit** | The system establishes a baseline of "Sanity" (Calibration & Bias). |
| **E2** | **Exposure** | The system resolves `UNKNOWN` gaps via governed search cycles. |
| **E3** | **Refinement** | (Future) The CoreLM is retrained on the *verified* Knowledge Brain facts. |

---

## 📚 Deep Links

- **[ADR Registry](../adr/README.md)**: The 13 Commandments.
- **[Walkthrough](../archival/walkthrough.md)**: Proof of Life.
- **[Codebase](../core/)**: The Source.

---
*Architecture Locked: 2025-12-23*
