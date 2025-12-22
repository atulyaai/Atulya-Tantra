# Atulya Tantra v1

A cognitive task-execution system with a strict core loop and file-based memory.

## Quick Start
```bash
python run_atulya_tantra.py "Your task here"
```

## Core Specs
- **Architecture**: `INPUT → INTENT → PLAN → ACT → CHECK → LEARN → OUTPUT`
- **Safety**: Managed by `Governor` and `SafePath` validation.
- **Memory**: Persistent JSON storage (Episodic, Procedural, Principle).

For technical details, see [ARCHITECTURE.md](ARCHITECTURE.md).
For project history, see [CHANGELOG.md](CHANGELOG.md).
