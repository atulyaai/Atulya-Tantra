"""Turn what Atulya knows about a user into a tree the web app can draw.

The trunk is the user. Each kind of memory (people, places, work, likes, health, dates, habits, notes) is a branch;
each fact or habit is a leaf. Nothing here is invented: every leaf is a stored fact.
"""
from __future__ import annotations

from typing import Any

BRANCHES = [
    ("person", "People"),
    ("place", "Places"),
    ("work", "Work"),
    ("preference", "Likes & dislikes"),
    ("health", "Health"),
    ("date", "Dates"),
    ("habit", "Habits"),
    ("note", "Notes"),
]
_LABELS = dict(BRANCHES)


def build_memory_graph(view: dict[str, Any], topics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """``view`` is ``ProfileStore.view()``; ``topics`` are MemoryTree L1 summaries (optional)."""
    nodes: list[dict[str, Any]] = [{"id": "root", "label": view.get("user") or "You", "group": "root", "kind": "root"}]
    edges: list[dict[str, str]] = []
    leaves: dict[str, list[dict[str, Any]]] = {kind: [] for kind, _ in BRANCHES}

    for fact in view.get("facts") or []:
        kind = fact.get("kind") if fact.get("kind") in leaves else "note"
        leaves[kind].append({"id": f"fact:{fact.get('id', len(nodes))}", "label": str(fact.get("value") or fact.get("text") or ""),
                             "detail": str(fact.get("text") or ""), "key": fact.get("key", "")})
    for habit in view.get("habits") or []:
        leaves["habit"].append({"id": f"habit:{habit.get('signature')}", "label": str(habit.get("label") or ""),
                                "detail": f"{habit.get('label')} {habit.get('when', '')}".strip(), "key": "habit"})
    for topic in topics or []:
        leaves["note"].append({"id": f"topic:{topic.get('topic')}", "label": str(topic.get("topic") or ""),
                               "detail": str(topic.get("summary") or "")[:200], "key": "topic"})

    for kind, label in BRANCHES:
        if not leaves[kind]:
            continue
        branch_id = f"branch:{kind}"
        nodes.append({"id": branch_id, "label": label, "group": kind, "kind": "branch", "count": len(leaves[kind])})
        edges.append({"from": "root", "to": branch_id})
        for leaf in leaves[kind]:
            nodes.append({**leaf, "group": kind, "kind": "leaf"})
            edges.append({"from": branch_id, "to": leaf["id"]})

    return {"nodes": nodes, "edges": edges, "total": sum(len(v) for v in leaves.values())}
