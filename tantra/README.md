# Tantra Folder Boundary

`tantra/` is the support and compatibility layer inside the Atulya-Tantra app repo.

It should contain:

- security, encryption, context, and task-classification helpers in `core/`
- support-layer config and scripts
- compatibility links needed by Drishti, Atulya, and Yantra
- legacy NP-DNA code kept so older routes, tests, and artifacts still load

It should not be the active home for custom LLM work.

Keep these in the separate LLM/model repository:

- model architecture changes
- tokenizer development
- training jobs and dataset growth
- checkpoints and benchmark releases
- model release notes

When Atulya needs a local custom model, expose that model through a provider endpoint or adapter, then connect it from this repo through the router layer.

## Legacy Subfolders

`npdna/`, `training/`, `outputs/`, and related evaluation scripts are retained for historical compatibility. Avoid adding new active model-training features here unless the model repo split is intentionally reversed.
