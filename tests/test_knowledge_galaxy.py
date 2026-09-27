"""Knowledge galaxy: the user's facts, topics, memories and skills as a star map."""
from __future__ import annotations

from drishti.dashboard.routes.knowledge import build_galaxy


def _galaxy(memories=None):
    return build_galaxy(
        {"username": "atul", "role": "admin"},
        {"facts": [{"id": "f1", "text": "Your wife is Priya", "kind": "relation"}],
         "habits": [{"text": "lights off around 11pm"}],
         "approvals": [{"key": "home_control:off", "trusted": True}]},
        [{"role": "user", "text": "turn off the bedroom lights"}, {"role": "user", "text": "lights on please"},
         {"role": "assistant", "text": "ignored assistant words"}],
        memories or [],
        [{"name": "web_search", "description": "Search the web"}],
    )


def test_every_constellation_hangs_off_the_user_or_atulya():
    g = _galaxy()
    ids = {n["id"] for n in g["nodes"]}
    assert {"you", "atulya", "fact:f1", "habit:0", "trust:home_control:off", "skill:web_search"} <= ids
    assert all(l["source"] in ids and l["target"] in ids for l in g["links"])
    assert {c["id"] for c in g["clusters"]} >= {"you", "about", "habit", "trust", "topic", "skill"}


def test_topics_come_from_what_the_user_says_not_atulya():
    g = _galaxy()
    topics = {n["label"]: n for n in g["nodes"] if n["group"] == "topic"}
    assert topics["lights"]["meta"]["mentions"] == 2
    assert "ignored" not in topics and "please" not in topics


def test_repeated_memories_collapse_and_link_to_topics():
    mems = [{"id": f"v{i}", "content": "Q: lights schedule\nA: 11pm"} for i in range(3)]
    g = _galaxy(mems)
    memory_nodes = [n for n in g["nodes"] if n["group"] == "memory"]
    assert len(memory_nodes) == 1 and memory_nodes[0]["label"] == "lights schedule"
    assert {"source": memory_nodes[0]["id"], "target": "topic:lights"} in g["links"]
