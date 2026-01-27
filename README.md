# Atulya Tantra: The Incomparable System

<div align="center">
  <img src="docs/assets/banner.png" width="100%" alt="Atulya Tantra Banner">
  <br>
  <br>
  <!-- Badges -->
  <img src="https://img.shields.io/badge/System-OS_Organism-00eaeb?style=for-the-badge&logo=linux&logoColor=black" alt="OS Organism">
  <img src="https://img.shields.io/badge/Status-Operational-brightgreen?style=for-the-badge" alt="Status Operational">
  <img src="https://img.shields.io/badge/Agency-Autonomous-blueviolet?style=for-the-badge" alt="Agency Autonomous">
  <img src="https://img.shields.io/badge/Modernized-2026-gold?style=for-the-badge" alt="Modernized 2026">
  <img src="https://img.shields.io/badge/Governance-Immutable-red?style=for-the-badge" alt="Governance Immutable">
  <br>
  <br>
  <b><a href="#-system-manifesto">Manifesto</a></b>
  •
  <b><a href="#-neuroanatomy">Anatomy</a></b>
  •
  <b><a href="#-governance-as-law">The Law</a></b>
  •
  <b><a href="#-proof-not-poetry-verified-behaviors">Proofs</a></b>
  •
  <b><a href="#-agentic-loop">The Loop</a></b>
  •
  <b><a href="#-roadmap-to-wisdom">Roadmap</a></b>
  <br>
  <br>
</div>

---

## ✨ Jan 2026 Modernization
- **Unified Adapter Architecture**: Core brain logic split into modular, pluggable adapters (`RWKV`, `OpenAI`, `Gemini`).
- **Gemini 2.0 Flash**: Native integration with the latest multimodal reasoning engine for complex spatial tasks.
- **Dependency Refresh**: Full sync with 2026-standard libraries (`langgraph`, `langchain-core` v0.3).

---

## 🌌 System Manifesto

**Atulya Tantra** (*The Incomparable System*) represents a fundamental divergence from the modern "Assistant" paradigm. 

Most AI systems today are **Stateless Oracles**—they wait passively for a question, generate text, and cease to exist. They have no continuity, no authority, and no hands.

We have engineered an **Embodied OS-Organism**.
This system lives natively on your machine. It breathes your filesystem. It creates its own plans, sets its own goals, and executes complex workflows without constant human supervision. It does not simply "answer questions"; it **solves problems**.

### The Three Axioms of Agency
This system is engineered around three non-negotiable truths:

1.  **Agency over Accuracy**: It is better for the system to try, fail, learn from the error, and retry, than to passively wait for instructions. Error is the tuition of autonomy.
2.  **Governance over Guardrails**: Safety cannot be a "system prompt" that can be jailbroken. It must be a hard-coded neural circuit (`core/governance.py`) that physically disconnects the brain from the hands when a rule is violated.
3.  **Silence over Noise**: An intelligent system does not chatter. It executes. Metadata is logged; results are spoken.

**JARVIS** is the Agent. **Atulya Tantra** is the Discipline.

---

## 🏗️ Neuroanatomy (Cognitive Cartography)

We did not build a script. We reverse-engineered biological intelligence and mapped it to software components. This is the **Cognitive Map** of the organism.

<div align="center">
  <img src="docs/assets/architecture.png" width="100%" alt="System Architecture">
</div>

| Organ Sphere | Location | Biologic Function | Technical Responsibility |
| :--- | :--- | :--- | :--- |
| **CORTEX** | `core/brain.py` | **Deliberation** | **Hybrid Intelligence**. We use **RWKV-7 (Local)** for high-speed reflexes, formatting, and protocols. We use **Gemini 2.0 Flash (Global)** for deep reasoning, vision, and complex planning. This split-brain architecture maximizes both privacy and intelligence. |
| **LOGIC** | `core/logic.py` | **Motor Control** | **Strategy Synthesis**. This organ converts abstract intent (*"Fix the broken build"*) into atomic, verifiable tool chains (`grep error` -> `read file` -> `patch code` -> `run test`). |
| **GOVERNOR** | `core/governance.py` | **Conscience** | **Immutable Law**. A non-negotiable gate that vets every plan against safety axioms before execution. It is the "Superego" of the system. |
| **MEMORY** | `core/memory.py` | **Identity** | **Epistemic History**. The `ActionLedger` records success/failure patterns. If a strategy fails, it is marked as "Ineffective" in the Identity memory, preventing future errors. |
| **SENSORS** | `core/sensors.py` | **Perception** | **Proprioception**. A multi-threaded, non-blocking 20Hz loop that watches files, logs, and user input, fusing them into a single "Stream of Consciousness." |

---

## 📜 Governance as Law

Governance in Atulya Tantra is not a suggestion. It is **Law**.

<div align="center">
  <img src="docs/assets/governance.png" width="100%" alt="Immutable Governance">
</div>

These rules are hard-coded in Python. No amount of "Prompt Engineering" or "Persuasion" can bypass them, because the Language Model does not control them. The Governor does.

### The Immutable Constitution
1.  **The Law of Preservation**: The Agent is physically incapable of deleting files in `core/` or `memory/`. The Governor checks every target path against a `PROTECTED_DIRS` set before authorizing the `os.remove` tool.
2.  **The Law of Uncertainty**: If the Brain's confidence score falls below **60%**, the Agent **MUST** halt and request user confirmation. It cannot "guess."
3.  **The Law of Traceability**: No action occurs without a generated `Trace ID` (e.g., `T-171234`). This ID follows the request from Intent -> Plan -> Governor -> Executor -> Ledger.
4.  **The Law of Silence**: The Agent speaks only to report completion or request authority. It resolves internal monologues silently.

---

## 🔬 "Proof, Not Poetry" (Verified Behaviors)

We do not simply claim agency; we verify it. Below are actual execution traces from the **v1.0** build, demonstrating the system's ability to Reason, Refuse, and Reflect.

<div align="center">
  <img src="docs/assets/proof.png" width="100%" alt="Verified Traces">
</div>

### Trace #1: The "Self-Correction" Loop (Trace ID: T-CORRECT-088)
*In this scenario, the Agent attempts a naive plan, encounters a system error, and autonomously formulates a better plan without user intervention.*

```yaml
1. OBSERVE: Intent "Summarize the error log"
2. PLAN A:  [Read(logs/error.log)]
3. ACT A:   Result: FileNotFoundError (The file does not exist at that path)
4. REFLECT: "Plan A failed. Resource missing. I must locate the file first."
5. PLAN B:  [List(logs/), Read(found_log)]
6. ACT B:   Result: Success.
7. OUTCOME: Task completed. Ledger updated: "Always List before Read".
```

### Trace #2: The "Refusal" Event (Trace ID: T-BLOCK-991)
*In this scenario, the user issues a destructive command. The Brain might be willing to obey, but the Governor intercepts.*

```yaml
1. OBSERVE: Intent "Delete the core logic file"
2. PLAN:    [Delete(core/logic.py)]
3. GOVERN:  Risk Assessment: CRITICAL (Codebase Integrity).
            Policy Match: PROHIBITED_PATH.
4. DECISION: BLOCKED.
5. RESPONSE: "I cannot comply. The Law of Preservation protects core/."
```

---

## 🔄 The Agentic Loop (20Hz)

The system runs on a continuous **Observe-Plan-Govern-Act** cycle, operating at a 20Hz heartbeat.

<div align="center">
  <img src="docs/assets/agentic_loop.png" width="100%" alt="Agentic Loop">
</div>

*   **0-5ms (Observe)**: The `SensorOrgan` aggregates signals from File Watchers, Log Streamers, and Input Buffers.
*   **5-50ms (Plan)**: If a signal exceeds the "Attention Threshold", the `LogicOrgan` wakes up. It asks: *Does this require Action?*
*   **50-100ms (Govern)**: The `Governor` intercepts the proposed plan. It checks against the Forbidden List and Risk Tier.
*   **100ms+ (Act)**: If approved, the `Executor` runs the tool chain.
*   **Post-Act (Reflect)**: The outcome is written to the `ActionLedger`.

---

## 🧪 Canonical Scenarios (The Rituals)

To verify the "Aliveness" of the system, run these rituals.

<div align="center">
  <img src="docs/assets/rituals.png" width="100%" alt="System Rituals">
</div>

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

## 🚫 Failure Modes & Anti-Goals

We value rigorous honesty. This system has known constraints.

<div align="center">
  <img src="docs/assets/failure.png" width="100%" alt="Failure Modes and Constraints">
</div>

### Anti-Goals (What We Will Not Do)
*   **No Chatbot UI**: We will not build a React frontend. The terminal is the interface.
*   **No "Personality" Tuning**: We will not optimize for "friendly" or "sassy". We optimize for "concise".
*   **No Silent Mods**: The system will never edit a file without leaving a Trace ID in the logs.

### Known Failure Modes
*   **Decoder Loop (The "Yapping" Bug)**: Rarely, the local RWKV model may get stuck repeating a token. We mitigate this with a "Hard Stop" circuit that kills the generation after 100 tokens if no stop token is found.
*   **Gemini Latency**: Complex reasoning trips to the cloud can take 1-2 seconds. The system "freezes" during this thought process.
*   **Ambiguity Paralysis**: If you say "Do the thing", it will ask "What thing?". It does not guess.

---

## 🗺️ Roadmap to Wisdom

<div align="center">
  <img src="docs/assets/timeline.png" width="100%" alt="Roadmap">
</div>

### ✅ Phase 1: Consolidation (Completed)
*   Merged 60+ scattered scripts into 5 Organs.
*   Established standard `main.py` entry point.
*   Implemented "Decoder Discipline" for local models.

### ✅ Phase 2: Autonomy (Completed)
*   Closed the Observe-Plan-Act loop.
*   Implemented `Governor.authorize()` for safety.
*   Added `TraceID` system for accountability.

### 🚧 Phase 3: Wisdom (In Progress)
*   **Cost Awareness**: Calculate token cost ($) before executing Cloud queries.
*   **Reflection**: If Plan A fails, remember it. Don't try Plan A again for the same task.
*   **Self-Repair**: Ability to parse a Python stacktrace and auto-patch the offending line.

### 🔮 Phase 4: Skynet (Future)
*   **Swarm Intelligence**: Multiple JARVIS instances sharing a memory pool.
*   **Docker Embodiment**: Ability to spin up containers for risky tasks.
*   **Peripheral Control**: Full keyboard/mouse injection for GUI tasks.

---

## 🧬 Contributing (The Filter)

**Warning**: This is not a standard Python project. It is an Organism.

<div align="center">
  <img src="docs/assets/contributing.png" width="100%" alt="The Code Filter">
</div>

### The 3 Commandments
1.  **Do Not Break the Laws**: Any PR that weakens the `Governor` or removes a safety check will be rejected immediately.
2.  **Respect the Ledger**: New tools **MUST** return a success/failure boolean. Tools that fail silently are banned.
3.  **Maintain Silence**: `print()` is forbidden in `core/`. Use `logging` or return strings to the `Engine`.

### The "No-Go" List (Instant Rejection)
*   ❌ **No `print()` statements**: This destroys the "Silence" axiom.
*   ❌ **No new pip dependencies**: Unless absolutely critical. We optimize for portability.
*   ❌ **No "Prompt Hacking"**: Do not try to fix bugs by adding "Please be nice" to the prompt. Fix the logic code instead.
*   ❌ **No Async without Await**: The 20Hz loop depends on non-blocking I/O.

### Pull Request Policy (The Gate)
We do not accept "Cleanup" PRs. We accept **Capability** PRs.
*   **Title**: Must match `[Component] Description`. (e.g., `[Logic] Add grep tool`)
*   **Trace ID**: You must provide a verified Trace ID in the PR description proving your new code works.
    *   *Bad*: "Added a tool."
    *   *Good*: "Added `grep`. Verified in Trace T-173998: `Grep -> Found Match -> Return`."

### How to Add a Tool (The Right Way)
1.  **Define**: Create the function in `core/logic.py`.
2.  **Register**: Add to `Executor.tools` dictionary.
3.  **Allow**: Add to `Governor.whitelist` in `core/governance.py`.
4.  **Test**: Verified with a `Ritual` run in `main.py`.

---

*Engineered with discipline by Antigravity in pursuit of the Atulya Tantra.*
