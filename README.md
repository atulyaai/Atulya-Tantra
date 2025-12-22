# Atulya Tantra

Atulya Tantra is an experimental, safety-first autonomous system focused on
explicit planning, governed execution, and persistent learning.

This repository contains the core system kernel — not a chatbot, not a UI demo,
and not an agent zoo. The goal is to build a system that can plan, act, fail,
recover, and improve without relying on fragile natural language shortcuts.

---

## Project Status

Current Version: v1.0.0 (Benchmarked, Stable)  
Next Phase: v0.2 – Typed Action Schema (Design Complete)

The system is intentionally paused at the architectural boundary between
planning and execution to formalize contracts before expanding interfaces
(voice, vision, continuous loops).

---

## Core Concepts

• Planner  
Generates structured plans from goals.

• Executor  
Executes only validated, typed actions.

• Governor  
Enforces safety rules and SafePath constraints.

• Memory  
Persists procedural knowledge, successes, and failures.

• Benchmarks  
Evidence-driven evaluation of system behavior.

---

## Why Typed Actions (v0.2)

Earlier versions relied on natural language descriptions leaking into execution.
v0.2 introduces a Typed Action Schema to:

• eliminate ambiguity  
• enforce safety at the parameter level  
• enable reliable failure avoidance  
• make execution auditable and deterministic  

Natural language remains for observability only.

---

## What This Is Not

• Not a general-purpose chatbot  
• Not an AGI claim  
• Not a UI-first project  
• Not a plug-and-play assistant  

This is a systems research project focused on correctness, resilience, and
long-term extensibility.

---

## Roadmap (High-Level)

✓ v1.0.0 — Benchmarked core loop  
✓ v0.2 — Typed Action Schema (design)  
→ Minimal Living Loop (single input → output)  
→ Continuous execution mode  
→ Multimodal interfaces (voice, vision)  
→ Modular agent expansion  

---

## Project History (Changelog)

### [v1.0.0] - 2025-12-23
- **Learning Activation**: Procedural Memory for `SUCCESS_RECALL` and `FAILURE_AVOID`.
- **Improved Governance**: Standardized `SafePath` and expanded forbidden signatures.

### [v0.1.0] - 2025-12-23
- **System Hardening**: Introduced Governor and SafePath.
- **TraceID**: Initial support for execution tracking.

### [v0.0.1] - 2022-12-22
- **Core Loop**: Initial implementation of the 7-stage cognitive loop.

---

## Philosophy

Slow is smooth.  
Explicit beats clever.  
Safety before scale.  
Evidence before confidence.