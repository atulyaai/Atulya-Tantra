# Security Model

This document describes the security controls that are enforced in the current
`main` branch and the controls that are still planned.

## Enforced Today

- Dashboard admin routes require the configured Atulya token.
- Admin token comparison uses constant-time comparison.
- Chat and model routes reject raw filesystem model paths and use checkpoint
  IDs from the local registry.
- Request payloads and query parameters are bounded in dashboard routes.
- The autonomy layer evaluates only restricted arithmetic expressions through
  an AST allowlist. It does not call Python `eval`, `exec`, or a shell.
- Training stop signals, optimizer recovery, and model management paths have
  regression tests.
- Memory write-back and cortex operations are covered by unit tests.

## Partial Controls

- Sandboxing is limited to restricted in-process controls and route-level
  validation. There is no repository-wide OS sandbox wrapper yet.
- Auditability exists through logs and tests, but not as a tamper-evident,
  append-only audit ledger.
- Dataset and skill hygiene is handled by code review and tests. A dedicated
  static scanner is not yet wired into CI on `main`.
- Encryption at rest is not enforced uniformly for all local artifacts.

## Planned Controls

- Signed first-party tool manifests with verification before loading.
- Strong process or container sandboxing for tool execution.
- Uniform encrypted storage for sensitive memory and credentials.
- Tamper-evident audit logs with hash chaining.
- A first-party skill scanner that blocks dangerous patterns before execution.
- CI gates for dependency review, static analysis, route fuzzing, and security
  regression tests.

## Operational Guidance

- Treat local checkpoints, logs, memory stores, and datasets as sensitive.
- Do not expose the dashboard on an untrusted network without a reverse proxy,
  TLS, authentication, and rate limiting.
- Keep generated training data and harvested data reviewable.
- Prefer first-party modules for tool execution, compression, and memory
  handling so security policy can be enforced consistently.
