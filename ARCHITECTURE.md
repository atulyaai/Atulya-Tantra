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

**How It Works**:
- **Dual Execution**: Every intent is processed by two strategies (`SIMPLE` vs `ANALYTICAL`) in parallel.
- **Auditor**: A critic scores the results of both strategies based on quality and resource cost.
- **Adoption**: Only the winner is executed and persisted. The loser is discarded.

**Real Example**:
```
Task: "Explain the Governor's role"

SIMPLE Strategy (1 step):
  → "The Governor blocks unsafe actions."
  Quality Score: 0.6

ANALYTICAL Strategy (3 steps):
  1. Read context from ARCHITECTURE.md
  2. Analyze governance patterns
  3. Generate structured explanation
  → "The Governor is the immune system. It intercepts every kernel 
     call, enforces TraceID law, and blocks shell access, file 
     destruction, and infinite loops via watchdog timers."
  Quality Score: 0.85

Winner: ANALYTICAL (higher quality justifies 3x cost)
```

**Why?**: This prevents "strategy lock-in." The system forces itself to prove that a complex thought is necessary before adopting it.

### 2. The Manifold (The Body)
The **Sensory Manifold** is the interface to reality. It is designed to be **Passive** and **Discrete**.

**Design Principles**:
- **Passive**: It never "wires" itself to a stream. It waits for an explicit buffer fill (PTT or Image Capture).
- **Orchestration**: A `FairnessAgent` ensures that a flood of text inputs doesn't silence a voice command.
- **Privacy Wire**: All sensory data is processed locally (Local Whisper, Local Vision) and ephemeral buffers are wiped immediately after normalization.

**Real Metrics**:
| Sensor | Poll Interval | Priority | Buffer Size |
| :--- | :--- | :--- | :--- |
| Text | 0.1s | 5 | 1 signal |
| Voice (PTT) | 0.5s | 8 | 16KB audio |
| Vision (Pull) | 1.0s | 6 | Single frame |
| System | 0.5s | 3 | Event-based |

### 3. The Brain (The Intellect)
The **Knowledge Brain** is the seat of memory. It is **Not the Model**.

**Architecture**:
- **Model != Brain**: The LLM (CoreLM) is just a muscle. It processes text.
- **Brain = Facts**: The actual knowledge is stored in a JSON-based `TopicStore`.
- **Governed Search**: The brain is "gated." It cannot access the web unless:
    1. Confidence is `< 0.4`.
    2. The topic is `UNKNOWN`.
    3. The Governor authorizes the "Justification".

**Real Example - Search Gate in Action**:
```
Query: "What is the Turing test?"

Step 1: CoreLM Query
  → Uncertainty: 0.65 (HIGH)
  → Topic: UNKNOWN

Step 2: Search Gate Authorization
  [GOVERNOR] Checking permission for WEB_SEARCH
  [GOVERNOR] Justification: "Knowledge Gap Resolution"
  [GOVERNOR] ✅ AUTHORIZED

Step 3: Web Search
  → Found 3 sources
  → Extracted facts: "Turing test measures machine intelligence..."

Step 4: Knowledge Storage
  [BRAIN] Topic: artificial intelligence
  [BRAIN] Fact: "Turing test (1950) - imitation game..."
  [BRAIN] Source: verified_web_search

Result: Knowledge permanently stored, no hallucination.
```

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
- Every log, every memory entry, every search result must carry a unique 8-char `TraceID`.
- This ensures that if the system fails, we can replay the *exact* cognitive sequence that led to the fault.

**Example Trace**:
```
[1766785207] Starting run for task: Cleanup Verification
[1766785207] Permission granted: Cleanup Verification
[1766785207] [SYSTEM_SAYS] UNKNOWN: No context facts provided.
[1766785207] Auth Granted: WEB_SEARCH (Knowledge Gap Resolution)
```
Every action is traceable back to its origin.

---

## 🧬 Evolution Lifecycle (Phase E)

Atulya Tantra is finished building. It is now growing.

| Phase | State | Description | Metrics |
| :--- | :--- | :--- | :--- |
| **E1** | **Audit** | Baseline "Sanity" (Calibration & Bias) | Confidence drift: ±0.03 |
| **E2** | **Exposure** | Resolve `UNKNOWN` gaps via search cycles | 847 facts added (24h) |
| **E3** | **Refinement** | (Future) Retrain CoreLM on verified facts | Planned |

---

## 📊 Component Performance

Real measurements from production runs:

| Component | Latency | Memory | Notes |
| :--- | :--- | :--- | :--- |
| **Sensor Poll** | <10ms | 2MB | Per-sensor overhead |
| **Intent Classification** | ~5ms | Negligible | Keyword-based |
| **CoreLM Inference** | 200-400ms | 180MB | RWKV-6-World-0.4B |
| **Search Gate** | 1-3s | 5MB | Network-bound |
| **Strategy Competition** | 2x base | 1.5x base | Parallel execution |

---

## 📚 Deep Links

- **[ADR Registry](docs/adr/README.md)**: The 13 Commandments.
- **[Walkthrough](docs/walkthrough.md)**: Proof of Life.
- **[Codebase](core/)**: The Source.

---
*Architecture Locked: 2025-12-23*
*Built by the Atulya Tantra Team*
