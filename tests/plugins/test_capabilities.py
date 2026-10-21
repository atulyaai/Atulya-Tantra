import asyncio
from dataclasses import replace

from tools.plugins.registry import PluginContext, build_default_registry
from tools.plugins.toolkit import TOOLS, Toolbox


def rows(box):
    return {row['name']: row for row in box.capabilities}


def test_registry_covers_tools_and_assistant_uses_same_status():
    box = Toolbox.for_registry(build_default_registry(), None)
    assert set(rows(box)) == {tool.name for tool in TOOLS}
    report = asyncio.run(box.call('what_can_you_do', {}))
    for row in box.capabilities:
        assert f"{row['name']}: {row['status']}" in report
        assert row['next_step']
    assert rows(box)['restart_service']['status'] == 'unsupported'


def test_plugin_toggle_and_public_mcp_boundaries():
    registry = build_default_registry()
    registry.set_enabled('online-information', False)
    assert rows(Toolbox.for_registry(registry, None))['get_weather']['status'] == 'disabled'
    box = Toolbox(TOOLS, public_only=True)
    assert rows(box)['remember_fact']['status'] == 'unsupported'
    assert rows(box)['calculate']['status'] == 'available'
    assert 'not available' in asyncio.run(box.call('remember_fact', {}))


def test_approval_location_google_and_missing_dependencies(monkeypatch):
    from tools.plugins.information import google_api
    monkeypatch.setattr(google_api, 'connection_status', lambda _: {})
    ctx = PluginContext('owner', None, None, 'person', is_admin=True)  # Gmail is admin-only (M12-2)
    state = rows(Toolbox(TOOLS, ctx))
    assert state['gmail_send']['status'] == 'needs_connection'
    assert state['get_weather']['status'] == 'needs_location'
    assert state['search_past_chats']['status'] == 'needs_connection'
    monkeypatch.setattr(google_api, 'connection_status', lambda _: {
        'configured': True, 'connected': True, 'gmail_send': True})
    assert rows(Toolbox(TOOLS, ctx))['gmail_send']['status'] == 'needs_approval'
    state = rows(Toolbox(TOOLS, replace(ctx, channel='telegram')))
    assert state['screen_control']['status'] == 'unsupported'
