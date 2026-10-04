"""Turn what Atulya knows into a tree the web app can draw (and click into).

The trunk is the user. Each *kind of memory* is a branch; each stored fact, remembered exchange, skill or
module is a leaf. Nothing is invented: every leaf comes from a real source (profile facts, chat history, the
tool registry, mood, the code modules). Sections with nothing in them are left out.
"""
from __future__ import annotations

from typing import Any

# id, label, words that mean this branch when spoken ("open episodic memories")
BRANCHES = [
    ("personal", "Personal history", ("personal history", "history", "personal")),
    ("concepts", "Concepts & entities", ("concepts", "entities", "people", "relations")),
    ("preference", "User preferences", ("preferences", "likes", "dislikes")),
    ("episodic", "Episodic memories", ("episodic", "episodes", "conversations", "chats")),
    ("skills", "Skills & capabilities", ("skills", "capabilities", "tools", "abilities")),
    ("self", "Self-awareness", ("self awareness", "self-awareness", "myself", "mood")),
    ("arch", "Cognitive architecture", ("architecture", "cognitive", "modules")),
    ("world", "World knowledge", ("world knowledge", "world", "knowledge", "topics")),
]
SECTIONS = [{"id": b, "label": label, "words": list(words)} for b, label, words in BRANCHES]

_PERSONAL_KINDS = {"place", "work", "date", "health", "note"}
_ENTITY_KINDS = {"person"}

MODULES = [
    ("kernel", "Cognitive kernel: routes every request"),
    ("planner", "Planner: turns a request into steps"),
    ("safety", "Safety: risky actions ask first"),
    ("triggers", "Triggers: reacts to events on its own"),
    ("memory", "Memory: profile, vectors, summaries"),
    ("senses", "Senses: camera, motion, home sensors"),
    ("router", "Brain router: fastest working brain first"),
]


def build_memory_graph(
    view: dict[str, Any],
    topics: list[dict[str, Any]] | None = None,
    *,
    episodes: list[dict[str, Any]] | None = None,
    skills: list[tuple[str, str]] | None = None,
    mood: dict[str, Any] | None = None,
    brains: list[dict[str, Any]] | None = None,
    vectors: int = 0,
) -> dict[str, Any]:
    """``view`` is ``ProfileStore.view()``; the rest are optional extra sources."""
    user = view.get("user") or "You"
    leaves: dict[str, list[dict[str, Any]]] = {b: [] for b, _, _ in BRANCHES}
    relations: list[dict[str, str]] = []
    prefs: list[str] = []

    for fact in view.get("facts") or []:
        kind, value, text = fact.get("kind"), str(fact.get("value") or ""), str(fact.get("text") or "")
        leaf = {"id": f"fact:{fact.get('id', len(relations))}", "label": value or text, "detail": text, "key": fact.get("key", "")}
        if kind in _ENTITY_KINDS:
            leaves["concepts"].append(leaf)
            relations.append({"a": user, "rel": str(fact.get("key") or "knows"), "b": value})
        elif kind == "preference":
            leaves["preference"].append(leaf)
            prefs.append(f"{fact.get('key', '')}: {value}")
        elif kind in _PERSONAL_KINDS or kind:
            leaves["personal"].append(leaf)
        else:
            leaves["personal"].append(leaf)
    for habit in view.get("habits") or []:
        leaves["personal"].append({"id": f"habit:{habit.get('signature')}", "label": str(habit.get("label") or ""),
                                   "detail": f"{habit.get('label')} {habit.get('when', '')}".strip(), "key": "habit"})
    for i, ep in enumerate(episodes or []):
        text = str(ep.get("text") or ep.get("content") or "").strip()
        if text:
            leaves["episodic"].append({"id": f"ep:{i}", "label": text[:48], "detail": text[:400], "time": ep.get("created_at", "")})
    for name, desc in skills or []:
        leaves["skills"].append({"id": f"skill:{name}", "label": name.replace("_", " "), "detail": desc})
    for k, v in (mood or {}).items():
        leaves["self"].append({"id": f"self:{k}", "label": f"{k}: {v}", "detail": f"Atulya's {k} is {v}"})
    for b in brains or []:
        leaves["self"].append({"id": f"brain:{b['name']}", "label": f"brain: {b['name']}",
                               "detail": f"{b['name']} answers in about {b['seconds']}s" if b.get("seconds") else f"{b['name']} is ready"})
    for name, desc in MODULES:
        leaves["arch"].append({"id": f"mod:{name}", "label": name, "detail": desc})
    for t in topics or []:
        leaves["world"].append({"id": f"topic:{t.get('topic')}", "label": str(t.get("topic") or ""), "detail": str(t.get("summary") or "")[:300]})

    nodes: list[dict[str, Any]] = [{"id": "root", "label": user, "group": "root", "kind": "root"}]
    edges: list[dict[str, str]] = []
    for bid, label, _ in BRANCHES:
        if not leaves[bid]:
            continue
        branch_id = f"branch:{bid}"
        nodes.append({"id": branch_id, "label": label, "group": bid, "kind": "branch", "count": len(leaves[bid])})
        edges.append({"from": "root", "to": branch_id})
        for leaf in leaves[bid]:
            nodes.append({**leaf, "group": bid, "kind": "leaf"})
            edges.append({"from": branch_id, "to": leaf["id"]})

    recent = [n for n in leaves["episodic"][:2]]
    return {
        "nodes": nodes, "edges": edges, "total": sum(len(v) for v in leaves.values()), "relations": relations,
        "sections": [s for s in SECTIONS if leaves[s["id"]]],
        "callouts": {
            "episodic": [{"label": n["label"], "time": n.get("time", "")} for n in recent],
            "relations": relations[:2],
            "preferences": prefs[:3],
            "vectors": vectors,
        },
    }
