"""PLAN M12-2: dangerous tools are admin-only on every channel; the model never sees them for a normal user,
and the server refuses them again on call and on approval."""
import asyncio

import pytest

from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import ADMIN_ONLY_REPLY, TOOLS, ActionQueue, PendingAction, Toolbox

PC_CONTROL = {tool.name for tool in TOOLS if tool.plugin_id == "pc-control"}
EXPECTED_ADMIN_ONLY = PC_CONTROL | {
    "smart_home_control", "cast_to_tv", "visual_inspect",
    "restart_service", "server_status", "server_logs", "atulya_status",
    "maintenance_check", "maintenance_read", "maintenance_propose", "maintenance_search",
    "maintenance_patch", "maintenance_set_proactive", "mcp_list_connections", "mcp_call_tool",
    "gmail_search", "gmail_drafts", "gmail_send",
}


def test_admin_only_column_is_exact():
    assert {"open_app", "take_screenshot", "read_document"} <= PC_CONTROL
    assert {tool.name for tool in TOOLS if tool.admin_only} == EXPECTED_ADMIN_ONLY


def _context(is_admin, channel="web"):
    return PluginContext("web", object(), object(), "u-admin" if is_admin else "u2", actions=ActionQueue(".").view(),
                         reminders=object(), maintenance=object(), mcp_connections=object(), channel=channel,
                         is_admin=is_admin)


@pytest.mark.parametrize("channel", ["web", "telegram", "android"])
def test_normal_user_never_sees_admin_tools(channel, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    names = {schema["function"]["name"] for schema in Toolbox(TOOLS, _context(False, channel)).schemas}
    assert not names & EXPECTED_ADMIN_ONLY
    assert {"get_weather", "create_reminder"} <= names  # ordinary tools stay available


def test_admin_keeps_admin_tools(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    names = {schema["function"]["name"] for schema in Toolbox(TOOLS, _context(True)).schemas}
    assert {"server_logs", "gmail_send", "maintenance_check"} <= names


def test_call_and_approval_refused_even_if_a_tool_slips_in(monkeypatch):
    """Defence in depth: a Toolbox built for an admin then used with a user's context still refuses."""
    monkeypatch.setenv("DISPLAY", ":test")
    box = Toolbox(TOOLS, _context(True))
    box.context = _context(False)
    for name, args in (("cast_to_tv", {"tv": "TV", "url": "https://x.test"}),
                       ("server_logs", {"query": "error"}), ("gmail_send", {"to": "a@b.c", "subject": "s", "body": "b"})):
        assert asyncio.run(box.call(name, args)) == ADMIN_ONLY_REPLY
    action = PendingAction("x1", "visual_inspect", {"device": "Phone", "question": "?"}, "Take a photo", "u2")
    assert asyncio.run(box.run_approved(action)) == ADMIN_ONLY_REPLY


def test_users_control_their_own_devices_only(tmp_path, monkeypatch):
    """AUDIT S5: device tools are per owner (AgentHub scopes every job), so a normal user may use them."""
    from tools.plugins.system.agents import AgentHub

    monkeypatch.setenv("ATULYA_DATA_DIR", str(tmp_path))
    hub = AgentHub(tmp_path)
    hub.pair("u2", "Bob Phone", ["ping", "send_sms"])
    hub.pair("u-admin", "Owner Phone", ["ping", "send_sms"])
    queue = ActionQueue(tmp_path)
    context = PluginContext("web", object(), object(), "u2", actions=queue.view(), is_admin=False)
    box = Toolbox(TOOLS, context)
    assert "Queued job" in asyncio.run(box.call("ask_device", {"device": "Bob Phone", "command": "ping"}))
    assert "Approval requested" in asyncio.run(box.call("device_action", {"device": "Owner Phone",
                                                                          "command": "send_sms", "detail": "1|hi"}))
    [pending] = context.actions.created
    assert "not paired to you" in asyncio.run(box.run_approved(pending))  # someone else's device
    assert hub.jobs("u-admin") == [] and [job["kind"] for job in hub.jobs("u2")] == ["ping"]


def test_voice_subset_of_a_user_has_no_admin_tools(monkeypatch):
    from tools.plugins.toolkit import VOICE_TOOLS
    monkeypatch.setenv("DISPLAY", ":test")
    names = {schema["function"]["name"] for schema in Toolbox(TOOLS, _context(False)).subset(VOICE_TOOLS).schemas}
    assert not names & EXPECTED_ADMIN_ONLY and "open_app" not in names and "read_document" not in names
