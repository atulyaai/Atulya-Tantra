# Atulya Tantra AGI - Modular Structure

## Overview

- TinyLlama is the default local model via HuggingFace Transformers.
- Additional providers (OpenAI/Anthropic/Ollama) can be added via the LLM router.

## Key Directories

- `Core/llm/`
  - `base.py`: Provider interface
  - `router.py`: Category-based router
  - `providers/tinyllama_provider.py`: CPU-friendly TinyLlama
- `demos/`: Minimal and full demos
- `deploy/`: Docker and Kubernetes
- `webui/`: Static web UI
- `scripts/`: Helper scripts
- `Test/`: Canonical test suite

## Running a Demo

```bash
python demos/simple_working_demo.py
```

## Configuration

- Default primary: `tinyllama`
- Extend with providers by registering them in `Core/llm/router.py` usage sites.


