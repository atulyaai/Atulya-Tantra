# WebUI Recommendations

## Completed Hardening

- Dashboard tokens are no longer written to model output folders.
- Authentication now expects `ATULYA_DASHBOARD_TOKEN` or a runtime-only generated token.
- Frontend login copy points users to the environment variable, not an output file secret.

## Next Improvements

- Route chat and automation actions through `yantra.dispatch.Dispatcher` so the backend stays thin.
- Stream event-bus updates from `yantra.events` to the frontend over WebSocket.
- Add a compact system-health strip backed by heartbeat model, provider (circuit-breaker-aware), Cortex, disk, and memory checks (provider check is done, need disk/memory in WebUI).
- Add visible dataset/checkpoint warnings when output folders are ignored or missing.
