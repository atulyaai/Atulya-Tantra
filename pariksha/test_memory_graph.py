from atulya.smriti import build_memory_graph


def test_graph_has_a_branch_per_kind_and_a_leaf_per_source():
    view = {"user": "aj", "facts": [
        {"id": "1", "kind": "person", "key": "wife", "value": "Priya", "text": "Your wife is Priya"},
        {"id": "2", "kind": "place", "key": "home", "value": "Delhi", "text": "You live in Delhi"},
        {"id": "3", "kind": "preference", "key": "likes", "value": "cricket", "text": "You like cricket"}],
        "habits": [{"signature": "s", "label": "play lofi", "when": "around 9 pm"}]}
    g = build_memory_graph(
        view, episodes=[{"text": "what is my day", "created_at": "t"}], skills=[("play_music", "Play a song")],
        mood={"mood": "calm"}, brains=[{"name": "Groq", "seconds": 0.8}], vectors=7)
    ids = {n["id"] for n in g["nodes"]}
    assert {"root", "branch:personal", "branch:concepts", "branch:preference", "branch:episodic",
            "branch:skills", "branch:self", "branch:arch"} <= ids
    assert "branch:world" not in ids                      # nothing there, so no empty branch
    assert g["relations"] == [{"a": "aj", "rel": "wife", "b": "Priya"}]
    assert g["callouts"]["preferences"] == ["likes: cricket"] and g["callouts"]["vectors"] == 7
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"])
    assert {s["id"] for s in g["sections"]} == {n["group"] for n in g["nodes"] if n["kind"] == "branch"}


def test_bare_profile_still_shows_the_architecture_branch():
    g = build_memory_graph({"user": "aj", "facts": [], "habits": []})
    assert [n["id"] for n in g["nodes"]] == ["root", "branch:arch"] + [n["id"] for n in g["nodes"][2:]]
    assert g["relations"] == [] and g["total"] == len(g["nodes"]) - 2


def test_route_requires_login():
    from fastapi.testclient import TestClient

    from atulya.sevak import app

    assert TestClient(app).get("/api/memory/graph").status_code in (401, 403)


def test_mood_route_requires_login_and_reports_values(monkeypatch):
    from fastapi.testclient import TestClient

    from atulya.sevak import app

    client = TestClient(app)
    assert client.get("/api/mood").status_code in (401, 403)
    from atulya.khata import ADMIN_TOKEN as token
    body = client.get("/api/mood", headers={"X-Atulya-Token": token}).json()
    assert set(body) == {"label", "valence", "energy"} and -1 <= body["valence"] <= 1
