# Atulya Runtime v1

`atulya_runtime` is the production boundary for Atulya. It owns durable local
state, the versioned API, user-scoped memory, and a policy-controlled action
executor. The legacy `core/` prototype remains available for reference but is
not the production entrypoint.

## Run locally

```powershell
cd brain
python -m pip install -r requirements-runtime.txt
python run.py
```

The service binds to `127.0.0.1:8000` by default. Set `ATULYA_HOST` and
`ATULYA_PORT` only when an authenticated front end is in place. Runtime data is
stored in `brain/data/atulya.sqlite3` by default and is ignored by Git. Set a
strong `ATULYA_API_TOKEN` before sharing the service beyond the local machine;
all `/v1/*` routes will then require `Authorization: Bearer <token>`.

To use a model, configure an OpenAI-compatible endpoint (for example, your
local inference server):

```powershell
$env:ATULYA_MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
$env:ATULYA_MODEL_NAME = "your-local-model"
# Set ATULYA_MODEL_API_KEY only when the provider requires it.
```

## API contract

- `GET /health`: process health.
- `GET /ready`: database readiness.
- `POST /v1/respond`: persists a user turn and returns an assistant response.
- `POST /v1/memories`: creates a user-scoped memory.
- `GET /v1/users/{user_id}/memories`: reads that user's active memories.
- `POST /v1/actions`: proposes a workspace-scoped action.
- `POST /v1/actions/{id}/approve`: explicitly approves a pending write.

Read-only actions (`list_files`, `read_file`) execute automatically inside the
configured workspace. `write_file` always requires explicit approval. Every
action has a trace ID and is persisted in SQLite.

## Gateway integration

The Atulya Gateway should be a thin authenticated client of this API:

1. Map channel identity to a stable `user_id` and conversation identity to a
   stable `session_id`.
2. Forward messages to `/v1/respond`.
3. Present pending actions to the user; call the approval endpoint only after
   their explicit confirmation.
4. Never expose this local API directly to the public network without gateway
   authentication, rate limiting, and TLS.

## Current deliberate limitation

When no model provider is configured, the response method is deliberately
deterministic. A configured model receives conversation text only; it has no
ability to execute actions. Actions are created through the separate policy and
approval API.
