# Atulya Tantra - Architecture & Design Report (v1)

## Executive Summary
Atulya Tantra is a cognitive task-execution system designed for high determinism, safety, and observability. It operates on a closed-loop architecture where every action is governed, logged, and evaluated for future learning.

## Core Cognitive Loop
The system follows a strict sequential cycle:
`INPUT → INTENT → PLAN → ACT → CHECK → LEARN → OUTPUT`

1.  **INPUT**: Raw task string from the user.
2.  **INTENT**: Classification into logical categories (Search, File Ops, etc.).
3.  **PLAN**: Decomposition into a series of actionable steps.
4.  **ACT**: Execution of steps via specialized tools under Governor oversight.
5.  **CHECK**: Formal verification of results against initial requirements.
6.  **LEARN**: Persistence of trace data and procedural patterns for future recall.
7.  **OUTPUT**: Final status and TraceID reported to user.

## System Components

### 1. Logical Roles
- **Interpreter**: Classifies task intent using weighted keyword analysis.
- **Planner**: Generates multi-step execution strategies, consulting Procedural Memory for optimizations.
- **Executor**: Dispatches actions to tools and handles error routing.
- **Critic**: Provides a final verdict on task success/failure.
- **Governor**: Enforces safety constraints (SafePath, Forbidden Signatures).

### 2. Memory Architecture
- **Working Memory**: In-memory state for the current loop execution.
- **Episodic Memory**: JSON-based history of all past task traces.
- **Procedural Memory**: Collection of successful and failed step patterns (`SUCCESS_RECALL` / `FAILURE_AVOID`).
- **Principles Memory**: Hardcoded and earned safety rules guiding the Governor.

## Safety & Governance
- **SafePath**: All file operations are confined to the repository root. Path traversal (`..`) is explicitly blocked.
- **Forbidden Signatures**: Intent-level blocking of dangerous commands (eval, exec, subprocess, etc.).
- **TraceID**: Every task is assigned a unique 8-character ID for cross-module log correlation.

## Observability
- **System Log**: Centralized, structured record of every transition, safety check, and cognitive event.
- **Causal Traceability**: Every log line is tagged with a `TraceID`.

---

## Future Roadmap: v0.2 — Typed Action Schema

The v0.2 phase formalizes the interface between the **Planner** and the **Executor** to eliminate ambiguity and enforce safety at the parameter level.

### 1. Typed Action Schema
Actions are no longer parsed from natural language descriptions. Instead, they follow a structured JSON schema:
- **`action`**: Verb (e.g., `create_file`).
- **`params`**: Explicit fields (e.g., `filename`, `content`, `path`).
- **`description`**: Human-readable intent (Observability only).

### 2. Planner → Executor Contract
- **Contract Rule**: The Executor rejects any action with missing mandatory parameters.
- **Resilient Fallback**: When `FAILURE_AVOID` triggers, the Planner must vary the `params` (e.g., different search query) rather than repeating the exact failed configuration.

### 3. Immediate Implementation Goal: The Minimal Living Loop
Following schema formalization, the system will implement a single-cycle loop where a user input produces a visible, governed output, proving the engine "breathes" before further expansion.
