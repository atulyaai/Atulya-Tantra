# Atulya Tantra

Atulya is a cross-platform assistant project. Its visible product name is **Atulya**; project folder names use lowercase for consistent Windows and Linux paths.

## Current state

- `webui/` opens directly to the Atulya scene, with no intro page or buttons.
- `atulya/server.py` serves the WebUI and exposes chat, health, local speech-to-text, and local text-to-speech endpoints.
- `atulya/` is the flat core application package; providers, channels, voice, and feature plugins live under root `tools/plugins/`.
- `tools/plugins/` contains providers, channels, voice, and feature tools, organized by area. Runtime databases stay under `data/`.
- The WebUI has typed chat, continuous voice after browser microphone permission, locally archived transcripts, an automatic camera preview, and on-device hand-gesture recognition. Camera layout commands can be typed or spoken.
- The circle-burst assembly is part of the reused renderer bundle and plays on load before the humanoid settles into its idle animation.

## Install (any OS, no admin rights)

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/install.ps1 | iex
```

Linux / macOS (x86-64 or ARM64, including Raspberry Pi):

```bash
curl -fsSL https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/install.sh | sh
```

The installer downloads the code into `~/Atulya-Tantra`, reuses Python 3.10+ or installs a private Python 3.12 with [uv](https://docs.astral.sh/uv/), creates `.venv`, copies `.env.example` to `.env`, and runs setup. Setup detects the OS, CPU, RAM, and GPU and picks a matching local model runtime (GPU offload when available; the offline model is skipped on machines under 6 GB RAM). Add `-Service` (Windows) or `--service` (Linux/macOS) to start Atulya automatically at login; `-RemoveService` / `--remove-service` undoes that and keeps your data.

Docker (servers, NAS, Raspberry Pi):

```bash
docker build -t atulya .
docker run -d --name atulya -p 127.0.0.1:8501:8501 --env-file .env -v atulya-data:/app/data -v atulya-models:/app/models atulya
```

Open `http://localhost:8501`. On phones, the WebUI can be installed as an app once it is served over HTTPS (see [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md)).

## Tools, skills, and MCP

Plugins provide tools (weather, news, time, calculator, your saved memories and meetings). The chat model calls them itself, several at once when useful, so "what's it like outside in Delhi and what's 17×23?" works without exact command words. Exact commands such as `weather in Pune` are still answered instantly without a model call. Skills in `tools/skills/<name>/SKILL.md` are multi-step instructions the model loads on demand. `python -m atulya.cli mcp` exposes the public tools and every skill (as a prompt) to MCP hosts such as Claude Desktop or VS Code; see [tools/mcp/README.md](tools/mcp/README.md). Disabling a plugin in the WebUI removes its tools everywhere.

## Start from a checkout

Requirements: Python 3.10 or newer (or none: `start.bat` / `start.sh` run the installer when Python is missing).

Create `.env` from `.env.example` (`Copy-Item .env.example .env` in PowerShell, or `cp .env.example .env` on Linux/macOS). If provider keys and model names are present, Atulya tries NVIDIA, Gemini, OpenRouter, then DeepSeek, and can fall back to the local model. In automatic mode it starts one backup provider after `ATULYA_PROVIDER_HEDGE_SECONDS` (default 1.25 seconds); at most two requests overlap. Set that value to `0` to avoid overlapping provider calls. Comma-separated keys and model preferences are tried individually. Set `ATULYA_MODEL_PROVIDER` to `local` to keep chat fully offline, or to a provider name to restrict chat to that provider. WebUI replies stream as they are generated. The interface reports channel readiness without exposing configuration details.

- `ATULYA_MODEL_PROVIDER=ollama`, then set `ATULYA_MODEL_NAME` and optionally `ATULYA_MODEL_BASE_URL`.
- `ATULYA_MODEL_PROVIDER=openai-compatible`, then set `ATULYA_MODEL_NAME`, `ATULYA_MODEL_BASE_URL`, and `ATULYA_MODEL_API_KEY` as needed.
- Use `ATULYA_MODEL_PROVIDER=openrouter`, `nvidia`, `gemini`, or `deepseek` to select a matching configured cloud model.

Start with `start.bat` on Windows or `./start.sh` on Linux/macOS. Each script creates a project-local `.venv`; bootstrap updates an outdated bundled pip, installs missing or incompatible runtime packages from the pinned `requirements.lock.txt`, prepares local models, then starts the WebUI/API. First setup needs internet access. Downloaded assets are stored in project-root `models/chat`, `models/vision`, `models/gesture`, `models/voice/{stt,tts}`, and `models/runtime`; they are not downloaded into the global Python environment. Open the WebUI at `http://localhost:8501` to use passkeys.

To install the exact development/test set into an existing environment, run `.venv/Scripts/python -m pip install -r requirements-dev.lock.txt` on Windows or `.venv/bin/python -m pip install -r requirements-dev.lock.txt` on Linux/macOS. Refresh the runtime lock after changing dependencies with `pip-compile pyproject.toml --extra voice --output-file requirements.lock.txt`; add `--extra dev --output-file requirements-dev.lock.txt` when regenerating the development lock. Locks are resolved on Python 3.12; verify clean installs on the other supported Python versions and platforms before release.

After the greeting, the WebUI requests microphone and camera permission; the browser still requires the user to grant access. Spoken turns send automatically after a pause, and the mic pauses during replies. Press Escape or use the voice control to stop. Speech recognition uses local Whisper. Local Supertonic 3 TTS is used when its runtime and verified model are available; browser/OS speech is the fallback. The speech waveform follows generated audio samples for local TTS; browser speech output has no exposed sample stream. First start needs internet access to install speech packages and download models. Chat transcripts are archived under `data/conversations.sqlite3` and are not inserted into future prompts. Explicitly saved memory facts are kept separately under `data/personal_memory.sqlite3` and may be supplied as relevant context. With a cloud provider selected, chat text and images are sent to that provider; voice transcription and local TTS remain on this device.

The service uses WebAuthn passkeys and server-side sessions. Complete first admin enrollment at `http://localhost:8501`; the browser/OS asks for an authenticator. Admins can invite another local user from **USERS**; invitations expire after 24 hours, and the invited person creates their own passkey. Admins can disable users and revoke backup passkeys while preserving the last passkey on each active account. There is no lost-admin-passkey recovery UI. For remote deployment, set `ATULYA_PUBLIC_ORIGIN` to the exact HTTPS origin and put a trusted TLS reverse proxy in front of the loopback-only app; configure only that proxy's IP in `ATULYA_TRUSTED_PROXY_IPS`. First enrollment on a non-local origin also requires a random `ATULYA_ADMIN_SETUP_TOKEN` of at least 32 characters; remove it after enrollment. This remote path has not been deployed or verified. Data ownership is enforced for local accounts and separately linked Telegram identities; linking a Telegram identity to a WebUI user is not implemented. Browser conversation IDs are not a security boundary; keep the app private until remote access is verified.
See [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md) for the reverse-proxy setup and verification checklist.

## Folders

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the responsibility boundaries, plugin categories, data/model placement, provider privacy, and test strategy.
See [docs/INTEGRATIONS_CATALOG.md](docs/INTEGRATIONS_CATALOG.md) for the common → medium → rare order for plugins, MCP tools, and skills. The catalog records candidates and priorities, not implemented features.

- `atulya/` — HTTP service, runtime settings, chat history, persona, and CLI entry point; this folder is the core package.
- Core owns app startup, orchestration, configuration, domain policy, API boundaries, and persistence contracts. Keep provider SDKs and optional integrations out of `atulya/`.
- `tools/plugins/brain/` — model provider interfaces and local/cloud chat backends.
- `tools/plugins/communications/channels/` — WebUI and Telegram adapters.
- `tools/plugins/voice/` — STT and TTS interfaces/backends.
- `tools/plugins/productivity/` — calendar and meeting reminders.
- `tools/plugins/personal/` — user-controlled personal memory.
- `tools/plugins/information/` — online weather and news lookups.
- `tools/plugins/utilities/` — local calculator and clock.
- `tools/plugins/entertainment/` — category reserved for future entertainment tools.
- `tools/mcp/` — optional, allowlisted MCP server (stdio).
- `tools/plugins/toolkit.py` — the shared tool list used by model tool calling, Telegram, and MCP.
- `tools/skills/` — reusable workflow instructions (`SKILL.md`); skills do not provide integrations or permissions by themselves.
- `tools/hardware.py` — OS/CPU/RAM/GPU detection used by setup.
- `install.ps1`, `install.sh`, `Dockerfile` — installers and container image.
- `tools/bootstrap.py` — first-run environment and model setup.
- `tools/diagnostics/provider_check.py` — short configured-provider benchmark; paid OpenRouter testing requires `--include-paid`, and local Qwen testing uses `--include-local`.
- `webui/` — direct-opening WebUI and unchanged scene images.
- `docs/` — project notes and deferred-work list.
- `data/` — private runtime data; created as needed and ignored by Git.
- `models/` — ignored local assets, grouped by capability: chat, vision, gesture, voice (`stt` and `tts`), and runtime engines.
- `tools/` — optional plugins and setup utilities; integrations are grouped by capability instead of mixed into core.
- `tests/core/`, `tests/providers/`, and `tests/communications/` — focused checks grouped by category.
- `tests/e2e/` — one composed API/chat/archive flow using a deterministic model stub; no paid API calls occur in the normal test suite.

## License and artwork

The project code is licensed under [MIT](LICENSE). The reused scene artwork has separate source and licensing details recorded in [webui/ATTRIBUTION.txt](webui/ATTRIBUTION.txt); those terms still need confirmation.
