# Atulya architecture

This document defines where responsibilities belong. Keep the deployed assistant named **Atulya**; Codex is the development agent, not a runtime speaker or user role.

## Boundaries

```text
WebUI / Telegram / future channels
                 |
                 v
atulya/  core service, orchestration, policy, settings, persistence boundaries
       |                 |                    |
       v                 v                    v
tools/plugins/       data/                models/
optional tools       local records        downloaded weights and runtimes
and providers
```

### `atulya/`: core only, kept flat

Core owns application startup and HTTP routes, configuration, request orchestration, domain rules/persona, provider selection policy, and the contracts for persistence and channel interaction. Keep files directly in `atulya/` while the package remains small. Core may call plugin interfaces, but should not absorb provider SDKs, channel-specific polling, model implementations, or optional feature implementations.

### `tools/plugins/`: optional implementations

Plugins implement capabilities that can be replaced or disabled without changing the core domain model. Organize them by responsibility:

| Path | Responsibility |
| --- | --- |
| `tools/plugins/brain/` | Chat-provider interfaces, cloud backends, local LLM backend, provider selection |
| `tools/plugins/communications/channels/` | WebUI and Telegram channel adapters |
| `tools/plugins/voice/` | Speech recognition and synthesis interfaces/backends/setup |
| `tools/plugins/memory/`, `personal/` | Memory contracts and user-controlled memory implementation |
| `tools/plugins/productivity/` | Calendar and reminders |
| `tools/plugins/information/` | Weather and news lookup |
| `tools/plugins/utilities/` | Calculator and clock |

`tools/bootstrap.py` prepares the environment and assets; `tools/diagnostics/` contains opt-in operational probes. A plugin should expose a small interface, declare its dependencies and configuration, fail with a safe actionable status, and never print credentials.

`tools/plugins/toolkit.py` is the single list of model-callable tools; each tool belongs to a plugin manifest, so disabling a plugin removes its tools from chat, Telegram, and MCP alike. The brain runs a bounded call loop (`Brain.stream(..., toolbox=...)`) and never executes tools on its own. `tools/mcp/` is an optional stdio MCP server exposing the public subset of those tools. `tools/skills/` holds reusable workflow instructions; the model sees their names and loads a body through the `use_skill` tool, and MCP publishes them as prompts. Skills do not grant tool permissions, and an MCP adapter must not bypass the core authorization boundary.

### Built-in command plugins

`tools/plugins/registry.py` dispatches deterministic built-in command handlers registered explicitly by core. Each feature category has a `plugin.json` manifest describing its identity, category, command labels, permissions metadata, and default enabled state. WebUI `/api/chat` and allowlisted Telegram private chats use the same registry for memory, calendar, information, clock, and calculator commands. Telegram's reserved slash commands remain channel-specific. The WebUI can enable or disable these fixed handlers through `/api/plugins`; choices persist in `data/plugin_settings.json` and apply to both channels. This is not arbitrary plugin auto-discovery, a sandbox, or LLM tool calling: handlers are Python code imported by the fixed registry, and permission labels are descriptive only. Do not add sensitive data access or system control until ownership scoping and guarded execution exist.

### `data/` and `models/`

- `data/` stores runtime records such as conversations, personal memories, calendar entries, and reminders. Conversations, memories, and calendar entries are keyed by authenticated user ID plus channel/conversation ID; old local rows migrate to the existing admin, while Telegram transcript/fact/event rows are assigned to their Telegram sender. Data is local and currently not encrypted. Conversation IDs are not authentication.
- `models/` stores downloaded weights and runtimes grouped by capability (`chat`, `vision`, `gesture`, `voice/stt`, `voice/tts`, and `runtime`). Do not place model files inside `atulya/` or in a global cache when the app can use the project-local model directory.
- Startup scripts create/repair the project `.venv`, update a vulnerable/outdated bundled pip, install runtime dependencies from the pinned `requirements.lock.txt`, and prepare configured local assets. Development tools are pinned separately in `requirements-dev.lock.txt`. Optional model assets may be skipped offline and retried later.
- Bootstrap verifies the MediaPipe package tarball against the npm registry's SHA-512 SRI value for the pinned version, then checks the extracted runtime files and gesture model against project-pinned SHA-256 digests before accepting them. Runtime tar extraction uses Python's `data` filter when available and a strict no-link extraction fallback on older supported Python versions.

### Channels and message identity

Channel adapters translate incoming channel events into the core request shape and deliver core replies back to their channel. They do not own model selection or business rules. Stored speaker roles are `user` for a human/Admin message and `assistant` for an Atulya response. A conversation ID separates transcripts in the current browser/client; it is not a verified user ID or an access-control boundary.

The local API requires a WebAuthn passkey session for private routes. The first passkey creates the admin account; admins can issue expiring one-time invitations for additional local users. Each user enrolls their own passkey. Admins can disable users and revoke a passkey only if that account has another credential; there is no lost-admin-passkey recovery UI. Challenges are one-time, sessions are opaque and stored as hashes, and cookies are HttpOnly/SameSite=Strict. Conversation, memory, and calendar records are separated by authenticated principal, with legacy rows kept under admin and Telegram records mapped by sender. Face recognition may help identify an enrolled local profile, but must not grant access. Do not store biometric templates by default. Channel-to-account linking and shared-account policy remain pending; keep the service on loopback.

Settings reject non-loopback bind addresses, the HTTP app only accepts loopback Host headers, and the Docker image binds to container loopback without publishing a port. This reduces network exposure and complements the local admin passkey; it does not make client-generated conversation IDs secure or support remote access. Explicitly saved memories are supplied as untrusted user context rather than trusted system instructions.

### Provider selection and privacy

Automatic cloud selection starts the preferred candidate, then hedges one additional configured candidate after `ATULYA_PROVIDER_HEDGE_SECONDS` (default 1.25 seconds) if no response has arrived. At most two candidates run concurrently, with a 30-second total budget for cloud attempts and a 20-second per-attempt timeout. A winning result cancels the other request on a best-effort basis; cancellation cannot guarantee that a provider did not process or bill the request. Set the delay to `0` to use sequential fallback. HTTP keep-alive connections are pooled and reused. HTTP 402 and 429 candidates enter cooldowns, and hard configuration errors are skipped until restart. The local model remains the final fallback when configured. Explicit provider selection restricts routing to that provider. WebUI chat streams text deltas to the browser; Telegram and other callers use complete responses. Cloud chat sends prompts (and images for vision requests) to the selected provider; local STT and local model execution remain on-device. Never include `.env` values, authorization headers, or raw provider exceptions in UI status or logs.

Free, paid, and local probes are opt-in diagnostics, not part of the normal test suite. Paid probes require the explicit `--include-paid` flag and should use a minimal prompt/token cap. Provider availability and response time vary; hedging improves time to first response when a candidate is slow, but does not establish that one provider is universally fastest.

### Tests and verification

- `tests/core/`: core state and persistence behavior.
- `tests/providers/`: provider selection and fallback behavior.
- `tests/communications/`: channel and reminder integration behavior.
- `tests/plugins/`: built-in command registry and manifest behavior.
- `tests/e2e/`: a composed API chat/archive flow using a deterministic in-process provider stub. It verifies speaker roles and conversation-ID separation without a network or billable API.
- `tools/diagnostics/provider_check.py`: explicit real-provider and local-model connectivity/timing probes. It is operational verification, not a deterministic test.
- Telegram reminder claims are transactionally leased in SQLite so concurrent pollers do not claim the same due row at once. Delivery errors back off and stop after five attempts; this gives at-least-once delivery semantics (a process crash after Telegram accepts a message but before SQLite records success can still produce a duplicate).

The ordinary test suite must not require internet, API credentials, camera/microphone permissions, or a paid API call. User-device checks (camera framing, browser permissions, actual voice quality, Telegram polling ownership) remain separately documented as pending until verified on the target device/service.
