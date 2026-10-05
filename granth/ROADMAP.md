# Atulya Tantra: feature map and next roadmap

This is the consolidated plan for growing Atulya into a dependable personal assistant. “Implemented” means the code and local checks exist; it does not mean the owner has verified the feature on a real device or public server.

## What already exists

| Area | Current capabilities | Limits to keep visible |
|---|---|---|
| Brain and conversation | FastAPI server, React/Vite screen, local and cloud model providers, provider fallback, chat history, voice input/output | Speed and Hindi quality depend on the selected provider and hardware |
| Personal assistant | Reminders, calendar, routines, price tracking, contacts, email and Telegram actions, money notes and bank-alert parsing | External services need owner setup; never say an email, message, purchase, or booking happened until its service confirms |
| Computer and devices | Local desktop tools, smart-home/device drivers, pairing and permission levels, action confirmation, audit log | Hardware and OS-specific behaviour remains unverified until tested on the owner’s devices |
| Web app and phone shell | PWA, installable Capacitor Android shell, saved server address, service-worker update prompt | A debug APK is not a Play Store release; native push and Android permissions need device checks |
| Deployment | Docker image and Compose Cloudflare Tunnel template, Oracle/Cloudflare click-by-click deployment guide | No public VM or website is being created in this work; first prove the whole stack locally |

## Newly consolidated work in this branch

- **Phone companion:** paired phone tokens can send bounded SMS, notification, and location batches to separate phone inbox storage. The admin dashboard can issue pairing codes, review/clear inbox items, and disconnect devices. The bank-SMS endpoint remains separate and its setup secret is now admin-only. Owners can ask Atulya to ring or locate a full-permission phone and read its recent inbox. The optional Termux script polls for commands and syncs only the categories explicitly enabled in its environment.
- **Background push delivery:** the existing live WebSocket remains the foreground path. Optional Web Push uses VAPID settings and the existing subscription feature for background alerts; it is disabled until the server operator installs the `push` extra and supplies keys.
- **Other-computer companion:** a paired computer checks in over HTTPS, receives only device-scoped queued work, and runs a narrow allowlist through the same `sharir.py` permission and path rules as local control. Results are size-limited and scoped to the paired device.
- **Mobile API routing:** PWA calls, streaming, voice, and WebSocket connections use the saved server address, including the local address during local checks.
- **Cross-platform CI and release packaging:** GitHub Actions check Linux/Windows and Python 3.11/3.12, build the PWA, package source plus built frontend, and build a debug APK on version tags.
- **Windows correctness:** permission tests now check Windows ACLs, temporary folders remain usable while browser profiles stay blocked, command-line parsing handles Windows quoting, and the ADB test double launches consistently on Windows.

These features are not yet verified on a real Android/Termux device, a second computer, an Oracle VM, or Cloudflare Access. The PR must pass local checks before any public deployment step.

## Remove overlap and preserve one source of truth

1. **Bank SMS versus phone sync:** `/api/money/sms` only parses financial alerts using its dedicated inbox key. `/api/phone/sms` stores paired-phone inbox data. Do not merge these payloads or credentials.
2. **Foreground versus background notifications:** WebSocket delivers while Atulya is open; VAPID Web Push covers supported browsers while suspended. Reuse the same event and subscription store rather than adding another push provider or alert database.
3. **Local versus remote computer tools:** both call `sharir.py`; keep file boundaries, blocked paths, permission checks, and output limits there. Do not create a second remote-only executor or shell bypass.
4. **Pairing and authority:** phone and computer agents use the existing paired-device registry and tokens. Do not add a separate pairing database, agent password, or role model.
5. **Messages:** keep the contact book and `message_send` as the user-facing multi-channel flow. Email-specific setup/read tools can remain specialized, but sending must converge on the same provider implementation and confirmation policy.
6. **Version and updates:** package metadata currently has multiple version values. Fix that before automatic updates. Keep updating manual and signed/checksummed until staging, health checks, and rollback have an end-to-end test.

## Next milestones

### 1. Local reliability gate — required before deployment

- Run `python -m pytest -q`, `ruff check atulya pariksha`, and `cd drishti && npm ci && npm run build` on the current branch and resolve all failures.
- Run the server locally, sign in, chat, use the UI update prompt, and check that the frontend calls the local server address.
- Build and start the Docker image locally; check the UI, API, and WebSocket through the container.
- Verify paired-device rejection and admin boundaries using the tests. Never add real bot tokens or passwords to test files.

### 2. Device-integration verification

- Pair a spare Android phone and verify each Termux permission prompt, SMS/notification/location upload, token revocation, ring, and location request.
- Pair a second computer; verify read-only and full permission, offline recovery, revoked token rejection, and blocked folder access.
- Verify the owner-facing pairing/inbox panel’s real-device behaviour and add visible online/last-seen states for phones as needed.
- Record every real-device result in `granth/STATUS.md`; until then label it unverified on hardware.

### 3. Safe long-running work

- Add an explicit job list, progress, cancellation, and expiry using the existing routines/trigger conventions.
- Require confirmation before external side effects; persist enough state to survive restart without repeating a completed action.
- Add resource/time limits and notifications for completion or failure. Do not create parallel schedulers for reminders, routines, and jobs.

### 4. Operations and updates

- Choose one authoritative version value and make Python, frontend, APK, and release assets display it consistently.
- Keep CI as the release gate; attach a source bundle, PWA assets, debug APK, and checksums.
- Add updater staging, signature/checksum validation, a health probe, backup, and tested rollback before enabling automatic updates.
- Add scheduled encrypted backups and a restore drill for `kosh/`; a backup is not complete until restore works.
- Add per-user and per-route throttling, retention controls for phone data, and audit-log export/rotation.

### 5. Public deployment — only after milestones 1 and 2

- Follow the click-by-click Oracle and Cloudflare steps in `DEPLOYMENT.md`.
- Keep inbound VM web ports closed. Use Cloudflare Access for the web UI and narrowly bypass only token-protected enrollment, phone, and companion routes with rate limits.
- Verify signed-out browser access, owner login, paired-agent access, token revocation, restart recovery, and backup restore before calling the site ready.

## Longer-term Jarvis capabilities

After the reliability and operations work: user feedback and preference correction; named cross-device scenes; richer Hindi/Hinglish recognition and natural offline speech; voice/face presence only with explicit opt-in; stronger OS sandboxing; safer browser workflows; and background research jobs. Real purchase/payment, unattended door unlocking, and private-data collection must remain explicit owner-approved actions.
