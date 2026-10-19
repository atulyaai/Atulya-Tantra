# Actions and connection verification

Atulya should execute through tools and describe the result supported by the receipt. A configured model, paired device or HTTP 200 health endpoint is not evidence that an action completed.

| State | What the assistant may say |
| --- | --- |
| Missing connection | Name the missing service/device and the shortest setup step. |
| Awaiting approval | Explain the requested action and target; do not claim execution. |
| Queued | The server stored a request. The target device has not confirmed it. |
| Running | A companion accepted the job; execution is still pending. |
| Executed | The companion returned a successful result. Read the result's limits: OS request acceptance is not proof of app readiness or audible playback. |
| Unconfirmed | The receipt was not received within the running timeout. Never replay a side effect automatically. |
| Failed | Explain the failure and a useful next step; do not convert it to success. |

## Check a device

Open **Devices → Test connection**. This queues a harmless ping using the signed-in account and waits for its execution receipt. Refresh shows later results if the device takes longer than 15 seconds.

- Android: open and unlock the installed app; its companion runs only while it is open/unlocked. Pairing is not a background listener.
- PC: run `tools/device_companion.py` with the per-device `ATULYA_AGENT_URL` and `ATULYA_AGENT_TOKEN`; grant `ATULYA_AGENT_FOLDER` only if file access is needed. The default poll interval is two seconds plus network/execution time. Credentials must never be pasted into public issues or chat logs.
- Windows setup: run `Connect-This-PC.cmd` in an installed source checkout, or the portable `Atulya-PC-Companion.exe`. Create a device in the signed-in Devices panel and paste its credential into the local setup window. Saved credentials and receipt outboxes use Windows DPAPI; the portable app stores them in `%LOCALAPPDATA%/Atulya/Companion`. Keep the companion process running. It does not yet install a startup service.
- Revoke a device in Devices to stop its credential. A new sign-in does not prove old jobs were executed.
- Readiness now distinguishes an offline paired device from a live companion. Owner-scoped ping tests cannot target another account's device.

## Google and channels

The owner can inspect the primary host using `server_status` without configuring SSH back to the same machine. `ATULYA_SERVERS` adds separate SSH hosts; an empty list does not disable primary-host diagnostics. `server_logs` reads bounded, redacted log excerpts from the configured data/log directory and rejects non-owner requests. These tools do not provide arbitrary shell access or service restarts. Maintenance can inspect and propose changes only within its permitted source-file list.

Google login and Gmail/Calendar service authorization are separate. Use **Connections → Connect Gmail/Calendar → Test Google access**. OAuth client configuration, the required service scopes and API activation are necessary. Successful empty Calendar delete responses are handled explicitly.

Telegram sends requests through the shared server/tool registry; a device action still needs a connected target and the required approvals. WhatsApp requires a configured Business integration. Gmail tools do not implement an email inbox command listener. None of these connections means software can silently install itself on another device.

## Reliability changes

- Completion-only, text-streaming and automatic model providers retain the action fallback; rejected native tool schemas can fall back to the existing text-call protocol.
- Closing the tool budget now prevents additional native side effects.
- The public URL reader pins its connection to a validated public address and preserves Host/TLS verification; redirects are resolved and validated separately. Environment proxies and cross-host TLS connection reuse are disabled for this client.
- Unsupported smart-home actions are refused instead of mapped to `turn_off`; qualified light/switch entity IDs are preserved.
- Stale running jobs become unconfirmed when status is read, even if the device never reconnects.
- PC receipt retries do not repeat the action. Identical server receipts are idempotent; a different owner or changed outcome cannot overwrite one.
- Android persists receipts and retries failed uploads before accepting more jobs. Slow polls cannot accumulate a backlog, and jobs delivered after the app leaves the foreground are refused.
- Saved Windows companions persist receipt uploads across restarts and prevent duplicate companion processes from using the same saved connection.
- Phone media controls fail when no prepared Atulya audio stream exists. Stream errors and stop-during-preparation release the player without crashing the app.
- Pull requests now compile the APK, run Android receipt unit tests, and exercise phone pairing, approvals, missing audio, and foreground reconnection on an emulator without release signing credentials.
- Missing PC apps, unsupported media actions and failed photo writes produce failed receipts.
- The deployment script rolls back after a failed functional selftest, even when the health endpoint passes.

Regression coverage includes a controlled DNS-rebinding attempt, tool-budget limits, provider fallbacks, Calendar HTTP 204, invalid smart-home actions, offline jobs, receipt loss, credential revocation, and a real HTTP server with a separate PC companion process. Tests use temporary accounts and mocks rather than live Google mutations or device side effects.
