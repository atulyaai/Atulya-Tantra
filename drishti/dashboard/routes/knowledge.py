"""Knowledge galaxy: everything Atulya knows, as stars and constellations.

The signed-in user is the sun. Around it: what Atulya has learned about them
(facts, habits, trusted actions), the topics they talk about, and Atulya's own
skills. Admins also see the shared long-term memories. Each node carries the
details the UI shows on hover.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from drishti.dashboard import chat_history
from drishti.dashboard.helpers import _require_auth

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[3]
_MEMORY_FILE = _ROOT / "assets" / "memory" / "vector_atulya_memory.json"

_STOP = set("""a an the and or but if then so of to in on at for from by with about as is are was were be been
being do does did have has had i me my mine you your yours we our us it its this that these those what which who
whom how why when where can could would should will shall may might must not no yes ok okay please thanks thank
hi hello hey just like get got make made tell say said know want need also very really there here some any all
more most much many one two up down out over again than too into only own same other such few each both now
atulya jarvis let lets im dont ive youre whats""".split())

_CLUSTERS = {
    "you": "You",
    "about": "About you",
    "habit": "Habits",
    "trust": "Trusted actions",
    "topic": "Your topics",
    "memory": "Memories",
    "skill": "Skills",
}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z']{2,}", (text or "").lower()) if w.strip("'") not in _STOP]


def _profile(request: Request, username: str) -> dict[str, Any]:
    from atulya.cognition import get_kernel
    from atulya.llm import get_default_llm

    try:
        return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm()).profiles.view(username)
    except Exception:
        return {"facts": [], "habits": [], "approvals": []}


def _memories(limit: int = 80) -> list[dict[str, Any]]:
    try:
        data = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = data.get("entries") if isinstance(data, dict) else data
    return list(entries or [])[-limit:]


def _skills(request: Request) -> list[dict[str, str]]:
    llm = getattr(request.app.state, "llm", None)
    tools = getattr(llm, "tools", None)
    try:
        return tools.list_tools() if tools else []
    except Exception:
        return []


def build_galaxy(user: dict, profile: dict, messages: list[dict], memories: list[dict],
                 skills: list[dict]) -> dict[str, Any]:
    name = str(user.get("display_name") or user.get("username") or "You")
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, str]] = []

    def add(node_id: str, label: str, group: str, detail: str = "", meta: dict | None = None,
            weight: float = 1.0, parent: str | None = "you") -> None:
        nodes.append({"id": node_id, "label": label[:60], "group": group, "detail": detail[:600],
                      "meta": meta or {}, "weight": round(weight, 2)})
        if parent:
            links.append({"source": parent, "target": node_id})

    add("you", name, "you", f"Signed in as {user.get('username', '')}", {"role": user.get("role", "")},
        weight=4, parent=None)
    add("atulya", "Atulya", "you", "Your assistant — everything around here is what it knows and can do.",
        weight=3)

    for fact in profile.get("facts", []):
        add(f"fact:{fact.get('id', fact.get('key'))}", fact.get("text") or fact.get("value", ""), "about",
            fact.get("text", ""), {"kind": fact.get("kind", ""), "learned": fact.get("created_at", "")})
    for i, habit in enumerate(profile.get("habits", [])):
        label = habit.get("text") or habit.get("label") or habit.get("action") or str(habit)
        add(f"habit:{i}", str(label), "habit", str(label),
            {k: v for k, v in habit.items() if isinstance(v, (str, int, float))})
    for appr in profile.get("approvals", []):
        add(f"trust:{appr['key']}", appr["key"].replace(":", " → "), "trust",
            "Runs without asking" if appr.get("trusted") else "Atulya still asks before doing this",
            {"approved": appr.get("count", ""), "trusted": bool(appr.get("trusted"))})

    counts = Counter(w for m in messages if m.get("role") == "user" for w in _words(m.get("text", "")))
    samples: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "user":
            for w in _words(m.get("text", "")):
                samples.setdefault(w, m.get("text", ""))
    for word, n in counts.most_common(24):
        add(f"topic:{word}", word, "topic", f"“{samples.get(word, '')[:160]}”", {"mentions": n}, weight=1 + n / 3)

    topic_ids = {f"topic:{w}" for w, _ in counts.most_common(24)}
    seen: set[str] = set()
    for mem in reversed(memories):  # newest first; repeats of the same memory collapse
        content = str(mem.get("content", ""))
        first = re.split(r"\n|\s+A:", content, maxsplit=1)[0].removeprefix("Q:").strip() or content[:40]
        if first.lower() in seen:
            continue
        seen.add(first.lower())
        mid = f"memory:{mem.get('id')}"
        add(mid, first, "memory", content, {"tags": ", ".join(mem.get("tags") or [])}, parent="atulya")
        for w in set(_words(content)):  # memories that touch your topics link to them
            if f"topic:{w}" in topic_ids:
                links.append({"source": mid, "target": f"topic:{w}"})

    for tool in skills:
        add(f"skill:{tool['name']}", tool["name"].replace("_", " "), "skill", tool.get("description", ""),
            parent="atulya", weight=0.8)

    groups = Counter(n["group"] for n in nodes)
    return {"nodes": nodes, "links": links,
            "clusters": [{"id": g, "label": _CLUSTERS[g], "count": groups[g]} for g in _CLUSTERS if groups[g]]}


@router.get("/api/knowledge/galaxy")
def api_galaxy(request: Request, user: dict = Depends(_require_auth)):
    username = str(user.get("username") or "default")
    memories = _memories() if user.get("role") == "admin" else []  # shared store: admins only
    return build_galaxy(user, _profile(request, username), chat_history.list_messages(user, limit=400),
                        memories, _skills(request))
