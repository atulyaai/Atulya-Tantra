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
