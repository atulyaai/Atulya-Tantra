import asyncio

import pytest

from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import TOOLS, Toolbox, TOOLS_BY_NAME

PC_TOOLS = {t.name for t in TOOLS if t.plugin_id == "pc-control"}


def ctx(user_id, is_admin):
    return PluginContext("owner", None, None, user_id, is_admin=is_admin)


def test_normal_user_gets_no_pc_or_smart_home_tools():
    names = {schema["function"]["name"] for schema in Toolbox(TOOLS, ctx("u2", False)).schemas}
    assert PC_TOOLS and not (names & PC_TOOLS)
    assert "smart_home_control" not in names


@pytest.mark.skipif(__import__("os").name != "nt", reason="pc-control is only offered on a desktop host")
def test_owner_keeps_pc_and_smart_home_tools():
    names = {schema["function"]["name"] for schema in Toolbox(TOOLS, ctx("owner-id", True)).schemas}
    assert {"search_files", "read_document", "smart_home_control"} <= names


@pytest.mark.parametrize("name", sorted(PC_TOOLS | {"smart_home_control"}))
def test_direct_call_by_normal_user_is_refused(name):
    reply = asyncio.run(TOOLS_BY_NAME[name].handler({"query": "x", "name": "x", "url": "https://x", "path": "x",
                                                     "command": "play", "target": "lights", "action": "on"},
                                                    ctx("u2", False)))
    assert "Only the owner" in reply


def test_second_admin_is_treated_as_owner():
    from tools.plugins.toolkit import _is_admin
    assert _is_admin(ctx("someone-else", True))
    assert not _is_admin(ctx("admin", False))
    assert not _is_admin(PluginContext("owner", None, None, "admin"))  # fail closed: the literal id grants nothing (S2)
