# Atulya — working list (cleaned 2026-10-13)

Status: ✅ done · 🔧 in progress · ⬜ to do · ⛔ blocked on owner

## Done (live on server)

- Toolkit restored, tools load (42 tools)
- Voice commands: stop, repeat, mute, wake word toggle, barge-in
- Routines: weekday 08:00 briefing (now ~40 words), daily 07:30 rain check
- House watch: disk >90% → Telegram alert
- Laptop agent code (outbound, allowlist)
- Gmail/Calendar tools (need Google re-auth with scopes)
- Persona: short Jarvis style, time-aware greeting
- System panel admin-only
- Passkeys and gesture recognizer code present
- OpenRouter switched to free multimodal model (google/gemma-4-26b-a4b-it:free)

## Still needed for real Jarvis

| Priority | Item | Notes |
|----------|------|-------|
| P0 | Vision actually green | Free multimodal model set; camera permission still required in browser |
| P0 | Gesture model on disk | models/gesture/ missing |
| P1 | Unified activity log | Routines + Telegram + web write to same audit so “stop that” works across channels |
| P1 | Proactive watchers | Calendar reminder 15 min before, disk, rain, “check email and ask to clean” |
| P1 | Cross-channel identity | Telegram and web share one conversation/memory for admin |
| P2 | Always-on wake word | Local openWakeWord on phone |
| P2 | Laptop agent running | Start on PC with token from .env |
| P2 | Continuous memory | Stronger cross-session recall, don’t re-ask |
| P3 | WebUI polish | Settings placement, hide/show, dashboard options, less boxes more scene |
| P3 | Vision mood/reaction | Expression reading once camera is on |
| ⛔ | WhatsApp / APK push | Needs Meta / Firebase accounts |

## Cleanup done this pass

- Removed tools/plugins/_toolkit_b64_0.txt and _toolkit_part_a.py
- Switched ATULYA_OPENROUTER_MODEL to free multimodal
- Shortened morning briefing
- This TODO rewritten to match reality
