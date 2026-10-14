"""Request-scoped capability views derived from the executable tool registry.

Available means callable, never deployed, delivered, or device verified.
"""
from __future__ import annotations

MCP_PUBLIC_TOOLS = frozenset({"get_weather", "get_news", "get_time", "calculate", "what_can_you_do"})


def tool_capabilities(toolbox):
    from tools.plugins.toolkit import TOOLS
    ctx = toolbox.context
    channel = getattr(ctx, "channel", "mcp" if toolbox.public_only else "web")
    rows = []
    for tool in TOOLS:
        status, step = "available", "Call the tool; inspect its execution receipt before claiming success."
        if tool.plugin_id not in toolbox.enabled_plugins:
            status, step = "disabled", "Enable the plugin in Connections."
        elif toolbox.public_only and tool.name not in MCP_PUBLIC_TOOLS:
            status, step = "unsupported", "Use an authenticated Atulya channel; this tool is not exported over public MCP."
        elif tool.name == "restart_service":
            status, step = "unsupported", "Service restart execution is not implemented."
        elif tool.name not in toolbox._tools:
            status, step = "needs_connection", "Connect the required service or use a supported signed-in channel."
            if tool.plugin_id == "pc-control" or tool.name == "screen_control":
                status, step = "unsupported", "Use a supported desktop/WebUI session."
            elif tool.name.startswith("maintenance_") or tool.name.startswith("mcp_"):
                step = "Use an owner session with this service connected."
            elif "reminder" in tool.name:
                step = "Connect a reminder store for this channel."
        elif tool.needs_context and ctx is None:
            status, step = "needs_connection", "Sign in to Atulya."
        elif tool.confirm and not (tool.low_risk and toolbox._safety() == "ask_risky"):
            status, step = "needs_approval", "Approve the queued action before it can execute."
            if getattr(ctx, "actions", None) is None:
                step = "Use the signed-in WebUI approval queue to run this action."
        dependency = {"personal-memory": "memory", "productivity-calendar": "calendar"}.get(tool.plugin_id)
        dependency = {"search_past_chats": "history", "update_profile": "profile", "save_place": "profile"}.get(tool.name, dependency)
        if status in {"available", "needs_approval"} and dependency and getattr(ctx, dependency, None) is None:
            status, step = "needs_connection", f"Connect the {dependency} store for this signed-in session."
        if status == "available" and tool.name in {"get_weather", "where_am_i", "places_near_me", "save_place"}:
            profile = getattr(ctx, "profile", None)
            if profile is None or not profile.location(ctx.user_id):
                status, step = "needs_location", "Share device location or supply a named place where supported."
        if tool.name.startswith(("gmail_", "calendar_")) and status in {"available", "needs_approval"}:
            from tools.plugins.information.google_api import connection_status
            try:
                connection = connection_status(ctx.user_id)
            except (OSError, ValueError):
                connection = {}
            scope = "gmail_send" if tool.name == "gmail_send" else "gmail_read" if tool.name.startswith("gmail_") else "calendar_write"
            if not all(connection.get(key) for key in ("configured", "connected", scope)) or connection.get("last_error"):
                status, step = "needs_connection", "Connect or reconnect Google with the required Gmail/Calendar scope in Connections."
        rows.append({"id": tool.name, "name": tool.name, "plugin_id": tool.plugin_id,
                     "description": tool.description, "channel": channel, "status": status,
                     "next_step": step, "verification": "Not established by this registry."})
    return rows


def format_capabilities(rows, channel):
    lines = [f"What I can do on {channel} (runtime readiness, not execution verification):"]
    for row in rows:
        lines.append(f"{row['name']}: {row['status']} — {row['next_step']}")
    return "\n".join(lines)


def catalogue_for_channel(channel="mcp"):
    # Without an authenticated request, only advertise the public MCP surface.
    from tools.plugins.toolkit import Toolbox, TOOLS
    box = Toolbox(TOOLS, public_only=True)
    return format_capabilities(box.capabilities, "mcp")
