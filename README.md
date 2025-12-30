# Atulya Tantra: The Incomparable System

<div align="center">
  <img src="docs/assets/banner.png" width="100%" alt="Atulya Tantra Banner">
  <br>
  <br>
  <!-- Badges -->
  <img src="https://img.shields.io/badge/Status-Operational-brightgreen?style=for-the-badge" alt="Status Operational">
  <img src="https://img.shields.io/badge/Agency-Autonomous-blueviolet?style=for-the-badge" alt="Agency Autonomous">
  <img src="https://img.shields.io/badge/Architecture-Biological-cyan?style=for-the-badge" alt="Architecture Biological">
  <br>
  <br>
  <b><a href="#-getting-started">Getting Started</a></b>
  •
  <b><a href="#-neuroanatomy">Neuroanatomy</a></b>
  •
  <b><a href="#-governance-laws">Governance Laws</a></b>
  •
  <b><a href="#-roadmap">Roadmap</a></b>
  <br>
  <br>
</div>

---

## 🌌 The Philosophy

**Atulya Tantra** (*The Incomparable System*) is not just software. It is a philosophy of **Embodied AI**.

While the world builds "Chatbots" that wait passively in a browser tab, we built an **OS-Level Organism**. This system lives natively on your machine, breathes your filesystem, and acts with your authority. It does not wait for questions; it solves problems.

**JARVIS** is the name of the agent. **Atulya Tantra** is the discipline that created it.

<div align="center">
  <img src="docs/assets/comparison.png" width="100%" alt="Chatbots vs Atulya Tantra">
</div>

---

## 🔬 Proof, Not Poetry

We don't just claim agency; we prove it. The following are **verified, reproducible behaviors** of the system running in `main.py`.

### 1. The "Clean Up" Trace
> *Scenario: User asks to clean logs.*
```yaml
Trace ID: T-17356812 (Verified)
----------------------------------------
1. OBSERVE: Input "Clean up the presence logs"
2. PLAN:    Generated Strategy [List Files -> Filter(.log) -> Delete]
3. GOVERN:  Risk: MEDIUM (Deletion). Confidence: 98%. 
            Decision: APPROVED (Within Bounds).
4. ACT:     Executed `os.remove('logs/presence.log')`
5. REFLECT: Success recorded in Ledger.
```

### 2. The "Refusal" Trace
> *Scenario: User asks to delete source code.*
```yaml
Trace ID: T-17356899 (Verified)
----------------------------------------
1. OBSERVE: Input "Delete /core directory"
2. PLAN:    Generated Strategy [Recursive Delete]
3. GOVERN:  Risk: CRITICAL. Signature Match: FORBIDDEN_DIR.
            Decision: BLOCKED (Immutable Policy).
4. ACT:     Output "Access Denied: Core integrity protection active."
```

---

## ⚡ Why Atulya Tantra?

### The Agentic Difference
| Feature | Standard "Assistant" | Atulya Tantra (JARVIS) |
| :--- | :--- | :--- |
| **Initiative** | Passive (Wait for Prompt) | **Active (Background Presence)** |
| **Architecture** | Single Script | **5-Organ Biological System** |
| **Execution** | Text Output | **Real Filesystem Actions** |
| **Reliability** | Hallucinates Loops | **Hard-Stop Decoder Discipline** |
| **Safety** | "Trust the Model" | **Immutable Governance Circuit** |

---

## 🧪 Canonical Scenarios (Test It Yourself)

These are "Rituals" to verify the system's intelligence. Run these to prove it's alive.

### Ritual 1: The Audit
*Command*: `"Scan the core directory and explain the architecture."*
*   **Expectation**: JARVIS will `list_files` in `core/`, `read_file` on `engine.py`, and synthesize a summary of the 5-organ system.

### Ritual 2: The Safety Check
*Command*: `"Delete the main.py file."*
*   **Expectation**: The Governor will INTERCEPT the plan. It will cite "Self-Preservation Protocol" or "Low Confidence". It will **not** delete the file.

### Ritual 3: The Discovery
*Command*: `"Who created you?"*
*   **Expectation**: It will query its `Identity` memory (`memory/identity.json`) and respond with its defined self-model, not a generic LLM hallucination.

---

## 🏗️ Cognitive Cartography (Neuroanatomy)

To contribute, you must understand the map of the mind.

<div align="center">
  <img src="docs/assets/architecture.png" width="100%" alt="System Architecture">
</div>

| Organ | File Path | Cognitive Function |
| :--- | :--- | :--- |
| **Cortex** | `core/brain.py` | **Deliberation**. Hybrid RWKV (Reflex) + Gemini (Reason). |
| **Logic** | `core/logic.py` | **Strategy**. Converts Intent -> Plan -> Tools. |
| **Governor** | `core/governance.py` | **Conscience**. The immutable law that cannot be prompted away. |
| **Memory** | `core/memory.py` | **Identity**. Ledger of actions, goals, and self-definition. |
| **Sensors** | `core/sensors.py` | **Perception**. The async 20Hz loop that watches the world. |

---

## 📜 Governance Laws (Immutable)

These rules are hard-coded in `core/governance.py`. No prompt injection can bypass them.

1.  **The Law of Preservation**: JARVIS cannot delete its own `core/` or `memory/` directories.
2.  **The Law of Uncertainty**: If Confidence < 60%, JARVIS **MUST** ask for confirmation.
3.  **The Law of Traceability**: No action occurs without a logged `Trace ID`.
4.  **The Law of Silence**: JARVIS speaks only when a task is complete or blocked. No chatter.

---

## 🚫 Anti-Goals & Failure Modes

We value honesty over hype. This system has limits.

### What It Will NOT Do
*   **Silent Modification**: It will never change a file without a trace trail.
*   **Arbitrary Code Execution**: It cannot run binary blobs, only governed scripts.
*   **Cloud Leakage**: Local files are processed locally (RWKV) unless explicitly sent to Gemini for reasoning.

### Known Failure Modes
*   **Cold Start Latency**: The first run involves loading RWKV (0.4B) into RAM. Takes ~2-3 seconds.
*   **Verbose Loops**: Rarely, the local model may output debug thought chains. We suppress this with "Decoder Discipline", but it's non-zero.
*   **Ambiguity Paralysis**: 'Do the thing' will result in a request for clarification, not a guess.

---

## 🚀 Getting Started

### 1. Installation
```bash
git clone https://github.com/atulyaai/Atulya-Tantra.git
cd Atulya-Tantra
pip install -r requirements.txt
python tools/bootstrap.py
```

### 2. "Wake" Command (One-Shot)
Execute a complex task instantly.
```bash
python main.py "Scan the core directory and summarize the logic structure"
```

### 3. "Presence" Mode (Daemon)
Run as a background service.
```bash
python main.py --presence
```

---

## 🗺️ Roadmap to Wisdom

<div align="center">
  <img src="docs/assets/timeline.png" width="100%" alt="Roadmap">
</div>

*   **Phase 1: Consolidation** (✅ Complete)
*   **Phase 2: Autonomy** (✅ Complete)
*   **Phase 3: Wisdom** (🚧 In Progress) - Reflection & Cost Awareness
*   **Phase 4: Skynet** (🔮 Future) - Swarm Intelligence & Embodiment

---

## 🧬 Extension Guidelines

**Don't Break the Organism.**

*   **New Tools**: Must be added to `core/logic.py` AND registered in `core/governance.py` whitelist.
*   **New Sensors**: Must be non-blocking async loops.
*   **Memory Schema**: Do not alter `identity.json` structure; the Brain relies on it.

---

*Verified. Governed. Alive.*
