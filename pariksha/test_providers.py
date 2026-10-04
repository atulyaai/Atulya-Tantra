import os

from fastapi.testclient import TestClient

from atulya.adhar import set_env_value
from atulya.mastishk import BY_ID, CATALOG


def test_catalog_is_consistent():
    ids = [s.id for s in CATALOG]
    assert len(ids) == len(set(ids)) and "mistral" in ids and "qwen" in ids and "anthropic" in ids
    assert all(s.base_url for s in CATALOG if not s.builtin and s.id != "custom")


def test_set_env_value_updates_adds_and_removes(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# keep me\nA=1\nGROQ_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    set_env_value("GROQ_API_KEY", "new", f)
    set_env_value("MISTRAL_API_KEY", "m", f)
    assert f.read_text().splitlines() == ["# keep me", "A=1", "GROQ_API_KEY=new", "MISTRAL_API_KEY=m"]
    set_env_value("A", "", f)
    assert "A=1" not in f.read_text() and "A" not in os.environ
    for bad in ("x\ny", "a=b\r"):
        try:
            set_env_value("K", bad, f)
        except ValueError:
            continue
        raise AssertionError("newline injection accepted")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)


def test_generic_provider_follows_the_catalog(monkeypatch):
    from atulya.mastishk import OpenAICompatProvider, ProviderRouter

    p = OpenAICompatProvider(BY_ID["mistral"])
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert not p.is_available()
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert p.is_available() and p.URL == "https://api.mistral.ai/v1/chat/completions" and p.name() == "Mistral"
    monkeypatch.setenv("ATULYA_MISTRAL_MODEL", "a, b")
    assert p.models() == ["a", "b"]
    assert sum(isinstance(x, OpenAICompatProvider) for x in ProviderRouter().providers) >= 10


def test_routes_are_admin_only_and_never_return_keys(tmp_path, monkeypatch):
    import atulya.adhar as ef
    from atulya.sevak import app
    from atulya.dwar import ADMIN_TOKEN

    monkeypatch.setattr(ef, "env_path", lambda: tmp_path / ".env")
    monkeypatch.setattr("atulya.dwar.set_env_value", lambda k, v: ef.set_env_value(k, v, tmp_path / ".env"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    c = TestClient(app)
    assert c.get("/api/providers").status_code in (401, 403)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    r = c.post("/api/providers/deepseek", json={"key": "sk-secret-12345678"}, headers=h)
    assert r.status_code == 200 and r.json()["configured"] and "secret" not in r.text and r.json()["key_hint"] == "…5678"
    assert "sk-secret" not in c.get("/api/providers", headers=h).text
    assert c.post("/api/providers/nope", json={}, headers=h).status_code == 404
    assert c.post("/api/providers/deepseek/test", headers=h).status_code == 200
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
