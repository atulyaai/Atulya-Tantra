"""Who may call each API route (PLAN M12-1). Every route in the app must be listed here:
tests/core/test_route_access.py fails on an unlisted route, and SessionAuthMiddleware answers
403 for an "admin" route before the handler (or body validation) runs. Handlers keep their own
checks as a second layer.

  public  no session needed (sign-in, health, app update metadata)
  device  authenticated by a paired device token in the request (agent poll/result)
  user    any signed-in account; data is scoped to that account inside the handler
  admin   the owner/administrator role only
"""
from __future__ import annotations

import re

ROUTE_ACCESS: dict[tuple[str, str], str] = {
    # public
    ("GET", "/api/health"): "public",
    ("GET", "/api/auth/status"): "public",
    ("POST", "/api/auth/register/options"): "public",
    ("POST", "/api/auth/register/verify"): "public",
    ("POST", "/api/auth/login/options"): "public",
    ("POST", "/api/auth/login/verify"): "public",
    ("POST", "/api/auth/login-requests"): "public",
    ("GET", "/api/auth/login-requests/{request_id}"): "public",
    ("POST", "/api/auth/login-requests/{request_id}/code"): "public",
    ("POST", "/api/auth/login-requests/{request_id}/voice"): "public",
    ("POST", "/api/auth/voice-unlock"): "public",
    ("GET", "/api/app/latest"): "public",
    ("GET", "/api/push/key"): "public",
    ("GET", "/api/auth/options"): "public",
    ("POST", "/api/auth/signup"): "public",
    ("GET", "/api/auth/google/start"): "public",
    ("GET", "/api/auth/google/callback"): "public",
    ("GET", "/api/auth/google/finish"): "public",
    ("POST", "/api/auth/google/app"): "public",
    ("POST", "/api/auth/telegram-webapp"): "public",
    ("POST", "/api/auth/password"): "public",
    ("POST", "/api/auth/logout"): "public",
    ("GET", "/openapi.json"): "public",
    ("GET", "/download"): "public",
    # device
    ("POST", "/api/agents/register"): "device",
    ("POST", "/api/agents/poll"): "device",
    ("POST", "/api/agents/result"): "device",
    # admin
    ("GET", "/api/maintenance"): "admin",
    ("PUT", "/api/maintenance/proactive"): "admin",
    ("POST", "/api/maintenance/check"): "admin",
    ("GET", "/api/maintenance/file"): "admin",
    ("POST", "/api/maintenance/proposals"): "admin",
    ("POST", "/api/maintenance/proposals/{proposal_id}/{action}"): "admin",
    ("POST", "/api/mcp/connections"): "admin",
    ("POST", "/api/mcp/connections/{connection_id}/test"): "admin",
    ("POST", "/api/mcp/connections/{connection_id}/grant"): "admin",
    ("DELETE", "/api/mcp/connections/{connection_id}"): "admin",
    ("GET", "/api/automations"): "admin",
    ("PUT", "/api/automations/{routine_id}"): "admin",
    ("DELETE", "/api/automations/{routine_id}"): "admin",
    ("POST", "/api/reminders/cancel-all"): "admin",
    ("GET", "/api/auth/signups"): "admin",
    ("POST", "/api/auth/signups/{user_id}"): "admin",
    ("GET", "/api/auth/users"): "admin",
    ("POST", "/api/auth/users"): "admin",
    ("DELETE", "/api/auth/users/{user_id}"): "admin",
    ("DELETE", "/api/auth/credentials/{credential_id}"): "admin",
    ("GET", "/api/connections"): "admin",
    ("POST", "/api/plugins/{plugin_id}"): "admin",
    ("GET", "/api/reminders/telegram"): "admin",
    ("GET", "/api/notifications"): "admin",
    ("GET", "/api/activity"): "admin",
    ("POST", "/api/smarthome/scene"): "admin",
    ("PUT", "/api/auth/users/{user_id}/content"): "admin",
    ("PUT", "/api/auth/users/{user_id}/limits"): "admin",
    ("GET", "/api/content-events"): "admin",
    ("GET", "/api/security-log"): "admin",
    # user (scoped to request.state.user_id inside each handler)
    ("GET", "/api/reminders"): "user",
    ("POST", "/api/reminders"): "user",
    ("POST", "/api/reminders/{reminder_id}/shown"): "user",
    ("PUT", "/api/reminders/{reminder_id}"): "user",
    ("DELETE", "/api/reminders/{reminder_id}"): "user",
    ("GET", "/api/readiness"): "user",
    ("GET", "/api/devices"): "user",
    ("POST", "/api/devices/pair"): "user",
    ("DELETE", "/api/devices/{name}"): "user",
    ("POST", "/api/devices/{name}/test"): "user",
    ("POST", "/api/music/search"): "user",
    ("GET", "/api/music"): "user",
    ("POST", "/api/music"): "user",
    ("POST", "/api/music/{track_id}/receipt"): "user",
    ("GET", "/api/phone/actions"): "user",
    ("POST", "/api/phone/actions/{request_id}/receipt"): "user",
    ("GET", "/api/weather"): "user",
    ("POST", "/api/auth/device-link"): "user",
    ("POST", "/api/auth/voice-unlock/enroll"): "user",
    ("DELETE", "/api/auth/voice-unlock/enroll"): "user",
    ("POST", "/api/push/subscribe"): "user",
    ("GET", "/api/google/status"): "user",
    ("POST", "/api/google/test"): "user",
    ("DELETE", "/api/google/connection"): "user",
    ("GET", "/api/auth/pending-logins"): "user",
    ("POST", "/api/auth/pending-logins/{request_id}"): "user",
    ("GET", "/api/plugins"): "user",
    ("GET", "/api/capabilities"): "user",
    ("POST", "/api/voice/synthesize"): "user",
    ("POST", "/api/voice/transcribe"): "user",
    ("GET", "/api/models/gesture/gesture_recognizer.task"): "user",
    ("GET", "/api/status"): "user",
    ("GET", "/api/memory"): "user",
    ("POST", "/api/memory"): "user",
    ("DELETE", "/api/memory"): "user",
    ("GET", "/api/calendar"): "user",
    ("POST", "/api/calendar"): "user",
    ("DELETE", "/api/calendar/{event_id}"): "user",
    ("GET", "/api/expenses"): "user",
    ("POST", "/api/expenses"): "user",
    ("POST", "/api/expenses/parse-sms"): "user",
    ("GET", "/api/events"): "user",
    ("GET", "/api/conversations"): "user",
    ("GET", "/api/conversations/{conversation_id}"): "user",
    ("DELETE", "/api/conversations/{conversation_id}"): "user",
    ("POST", "/api/conversations/{conversation_id}/messages"): "user",
    ("POST", "/api/chat"): "user",
    ("GET", "/api/profile"): "user",
    ("PUT", "/api/profile"): "user",
    ("GET", "/api/profile/content"): "user",
    ("PUT", "/api/profile/birth-date"): "user",
    ("PUT", "/api/profile/adult-content"): "user",
    ("POST", "/api/location"): "user",
    ("POST", "/api/briefing"): "user",
    ("POST", "/api/actions/{action_id}"): "user",
}


def _pattern(template: str) -> re.Pattern:
    return re.compile("^" + re.sub(r"\\\{[^/]+?\\\}", r"[^/]+", re.escape(template)) + "$")


_ADMIN = [(method, _pattern(path)) for (method, path), access in ROUTE_ACCESS.items() if access == "admin"]


def is_admin_route(method: str, path: str) -> bool:
    method = "GET" if method.upper() == "HEAD" else method.upper()
    return any(method == m and pattern.match(path) for m, pattern in _ADMIN)
