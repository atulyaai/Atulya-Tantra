# JARVIS (Atulya Tantra)

> **Autonomous. Local. Agentic.**
> *The Incomparable System*

<div align="center">
  <br>
  <img src="docs/assets/logo.png" width="500" alt="Atulya Tantra Logo">
  <br>
  <br>
  <b><a href="#-getting-started">Getting Started</a></b>
  •
  <b><a href="#-architecture">Architecture</a></b>
  •
  <b><a href="#-agentic-loop">The Loop</a></b>
  •
  <b><a href="#-roadmap">Roadmap</a></b>
  <br>
  <br>
</div>

---

## 🌌 The Philosophy

**Atulya Tantra** (*The Incomparable System*) represents a divergence from modern AI development. While the industry races to build bigger "Chatbots" that wait for your input, we asked a different question:

> *What if the AI didn't wait?*
> *What if it lived on your computer, understood your goals, and worked alongside you?*

**JARVIS** is the answer. It is an **OS-Level Organism**. It feels pain when code fails. It feels joy when tests pass. It has hands to write files, eyes to read logs, and a brain to govern its own actions.

<div align="center">
  <img src="docs/assets/comparison.png" width="100%" alt="Chatbots vs JARVIS">
  <br>
  <em>Figure 1: The Evolution from Tools to Agency.</em>
</div>

---

## 💎 why JARVIS? (The USP)

| Feature | Standard "AI Assistant" | JARVIS (Atulya Tantra) |
| :--- | :--- | :--- |
| **Initiative** | Passive (Wait for Prompt) | **Active (Background Presence)** |
| **Architecture** | Single Script / LLM Call | **5-Organ Biological System** |
| **Execution** | Text Output Only | **Real Filesystem & Tool Access** |
| **Safety** | "Trust the Model" | **Dedicated Governance Circuit** |
| **Reliability** | Hallucinates Loops | **Hard-Stop Decoder Discipline** |
| **Cost** | High (Cloud Only) | **Hybrid (Local Reflexes + Cloud Logic)** |

---

## 🏗️ Structure & Anatomy

JARVIS is not a spaghetti script. It is engineered with the precision of a biological entity.

<div align="center">
  <img src="docs/assets/architecture.png" width="100%" alt="System Architecture">
</div>

### 1. 🧠 Brain (The Cortex)
*   **Local Reflexes (RWKV-6 0.4B)**: The "Fast System" (Thinking Fast). Handles routine checks, formatting, and high-speed silence. Runs locally on CPU/GPU.
*   **Cloud Reasoning (Gemini Flash)**: The "Deep System" (Thinking Slow). Wakes up for complex planning, visual analysis, and creative strategy.

### 2. 📐 Logic (The Hands)
*   **Dynamic Planner**: JARVIS does not use hardcoded chains. It *invents* plans.
    *   *Intent*: "Fix the broken imports."
    *   *Plan*: `Search(grep error) -> Read(file) -> Patch(write) -> Verify(run)`.
*   **Executor**: A tool-wielding engine that touches the real world (`os`, `subprocess`, `browser`).

### 3. 🛡️ Governance (The Conscience)
*   **The Governor**: An immutable safety layer that intercepts *every* action.
*   **Traceability**: Every action generates a unique `Trace ID` (e.g., `T-171234`).
*   **Confidence Throttling**:
    *   *Confidence > 90%*: Auto-Execute.
    *   *Confidence < 60%*: **Ask Permission**.
    *   *Destructive Action*: **Block** (unless overridden).

---

## 🔄 The Agentic Loop

This is the heartbeat of autonomy. It beats 20 times a second.

1.  **OBSERVE**: Sensors pick up a signal (User command, File change, System Error).
2.  **PLAN**: The Brain formulates a multi-step strategy.
3.  **GOVERN**: The Governor validates the plan against safety policies.
4.  **ACT**: The Executor runs the tools.
5.  **REFLECT**: The result is written to the `ActionLedger`. Success strengthens the neural pathway; failure weakens it.

<div align="center">
  <img src="docs/assets/dashboard.png" width="100%" alt="Neural Dashboard">
  <br>
  <em>Figure 2: The Cognitive Dashboard monitoring the Agentic Loop.</em>
</div>

---

## ⏳ Evolution Roadmap

We are building towards Skynet (The Good Kind).

<div align="center">
  <img src="docs/assets/timeline.png" width="100%" alt="Project Roadmap">
</div>

### ✅ Phase 1: Consolidation
*   Merged 60+ scattered scripts into a clean, modular architecture.
*   Established the 5-Organ biological standard.

### ✅ Phase 2: Autonomy (Current)
*   Closed the "Observe-Plan-Act" loop.
*   **Achievement Unlocked**: Stabilized local model "Infinite Loops" using strict decoder discipline.

### 🚧 Phase 3: Wisdom (Next)
*   **Reflection**: JARVIS will *refuse* to repeat a plan that failed 3 times.
*   **Cost Awareness**: "This query will cost $0.02. Is it worth it?"

### 🔮 Phase 4: Skynet
*   **Self-Replication**: Ability to deploy sub-agents to Docker containers.
*   **Swarm Intelligence**: Multiple JARVIS nodes communicating over a mesh network.
*   **Embodiment**: Full control over OS peripherals (Mouse, Keyboard, Camera).

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
python main.py "Scan the core directory and summarize the logic structure"
```

**Presence Mode (Daemon)**
Keep JARVIS running in the background, listening for instructions.
```bash
python main.py --presence
```

---

## 🤝 Contributing to Atulya Tantra

We welcome other architects of the future.
1.  Fork the repo.
2.  Create your feature branch (`git checkout -b feature/NewOrgan`).
3.  Commit your changes.
4.  Push to the branch.
5.  Open a Pull Request.

---

*Engineered in pursuit of the Atulya Tantra.*
