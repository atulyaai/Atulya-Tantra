# Atulya — verified work list (14 October 2026)

This replaces earlier claims that code presence meant a working feature. Status means **live verified**, **implemented but device verification pending**, **local draft**, **missing**, or **requires owner connection**. Mark complete only with an execution receipt or relevant test evidence.

## Confirmed live

- Chat, calculation, weather retrieval, saved memory and server speech passed earlier real checks.
- One authorized Telegram reminder reached Android; notification was silent. This proves message arrival, not sound/vibration.
- PR #88 deployed: document prototypes, unexecuted workflows and service restart no longer claim success.
- Reminder #2 was cancelled on 13 October; it did not deliver.
- Daily Surah Yaseen routine was independently enabled and fired on 14 October. Disabled on server with backup, 14 October.
- Gesture runtime/model assets exist and hashes were checked. Recognition on the owner's phone remains unverified.
- Proactive proposals enabled with owner consent; production changes still require review.

## P0 — stop incorrect behavior

- [ ] Deploy and verify scheduling fixes: no default subscriptions, no duplicate rain sender, calendar routine uses calendar, cancellation affects recurring message reminders.
- [ ] Confirm stop/pause persists after service restart and no send occurs from a cancelled schedule snapshot.
- [ ] Replace static capability claims with actual implementation, connection and verification status.
- [ ] Add task receipts that distinguish queued, proposed, approved, executed, provider accepted, delivered and failed.
- [ ] Remove unnecessary reminder approvals; verify new conversations and stored old approval language do not recreate them.
- [ ] Check duplicate calendar entries and preserve genuine appointments while removing confirmed duplicates.

## P1 — daily use and WebUI

- [ ] Deploy compact weather: temperature, feels-like, day range/rain chance, AQI, measured warnings, timestamp.
- [ ] Deploy sourced briefing with separate city-matching local, India and world news, calendar and article buttons.
- [ ] Add visible recurring schedule controls; pause/delete and cancel-all reminders must produce real counts.
- [ ] Add Connections: Google scopes, test/reconnect/disconnect, Telegram, MCP and WhatsApp state.
- [ ] Finish session renewal, app cookie persistence and proof-bound external Google login return. Test replay, wrong nonce/audience, disabled accounts and sign-out.
- [ ] Verify passkeys on two devices; synced credentials depend on the user's password manager. Add visible pairing without duplicate HTML IDs.
- [ ] Test camera, vision and gesture separately on the actual phone; display specific model/permission failures.
- [ ] Show actionable failures and readable mobile navigation; retain existing scene.

## P1 — real execution

- [ ] Implement missing AgentHub module, owner-scoped pairing, single device registry, revocable abilities and persistent jobs/receipts.
- [ ] Choose target device for phone/laptop actions; verify execution instead of saying sent means done.
- [ ] Finish Gmail/Calendar real API actions and mock error/receipt tests; connect owner's Google services and run consented end-to-end checks.
- [ ] Music player: client plays audible media; server stores queue/control state. Current YouTube search link is not playback.
- [ ] Phone SMS/dialer draft: explicit compose/dial actions. Background SIM SMS requires companion permissions and device testing; not implemented.

## Owner-dependent connections

- [ ] New Atulya WhatsApp Business account: Meta setup, number, credentials, webhook and shared identity. No active connection yet.
- [ ] Connect actual Gmail/Calendar scopes and activate APIs. Google sign-in is separate.
- [ ] Test owner's real MCP endpoint; add authenticated integrations where needed.
- [ ] Install updated signed APK and verify physical device behavior.

## Later implementation

- [ ] Real document encoders/readers/upload/edit UI and scoped file access.
- [ ] Generic durable workflows with actual action executor/checkpoints.
- [ ] Broader proactive diagnosis with tested repair proposals and rollback, retaining protected core/setup boundaries.
- [ ] Native reliable reminders, delivery receipts and configurable quiet hours.

## Backup and synchronization

- [x] Downloaded private 2.7 GB project archive and matched server SHA-256. Do not commit private data or restore Linux virtualenv over Windows.
- [ ] Test, review, merge and deploy local drafts; verify main/server commit match.
- [ ] Keep assistant development branches separate and preserve other contributors' changes.

The old list incorrectly described laptop agents and Gmail/Calendar as done, claimed gesture assets were missing, and treated a 40-word/one-headline briefing as finished. None of those statements should be reused as verification.

## Local implementation evidence from this pass

- Scheduling controls, bulk reminder cancellation, compact weather, sourced category briefings and receipt checks implemented locally; 11 focused regressions passed.
- Device backend, isolated per-device credentials, durable jobs and outbound laptop companion implemented; isolation/no-replay/folder-boundary tests passed. No actual laptop paired yet.
- Google app return and explicit Gmail/Calendar connection drafted with security tests; nonce/consent/replay tests passed. Real owner OAuth remains required.
- Music queue/player and phone composer/dialer request UI implemented locally. Physical Android and playback verification pending.
- These entries do not mean deployed or verified on the owner's phone. Update each corresponding checkbox only when its stated verification is complete.
