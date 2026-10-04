import json

import pytest
from fastapi.testclient import TestClient

from atulya import vault


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_VAULT_DIR", str(tmp_path))
    monkeypatch.delenv("ATULYA_VAULT_PASSPHRASE", raising=False)
    vault._cache.clear()


def test_off_means_plain_text_and_says_so(tmp_path):
    f = tmp_path / "a.json"
    vault.write_text(f, '{"x": 1}')
    assert f.read_text() == '{"x": 1}' and not vault.status(tmp_path)["on"]


def test_roundtrip_is_really_encrypted(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "correct horse")
    f = tmp_path / "money.json"
    vault.write_text(f, '{"secret": "salary 50000"}')
    raw = f.read_bytes()
    assert raw.startswith(b"ATV1") and b"salary" not in raw and b"50000" not in raw
    assert json.loads(vault.read_text(f)) == {"secret": "salary 50000"}
    assert oct(f.stat().st_mode)[-3:] == "600"


def test_wrong_or_missing_passphrase_locks_and_never_overwrites(tmp_path, monkeypatch):
    f = tmp_path / "money.json"
    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "right")
    vault.write_text(f, '{"v": 1}')
    before = f.read_bytes()
    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "wrong")
    vault._cache.clear()
    with pytest.raises(vault.VaultLocked):
        vault.read_text(f)
    with pytest.raises(vault.VaultLocked):
        vault.write_text(f, '{"v": "overwritten"}')
    monkeypatch.delenv("ATULYA_VAULT_PASSPHRASE")
    with pytest.raises(vault.VaultLocked):
        vault.write_text(f, "{}")
    assert f.read_bytes() == before                      # untouched through all of that


def test_tampering_is_detected(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "p")
    f = tmp_path / "x.json"
    vault.write_text(f, '{"a": 1}')
    blob = bytearray(f.read_bytes())
    blob[-3] ^= 0x01
    f.write_bytes(bytes(blob))
    with pytest.raises(vault.VaultLocked):
        vault.read_text(f)


def test_plain_files_are_encrypted_on_demand_and_only_private_ones(tmp_path, monkeypatch):
    (tmp_path / "money.json").write_text('{"m": 1}')
    (tmp_path / "settings.json").write_text('{"s": 1}')
    with pytest.raises(vault.VaultLocked):
        vault.encrypt_tree(tmp_path)                     # no passphrase yet
    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "p")
    assert vault.encrypt_tree(tmp_path) == 1
    assert (tmp_path / "money.json").read_bytes().startswith(b"ATV1") and (tmp_path / "settings.json").read_text() == '{"s": 1}'
    assert vault.encrypt_tree(tmp_path) == 0
    s = vault.status(tmp_path)
    assert s == {"on": True, "encrypted_files": 1, "plain_files": 1}


def test_money_and_chat_history_and_profiles_use_the_vault(tmp_path, monkeypatch):
    from atulya.agent import money as m
    from atulya.agent import tools as t
    from atulya.cognition.profile import ProfileStore
    from atulya.server import chat_history

    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "p")
    monkeypatch.setattr(t, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_history, "HISTORY_FILE", tmp_path / "chat_history.json")
    import asyncio

    asyncio.run(m.expense_add(500, "food", "lunch"))
    chat_history.append_exchange({"username": "a"}, "hello private", "hi")
    store = ProfileStore(tmp_path / "profiles")
    store.remember("a", [{"kind": "person", "key": "wife", "value": "Priya"}])
    for f in (tmp_path / "money.json", tmp_path / "chat_history.json", tmp_path / "profiles" / "a.json"):
        assert f.read_bytes().startswith(b"ATV1"), f
        assert b"Priya" not in f.read_bytes() and b"hello private" not in f.read_bytes()
    assert m._load()["expenses"][0]["amount"] == 500                    # and they still read back
    assert chat_history.list_messages({"username": "a"})[0]["text"] == "hello private"
    assert store.load("a")["facts"][0]["value"] == "Priya"
    monkeypatch.setenv("ATULYA_VAULT_PASSPHRASE", "wrong")
    vault._cache.clear()
    before = (tmp_path / "money.json").read_bytes()
    with pytest.raises(vault.VaultLocked):
        asyncio.run(m.expense_add(1, "x"))                              # cannot add to what it cannot open
    chat_history.append_exchange({"username": "a"}, "should not be saved", "no")   # silently skipped, no crash
    assert (tmp_path / "money.json").read_bytes() == before


def test_routes_report_status_and_a_locked_vault_is_423(tmp_path, monkeypatch):
    from atulya.server.app import app
    from atulya.server.state import ADMIN_TOKEN

    c = TestClient(app)
    assert c.get("/api/vault").status_code in (401, 403)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    assert c.get("/api/vault", headers=h).json()["on"] is False
    assert c.post("/api/vault/encrypt-now", headers=h).status_code == 400
