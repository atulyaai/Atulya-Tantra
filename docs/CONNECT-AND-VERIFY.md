# Connect this PC and verify actual actions

## Current verification

On 19 October 2026, a real local HTTP server and a separate Python companion process completed pairing → queued ping → execution → accepted receipt. The test also verified account isolation and revocation. This is a test on this PC, **not** a connection to the production account. The test creates temporary accounts and stores no real credential.

## Fastest live connection

1. In the Chrome session already signed in to `https://atulya.atulvij.com`, open **Devices** on the original WebUI. Create `This-PC` with `ping` and `battery_status` only for the initial check.
2. Open `Connect-This-PC.cmd` from the project folder. Paste the device credential into its hidden field and click **Connect and run companion**. Credentials stay on this PC, encrypted with Windows DPAPI in `data/companion/secrets.enc`. Do not paste them into chat or commit the file.
3. Refresh Devices. The companion should become online on its first poll. After the server update, use **Test connection**: only an `executed` ping receipt proves the round trip. On the old server, ask Atulya to list devices and ping `This-PC`, then inspect its receipt.
4. Grant additional abilities only as needed. File operations require an explicit `ATULYA_AGENT_FOLDER` grant; phone SMS/calls and speech are not implemented by the desktop companion.
5. To disconnect, revoke `This-PC` in Devices. The companion exits when its credential is rejected.

The server changes in this working folder need deployment before the new Test connection button, readiness view, music search and expanded proactive checks appear on the live service. An existing production pairing endpoint can already accept this updated PC companion.

## Terminal alternative

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m tools.device_companion --url https://atulya.atulvij.com
```

The token is requested in a hidden prompt. Once local setup has saved a connection:

```powershell
.\.venv\Scripts\python.exe -m tools.device_companion --saved --check
.\.venv\Scripts\python.exe -m tools.device_companion --saved
```

`--check` verifies the credential, not execution. `--once` executes one pending batch and exits. Never run two companions with the same device credential. Saved connections enforce a single-process lock; retry receipts are encrypted on disk and sent again without repeating the action. The server accepts identical receipt retries.

For automatic startup after Windows sign-in, after successful pairing:

```powershell
powershell -NoProfile -File .\tools\install_companion.ps1
```

This installs the user task **Atulya PC Companion**, separate from **Atulya Personal PC Host**. It does not keep a sleeping PC awake. Check connection logs in `data/companion/companion.log` for a manually started saved companion.

## Access routes

| Route | What works / requirement |
| --- | --- |
| Browser on PC/phone | Sign in to the same HTTPS server; account records live on that server. |
| Installed Android app | Same server login; native voice, composer/dialer and media features depend on the installed APK and device permissions. The current APK is not a background AgentHub executor. |
| Telegram | `ATULYA_TELEGRAM_ALLOWLIST` is **for the owner only**: every id on it acts as the administrator (owner memory, PC control, devices). Never add family members or friends there; they message the bot, send `/register <name>`, and the owner approves them as members (`tg_<id>` accounts with their own data and no admin tools). A pending approval can only be approved from the same Telegram id that asked for it. Device actions require a paired running companion; a Telegram reply alone is not execution. |
| PC companion | Outbound HTTPS connection; no inbound router/firewall port required. Only paired abilities execute. |
| Private network | Existing private HTTPS routes can replace the public origin consistently; do not expose the Python port directly. |

Avoid running multiple copies of the server against independent data directories: connections, sessions and queues will diverge. The PC companion is a client of the existing server, not a second server.

## Speed and reliability

- Default poll interval is now **2 seconds**, previously 5. Scheduling wait is approximately 0–2 seconds plus network and execution time; it is not a promised end-to-end latency. `--interval 1` reduces wait at the cost of more requests. Allowed range: 0.5–60 seconds.
- Exact test ping timing is recorded as `pc_ping_receipt_ms` in the JUnit results. It includes starting the separate test companion and must not be presented as internet latency.
- Proactive diagnostic checks run every five minutes. If enabled, changed findings may trigger AI repair proposals and attention notifications at most once per hour. Unchanged findings stay quiet. Notification acceptance does not prove phone sound or delivery.
- Music search resolves names to actual YouTube video choices without downloading media. Search has a hard 25-second timeout. Playback requires a browser/player gesture when autoplay is blocked; `playing` is recorded only from the player's state event.

## Google and repairs

Connect Gmail/Calendar through **Connections**, separate from Google sign-in, then run **Test Google access**. Account consent and server OAuth configuration are required; no code change can replace them. The readiness endpoint reports connection/scopes and recent device heartbeat, not a successful live API action.

Maintenance now checks those connection blockers and can propose edits to a small explicit list of backend modules as well as WebUI/skill files. Python/JavaScript syntax checks do not prove functional correctness; run regression tests before applying a proposal. Authentication, secrets, server setup and deployment files remain protected. Applied proposals retain rollback and refuse to overwrite subsequent edits.
