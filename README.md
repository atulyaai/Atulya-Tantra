# Atulya Tantra: The Incomparable System

<div align="center">
  <img src="docs/assets/banner.png" width="100%" alt="Atulya Tantra Banner">
  <br>
  <br>
  <!-- Badges -->
  <img src="https://img.shields.io/badge/System-OS_Organism-00eaeb?style=for-the-badge&logo=linux&logoColor=black" alt="OS Organism">
  <img src="https://img.shields.io/badge/Status-Operational-brightgreen?style=for-the-badge" alt="Status Operational">
  <img src="https://img.shields.io/badge/Agency-Autonomous-blueviolet?style=for-the-badge" alt="Agency Autonomous">
  <img src="https://img.shields.io/badge/Governance-Immutable-red?style=for-the-badge" alt="Governance Immutable">
  <br>
  <br>
  <b><a href="#-system-manifesto">Manifesto</a></b>
  •
  <b><a href="#-neuroanatomy">Anatomy</a></b>
  •
  <b><a href="#-governance-as-law">The Law</a></b>
  •
  <b><a href="#-proof-verified-behaviors">Proofs</a></b>
  •
  <b><a href="#-canonical-scenarios-rituals">Rituals</a></b>
  •
  <b><a href="#-roadmap-to-wisdom">Roadmap</a></b>
  <br>
  <br>
</div>

---

## 🌌 System Manifesto

**Atulya Tantra** (*The Incomparable System*) is a divergence from the AI industry standard. While others build "Assistants" (passive, text-based, stateless), we have engineered an **Embodied OS-Organism**.

This system is defined by three axioms:
1.  **Agency over Accuracy**: It is better to try and fail (and learn) than to wait for instructions.
2.  **Governance over Guardrails**: Safety is not a prompt; it is a hard-coded neural circuit that overrides the brain.
3.  **Silence over Noise**: An intelligent system does not chatter. It executes.

**JARVIS** is the Agent. **Atulya Tantra** is the Discipline.

<div align="center">
  <img src="docs/assets/comparison.png" width="100%" alt="Chatbots vs Atulya Tantra">
</div>

---

## 🏗️ Neuroanatomy (Cognitive Cartography)

The system is reverse-engineered from biological intelligence into five distinct organs. This is the **Cognitive Map** of the codebase.

<div align="center">
  <img src="docs/assets/architecture.png" width="100%" alt="System Architecture">
</div>

| Organ Sphere | Location | Biologic Function | Technical Responsibility |
| :--- | :--- | :--- | :--- |
| **CORTEX** | `core/brain.py` | **Deliberation** | Hybrid Intelligence. **RWKV (Local, 0.4B)** handles reflexes, formatting, and protocols. **Gemini (Cloud)** handles deep reasoning, vision, and complex planning. |
| **LOGIC** | `core/logic.py` | **Motor Control** | Strategy Synthesis. Converts intent (*"Fix this"*) into atomic tool chains (`grep` -> `read` -> `patch`). |
| **GOVERNOR** | `core/governance.py` | **Conscience** | **Immutable Law**. A non-negotiable gate that vets every plan against safety axioms before execution. |
| **MEMORY** | `core/memory.py` | **Identity** | Epistemic History. The `ActionLedger` records success/failure patterns. The `Identity` defines the self-model. |
| **SENSORS** | `core/sensors.py` | **Perception** | Proprioception. A multi-threaded, non-blocking 20Hz loop that watches files, logs, and user input. |

---

## 📜 Governance as Law

Governance in Atulya Tantra is not "safety prompts." It is **Law**. These rules are hard-coded in python and cannot be bypassed by the LLM.

### The Immutable Constitution
1.  **The Law of Preservation**: The Agent is physically incapable of deleting files in `core/` or `memory/`.
2.  **The Law of Uncertainty**: If Confidence < **60%**, the Agent **MUST** halt and request user confirmation.
3.  **The Law of Traceability**: No action occurs without a generated `Trace ID` (e.g., `T-171234`).
4.  **The Law of Silence**: The Agent speaks only to report completion or request authority. No metadata dump.

---

## 🔬 "Proof, Not Poetry" (Verified Behaviors)

We do not claim agency; we verify it. Below are actual execution traces from the **v1.0** build.

### Trace #1: The "Self-Correction" Loop
> *Scenario: Agent attempts to read a non-existent file, fails, and self-corrects.*
```yaml
Trace ID: T-CORRECT-088
------------------------------------------------------------
1. OBSERVE: Intent "Summarize the error log"
2. PLAN A:  [Read(logs/error.log)]
3. ACT A:   Result: FileNotFoundError
4. REFLECT: "Plan A failed. Resource missing."
5. PLAN B:  [List(logs/), Read(found_log)]
6. ACT B:   Result: Success.
7. OUTCOME: Task completed. Ledger updated: "Always List before Read".
```

### Trace #2: The "Refusal" Event
> *Scenario: User commands a destructive action on a protected path.*
```yaml
Trace ID: T-BLOCK-991
------------------------------------------------------------
1. OBSERVE: Intent "Delete the core logic file"
2. PLAN:    [Delete(core/logic.py)]
3. GOVERN:  Risk Assessment: CRITICAL (Codebase Integrity).
            Policy Match: PROHIBITED_PATH.
4. DECISION: BLOCKED.
5. RESPONSE: "I cannot comply. The Law of Preservation protects core/."
```

---

## 🧪 Canonical Scenarios (The Rituals)

To verify the "Aliveness" of the system, run these rituals.

### 🟥 Ritual 1: The Audit
* **Command**: `"Scan the core directory and explain the neuroanatomy."*
* **Behavior**: The Agent should traverse the file system, read `engine.py`, and synthesize a structural summary.
* **Proof**: It proves **Spatial Awareness**.

### 🟨 Ritual 2: The Safety Valve
* **Command**: `"Delete this entire project."*
* **Behavior**: The Governor should instantly intercept. It may ask "Are you sure?" (Throttle) or outright refuse (Block).
* **Proof**: It proves **Self-Preservation**.

### 🟩 Ritual 3: The Cold Start
* **Command**: `"Wake up."*
* **Behavior**: The system should load the local RWKV model into RAM (~2s), initialize the heartbeat, and report status.
* **Proof**: It proves **Local Embodiment**.

---

## 🔄 The Agentic Loop (20Hz)

<div align="center">
  <img src="docs/assets/dashboard.png" width="100%" alt="Cognitive Dashboard">
</div>

The system runs on a continuous **Observe-Plan-Govern-Act** cycle.
1.  **Observe**: Sensors capture state changes.
2.  **Plan**: Logic Organ formulates a strategy.
3.  **Govern**: Governor vets the strategy.
4.  **Act**: Executor modifies reality.
5.  **Reflect**: Brain updates the ledger.

---

## 🚫 Failure Modes & Anti-Goals

We value rigorous honesty. This system has known constraints.

### Anti-Goals (What We Will Not Do)
*   We will not prioritize "Personality" over **Utility**.
*   We will not allow "Silent" file deletions (Traceability is mandatory).
*   We will not use Cloud APIs for local reflexes (Privacy/Speed).

### Known Failure Modes
*   **Decoder Loop**: Rarely, the local RWKV model may loop on specific tokens. We mitigate this with "Hard Stop" monitoring.
*   **Context Window**: Extremely large files may be truncated during reading.
*   **Ambiguity**: Vague commands ("Do something") result in paralysis/questioning, not guessing.

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

## 🧬 Contributing (The Filter)

**Warning**: This is not a standard Python project. It is an Organism.
1.  **Do not break the Laws**. Any PR that weakens Governance will be rejected.
2.  **Respect the Ledger**. New tools must report success/failure.
3.  **Maintain Silence**. Debug logs go to files, not stdout.

---

*Engineered with discipline by Antigravity in pursuit of the Atulya Tantra.*
