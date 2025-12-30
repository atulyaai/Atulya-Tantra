# JARVIS (Atulya Tantra)

> **Autonomous Agentic Infrastructure**
> *Built on RWKV (Local) & Gemini (Reasoning)*

![Atulya Tantra Logo](docs/assets/logo.png)

## 🌌 The Vision

**JARVIS** (Just A Rather Very Intelligent System) is not a chatbot. It is an **Autonomous Agent** designed to live on your machine, understand your filesystem, and execute complex tasks without constant supervision.

Most AI projects stop at "text generation." We pushed through to **Agency**. JARVIS observes, plans, governs its own safety, executes actions, and learns from the results. It is the realization of the *Atulya Tantra* (Incomparable System) philosophy: a machine that serves as an extension of the user's will.

---

## 🏗️ System Architecture

JARVIS is engineered to function like a biological entity, consolidated into five core "Organs."

![JARVIS Architecture](docs/assets/architecture.png)

### The 5 Organs

1.  **🧠 BRAIN (`core/brain.py`)**
    *   **Dual-Model Cortex**:
        *   **RWKV-6 (Local)**: The "Fast System." Handles routine tokens, formatting, and high-speed feedback. Tuned for silence and discipline.
        *   **Gemini Flash (Cloud)**: The "Deep System." Handles complex reasoning, visual analysis, and creative planning.
    *   **Role**: Thinking, synthesizing, and speaking.

2.  **📐 LOGIC (`core/logic.py`)**
    *   **Planner**: Generates dynamic execution strategies. It doesn't use hardcoded scripts; it invents plans based on your intent (e.g., "Analyze the error logs" -> `[List Docs, Read Log, Summarize]`).
    *   **Executor**: The hands of the system. Equipped with verifying tools (`list_files`, `read_file`, `write_file`, `search`, `delete`).

3.  **🛡️ GOVERNANCE (`core/governance.py`)**
    *   **The Governor**: A dedicated safety circuit that intercepts *every* action before execution.
    *   **Policy Brain**: Evaluates risk tiers.
        *   *Observation* (List/Read) -> **Auto-Approved**.
        *   *Mutation* (Write/Edit) -> **Traceable**.
        *   *Destruction* (Delete) -> **High Governance** (Throttles or Blocks based on confidence).

4.  **💾 MEMORY (`core/memory.py`)**
    *   **Action Ledger**: Records every success and failure. JARVIS remembers what strategies work.
    *   **Goal Manager**: Tracks hierarchical objectives across sessions.
    *   **Identity**: Maintains a consistent self-model (`I am JARVIS v1.0...`).

5.  **👁️ SENSORS (`core/sensors.py`)**
    *   **Multi-Modal Inputs**: Text, Voice (Whisper), and System Events.
    *   **Orchestrator**: A non-blocking concurrent loop that fuses these signals into a single "Stream of Consciousness."

---

## 🔄 The Agentic Loop

How does JARVIS actually *work*? It runs a continuous 20Hz cognitive cycle:

![Agentic Loop](docs/assets/agentic_loop.png)

1.  **OBSERVE**: The `SensorOrgan` picks up a signal (e.g., User types "Cleanup the logs").
2.  **PLAN**: The `LogicOrgan` asks the Brain: *"How do I cleanup logs?"* -> *Plan: List dir, finding .log, delete.*
3.  **GOVERN**: The plan is sent to the `Governor`.
    *   *Governor*: "Deleting files is risky. Is confidence high?"
    *   *Brain*: "Confidence 95%."
    *   *Governor*: "APPROVED (Trace ID: T-12345)."
4.  **ACT**: The `Executor` runs `os.remove(...)`.
5.  **REFLECT**: The result ("Success") is written to the Ledger. Future cleanup tasks will be trusted more.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Git
*   A Google Gemini API Key

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/atulyaai/Atulya-Tantra.git
    cd Atulya-Tantra
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Bootstrapping (First Run)**
    This script will download the local RWKV model (~800MB) and set up the models directory.
    ```bash
    python tools/bootstrap.py
    ```

4.  **Configuration**
    Create a `.env` file in the root directory:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```

### Running JARVIS

**One-Shot Command (CLI Mode)**
Give JARVIS a single task. It will wake up, execute, and shut down.
```bash
python main.py "Check the system logs"
```

**Presence Mode (Daemon)**
Keep JARVIS running in the background, listening for instructions.
```bash
python main.py --presence
```

---

## 🛡️ Safety & Governance

We take AI safety seriously. JARVIS is not a "permissionless" script.

*   **Filesystem Sandbox**: While JARVIS *can* access your file system, the Governor has a hardcoded "Forbidden List" (e.g., `rm -rf /`, system critical directories).
*   **Confidence Throttling**: If JARVIS is unsure (Confidence < 60%), it will **refuse** to act and ask for clarification.
*   **Traceability**: Every action has a unique `Trace ID` (e.g., `T-176713000`). You can grep the logs to see exactly *why* it did something.

---

## 🗺️ Roadmap: Phase 2 (Maturation)

We have achieved **Autonomy**. Now we aim for **Wisdom**.

*   [ ] **Cost Awareness**: "This query will cost $0.02. Is it worth it?"
*   [ ] **Self-Repair**: If a python script crashes, JARVIS should read the stack trace and patch the code itself.
*   [ ] **Visual Logic**: Fully integrating the Vision Sensor for "Look at my screen and fix this error" workflows.
*   [ ] **Identity Locking**: Cryptographically signing the core directive to prevent "jailbreaks."

---

*Consolidated & Engineered by Antigravity*
