# Feature audit — 14 October 2026

This is a source audit and the last recorded verification, not a claim that every feature works on the owner's phone. Catalogues and tool names are not execution evidence.

| Feature | Evidence / current gap | Next verification |
| --- | --- | --- |
| Chat, calculation, weather, saved memory | Earlier real server checks passed | Repeat after the current changes deploy |
| Server speech recognition and synthesis | Earlier real audio round trip passed | Check the installed phone app separately |
| Telegram reminders | One real test was accepted by Telegram and reached the phone silently | Android sound/vibration and reliable native alerts remain to verify |
| Reminder and meeting editing/cancellation | Implemented and covered by targeted tests | Verify final deployed version |
| Browser navigation | PR #86 preserves popup WebViews and POST requests | Verify installed APK version and app update |
| Google sign-in persistence | Thirty-day sessions, cookie persistence and proof-bound app return are local drafts | OAuth replay, identity, expiry and real app return tests required |
| Cross-device passkeys | Existing server registration and device-link flow; visible button added locally | Test on two devices; password-manager sync is controlled by its provider |
| Gmail read/search | Depends on account-specific Google OAuth and Gmail API activation | Connect and test the actual account |
| Gmail send / Google Calendar create | Previous handlers were placeholders; real API calls are now local drafts | Test permissions and API receipts; no test email has been sent |
| Camera/gesture | Runtime assets and lifecycle fixes were made | Actual recognition on the owner's phone is unverified |
| MCP | Owner grants and discovery implemented; initial endpoints lack OAuth support | Test the owner's real endpoint |
| Phone music | Local private queue and embedded YouTube player added; browser playback still needs verification | Real playback, target device and playback receipts missing |
| Phone SMS/calls | Composer/dialer bridge drafted locally | Local server request queue and native composer/dialer receipts implemented; no automatic SIM send or background executor |
| WhatsApp Business | No active Atulya business connection | Meta account, number, credentials, webhook and shared identity required |
| Laptop/phone agents | Previously missing backend is now implemented locally | Local owner-scoped AgentHub and laptop companion implemented; pairing/revocation/no-replay tests passed, target laptop not connected |
| Device listing | Local fix uses one owner-scoped AgentHub and removes duplicate handler | Use one owner-scoped source of device state |
| Service restart | Merged/deployed PR #88 fix explicitly reports unavailable and creates no fictional approval | Report unsupported rather than suggesting an approval will execute it |
| Document creation prototype | Merged/deployed PR #88 fix rejects creation without a real encoder and writes no fake files | Implement real formats or explicitly report unavailable |
| Generic workflow prototype | Merged/deployed PR #88 fix fails unimplemented actions without advancing steps; rain check remains unimplemented | Distinguish this from the separate time-of-day routine scheduler |
| Capability catalogue | Static status entries can contradict implementation and current tests | Show implementation, connection and verification status separately |
| Full server backup | Private full project archive downloaded; SHA-256 matches server ce3610306a57f54f699602ff048674eae50f0506e6bc46e8a70c36eee2b15f80 | Verify archive, transfer, checksum and database snapshots |

Every action should distinguish proposed, approved, queued, executed, accepted by provider, delivered and failed. A queued job is not execution; an API acceptance is not recipient delivery; a syntax check is not a device test.

Local receipt regression checks: three tests passed for invalid documents, unexecuted workflows and unavailable service restart. Five OAuth/session/redaction checks also passed. These local tests do not verify deployment or phone behavior.

14 October investigation: Reminder #2 was cancelled and never delivered. Separate daily Surah Yaseen routine fired today and was still enabled; disabled live with a backup. Morning/rain scheduler duplication and calendar-to-briefing fallthrough fixed locally. Stored chat showed fictional approvals, server-versus-phone confusion, Gmail 403 and duplicate calendar entries. No new Telegram test messages were sent.
