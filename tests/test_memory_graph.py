from atulya.memory.graph import build_memory_graph


def test_graph_has_a_branch_per_kind_and_a_leaf_per_fact():
    view = {"user": "aj", "facts": [
        {"id": "1", "kind": "person", "key": "wife", "value": "Priya", "text": "Your wife is Priya"},
        {"id": "2", "kind": "place", "key": "home", "value": "Delhi", "text": "You live in Delhi"},
        {"id": "3", "kind": "weird", "key": "x", "value": "odd", "text": "odd"}],
        "habits": [{"signature": "s", "label": "play lofi", "when": "around 9 pm"}]}
    g = build_memory_graph(view)
    ids = {n["id"] for n in g["nodes"]}
    assert {"root", "branch:person", "branch:place", "branch:habit", "branch:note"} <= ids
    assert g["total"] == 4
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"])


def test_empty_memory_is_just_the_trunk():
    g = build_memory_graph({"user": "aj", "facts": [], "habits": []})
    assert [n["id"] for n in g["nodes"]] == ["root"] and g["edges"] == []


def test_route_requires_login():
    from fastapi.testclient import TestClient

    from atulya.server.app import app

    assert TestClient(app).get("/api/memory/graph").status_code in (401, 403)


def test_mood_route_requires_login_and_reports_values(monkeypatch):
    from fastapi.testclient import TestClient

    from atulya.server.app import app

    client = TestClient(app)
    assert client.get("/api/mood").status_code in (401, 403)
    from atulya.server.state import ADMIN_TOKEN as token
    body = client.get("/api/mood", headers={"X-Atulya-Token": token}).json()
    assert set(body) == {"label", "valence", "energy"} and -1 <= body["valence"] <= 1
