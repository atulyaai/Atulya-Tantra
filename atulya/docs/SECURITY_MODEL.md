# Security Model

What is enforced today, and what is not.

## Enforced Today

- **Login:** API routes need a session token or the admin token (`X-Atulya-Token`), compared in constant time. On the computer Atulya runs on, `/api/auth/local` signs you in without a password; it refuses proxied and remote requests, and `ATULYA_REQUIRE_LOGIN=on` turns it off.
- **Risky actions ask first:** sending email, deleting events or reminders, unlocking doors, running code, and all PC control need your confirmation (`atulya/cognition/safety.py`). `ATULYA_AUTO_APPROVE` can pre-approve specific ones.
- **PC control is off by default:** `ATULYA_PC_CONTROL=on` enables it; it only opens apps from a fixed list and blocks dangerous shortcuts.
- **Audit log:** every tool call is appended to `assets/agent/audit.jsonl` with passwords and tokens masked; admins can read it at `GET /api/audit`.
- **Triggers cannot be hijacked:** event data never becomes a command, and risky trigger commands are refused unless the rule allows them.
- **Network guard:** the price tracker and web fetch tools only reach public addresses (`SSRFProtection`).
- **No `eval`:** math goes through an AST allowlist (`atulya/core/safe_eval.py`).
- **Bounded inputs:** request payloads and query parameters are size-limited; chat rejects model paths and empty prompts.
- **Lockdown profile:** `ATULYA_LOCKDOWN=on` listens on localhost only and allows no cross-site callers.

## Not Done Yet

- No OS-level sandbox for tools; protection is the confirmation prompt and allowlists.
- The audit log is a plain file, not tamper-evident.
- Memory, chat history and credentials are stored unencrypted (`yantra/capabilities/encrypted_storage.py` exists but is not wired in).
- By default the server listens on all interfaces with open CORS so the phone app can connect. Use lockdown, or set `ATULYA_HOST` and `ATULYA_CORS_ORIGINS`, to tighten this.
- No rate limiting.

## Guidance

- Treat `assets/` (memory, audit log, tokens), `.env` and `config/chat_history.json` as sensitive; they are git-ignored.
- Do not expose the dashboard to an untrusted network without TLS, a reverse proxy and login.
- See `docs/DEPLOYMENT.md` for the hardening checklist.
