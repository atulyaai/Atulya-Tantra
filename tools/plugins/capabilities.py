"""Capability catalogue: one registry the AI, UI and MCP all read.

Every capability has a status (available / needs_location / needs_connection /
needs_approval / unsupported) and a list of channels it works on. The model
reads this to answer "what can you do here?" honestly, and the MCP server
exposes the same registry so outside AI apps see the same truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field


STATUS_AVAILABLE = "available"
STATUS_NEEDS_LOCATION = "needs_location"
STATUS_NEEDS_CONNECTION = "needs_connection"
STATUS_NEEDS_APPROVAL = "needs_approval"
STATUS_UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class Capability:
    id: str
    name: str
    description: str
    status: str
    channels: frozenset[str] = field(default_factory=frozenset)
    next_step: str = ""  # what the user can do to enable it


# Channel constants
WEB = "web"
TELEGRAM = "telegram"
MCP = "mcp"
ANDROID = "android"

ALL_CHANNELS = frozenset({WEB, TELEGRAM, MCP, ANDROID})


CAPABILITIES: tuple[Capability, ...] = (
    # --- Platform and safety ---
    Capability("PLT-01", "Shared tool registry", "One tool set used by web, Telegram, Android and MCP",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("PLT-02", "Capability catalogue", "The AI can read what it can and cannot do, per channel",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("PLT-03", "Honest status", "Every tool reports available / needs location / needs approval / unsupported",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("PLT-04", "Approval queue", "Side-effecting actions wait for user approval",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("PLT-05", "Identity", "Passkeys, password, Telegram codes — one account everywhere",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("PLT-06", "Per-device permissions", "Control which devices can do what",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H5"),
    Capability("PLT-07", "Audit log", "Every tool run recorded with who, what, result",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H3"),
    Capability("PLT-08", "Encrypted secrets", "API keys encrypted at rest, logs redacted",
               STATUS_AVAILABLE, frozenset({WEB})),
    Capability("PLT-09", "Durable jobs", "Reminders and briefings survive restarts",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM})),
    Capability("PLT-10", "Progress and cancel", "Long tasks show progress and can be cancelled",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H8"),

    # --- Information and location ---
    Capability("LOC-01", "Current weather", "Named place or device location",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("LOC-02", "Forecast", "Next hours / today / tomorrow / 7-day",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("LOC-03", "Where am I", "Address from device location with consent",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("LOC-04", "Device location", "Web/app geolocation, Telegram share button",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("LOC-05", "Saved home city", "Fallback when no device location",
               STATUS_AVAILABLE, ALL_CHANNELS),
    Capability("LOC-06", "Places and routes", "Nearby places, routes, travel time (OSRM)",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H4"),
    Capability("LOC-07", "Severe-weather alerts", "Push alerts for rain, storms",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H8"),
    Capability("RES-01", "Web search", "Search with sources",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H4"),
    Capability("RES-02", "Read web pages", "Fetch and summarize any URL",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H4"),
    Capability("RES-03", "News headlines", "BBC News headlines",
               STATUS_AVAILABLE, ALL_CHANNELS),

    # --- Memory and personal ---
    Capability("MEM-01", "Remember facts", "Save and recall facts the user tells you",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("MEM-02", "Preferences", "Name, language, tone, voice, short/detailed",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("MEM-03", "Search past chats", "Search earlier conversations",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("MEM-04", "Short or detailed", "Ask when unclear; default short",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM, ANDROID})),
    Capability("MEM-05", "Project memory", "Status, blockers, next step per project",
               STATUS_UNSUPPORTED, frozenset(), "Coming later"),

    # --- Files and documents ---
    Capability("FIL-01", "Find files", "Search files by name on this PC",
               STATUS_AVAILABLE, frozenset({WEB})),
    Capability("FIL-02", "Read documents", "PDF, DOCX, XLSX, CSV, code",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H6"),
    Capability("FIL-03", "Upload in chat", "Send a file in any chat and ask about it",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H6"),
    Capability("FIL-04", "Edit files safely", "Preview diff, save as new copy, approval",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H7"),
    Capability("FIL-05", "Create documents", "Word, Excel, PDF, PowerPoint",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H7"),
    Capability("FIL-06", "Laptop files from anywhere", "Paired agent, approved folders",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H6"),
    Capability("FIL-07", "Phone files", "Android document picker",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H6"),

    # --- Devices and server ---
    Capability("DEV-01", "PC control", "Open apps/URLs, media keys, screenshot (approval)",
               STATUS_AVAILABLE, frozenset({WEB})),
    Capability("DEV-02", "Device registry", "List devices with status and granted abilities",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H5"),
    Capability("DEV-03", "Server health", "CPU/RAM/disk/services (read-only SSH)",
               STATUS_AVAILABLE, frozenset({WEB})),
    Capability("DEV-04", "Server logs", "Explain errors, restart with approval",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H5"),
    Capability("DEV-05", "Deploy", "GitHub Actions deploy with rollback",
               STATUS_AVAILABLE, frozenset({WEB})),

    # --- Communication ---
    Capability("COM-01", "Telegram", "Chat, voice notes, approvals, reminders",
               STATUS_AVAILABLE, frozenset({TELEGRAM})),
    Capability("COM-02", "Gmail", "Search, summarize, draft (send with approval)",
               STATUS_UNSUPPORTED, frozenset(), "Needs Google OAuth (D1) → H9"),
    Capability("COM-03", "Google Calendar", "Search, create, update",
               STATUS_UNSUPPORTED, frozenset(), "Needs Google OAuth (D1) → H9"),
    Capability("COM-04", "GitHub", "Repos, issues, PRs, CI status",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H9"),
    Capability("COM-05", "WhatsApp", "Chat via WhatsApp",
               STATUS_UNSUPPORTED, frozenset(), "Needs Meta Business account (C5)"),

    # --- Automation ---
    Capability("AUT-01", "Reminders", "One-time reminders",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM})),
    Capability("AUT-02", "Morning briefing", "Daily weather + calendar + news",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM})),
    Capability("AUT-03", "Recurring routines", "Every weekday 9am …",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H8"),
    Capability("AUT-04", "Condition alerts", "Rain, disk full, site down",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H8"),
    Capability("AUT-05", "Multi-step workflows", "Checkpoints that survive restarts",
               STATUS_UNSUPPORTED, frozenset(), "Coming in H8"),

    # --- Interop ---
    Capability("ECO-01", "MCP server", "Expose tools to outside AI apps",
               STATUS_AVAILABLE, frozenset({MCP})),
    Capability("ECO-02", "Outside MCP servers", "Use external MCP servers as tools",
               STATUS_UNSUPPORTED, frozenset(), "Coming later"),
    Capability("ECO-03", "Skills", "Multi-step recipes that call tools",
               STATUS_AVAILABLE, frozenset({WEB, TELEGRAM})),
)


def catalogue_for_channel(channel: str) -> str:
    """Return the capability catalogue as text for a specific channel.

    The model calls this to answer "what can you do here?" honestly.
    Shows all capabilities: available ones first, then unavailable ones with
    what's needed to enable them.
    """
    available = []
    unavailable = []
    for cap in CAPABILITIES:
        entry = (cap, channel in cap.channels)
        if entry[1] and cap.status == STATUS_AVAILABLE:
            available.append(entry)
        else:
            unavailable.append(entry)

    lines = [f"What I can do on {channel}:"]
    for cap, _ in available:
        lines.append(f"  ✅ {cap.name} — {cap.description}")
    if unavailable:
        lines.append(f"\nNot available on {channel}:")
        for cap, on_channel in unavailable:
            if on_channel:
                status_icon = {
                    STATUS_NEEDS_LOCATION: "📍",
                    STATUS_NEEDS_CONNECTION: "🔌",
                    STATUS_NEEDS_APPROVAL: "✋",
                }.get(cap.status, "⬜")
                lines.append(f"  {status_icon} {cap.name} — {cap.description}")
            else:
                lines.append(f"  ⬜ {cap.name} — {cap.description} (not on {channel})")
            if cap.next_step:
                lines.append(f"     → {cap.next_step}")
    return "\n".join(lines)


def all_capabilities() -> list[dict]:
    """Return the full catalogue as a list of dicts (for API/MCP exposure)."""
    return [
        {
            "id": cap.id,
            "name": cap.name,
            "description": cap.description,
            "status": cap.status,
            "channels": sorted(cap.channels),
            "next_step": cap.next_step,
        }
        for cap in CAPABILITIES
    ]


def capability_by_id(cap_id: str) -> Capability | None:
    """Look up a capability by its ID."""
    for cap in CAPABILITIES:
        if cap.id == cap_id:
            return cap
    return None
