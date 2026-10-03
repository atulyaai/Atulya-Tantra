# Drishti Recommendations

## Completed Hardening

- Dashboard tokens are no longer written to model output folders.
- Authentication now expects `ATULYA_DASHBOARD_TOKEN` or a runtime-only generated token.
- Frontend login copy points users to the environment variable, not an output file secret.

## Next Improvements

- Keep route handlers thin: put logic in `atulya/` (cognition kernel and agent tools), not in `drishti/dashboard/routes/`.
- Stream event-bus updates from `yantra.events` to the frontend over WebSocket.
- Add a compact system-health strip backed by heartbeat model, provider (circuit-breaker-aware), Cortex, disk, and memory checks (provider check is done, need disk/memory in Drishti).
- Show the audit log (`assets/agent/audit.jsonl`) and PC-control status in the UI.
- Offer a one-click "lockdown" profile (localhost only, no wildcard CORS).
