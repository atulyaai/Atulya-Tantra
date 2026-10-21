"""PLAN M13-2 / AUDIT H3: secrets are encrypted at rest off Windows too, with the key outside data/."""
import base64
import json
import os
import stat

import pytest

from atulya import secrets_store


@pytest.fixture()
def fernet_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_SECRETS_SCHEME", "fernet")
    monkeypatch.setenv("ATULYA_SECRETS_KEY_FILE", str(tmp_path / "config" / "secrets.key"))
    data = tmp_path / "data"
    data.mkdir()
    return data


def test_round_trip_is_encrypted_and_key_lives_outside_data(fernet_env, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    secrets_store.set_secret(fernet_env, "TELEGRAM_BOT_TOKEN", "123:very-secret-value")
    blob = secrets_store.secrets_path(fernet_env).read_bytes()
    assert blob.startswith(b"FERNET:") and b"very-secret-value" not in blob
    assert b"very-secret-value" not in base64.b64decode(blob[7:] + b"==", validate=False)
    assert not any(path.name == "secrets.key" for path in fernet_env.rglob("*"))   # key not in the data folder
    assert secrets_store.load_protected(fernet_env) == 1
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "123:very-secret-value"


def test_wrong_key_cannot_decrypt(fernet_env, tmp_path, monkeypatch):
    secrets_store.set_secret(fernet_env, "SOME_API_KEY", "abc")
    monkeypatch.setenv("ATULYA_SECRETS_KEY_FILE", str(tmp_path / "other.key"))  # e.g. a copied data folder
    with pytest.raises(Exception):
        secrets_store.load_protected(fernet_env)


def test_plain_file_is_migrated_on_load(fernet_env, monkeypatch):
    monkeypatch.delenv("OLD_API_KEY", raising=False)
    path = secrets_store.secrets_path(fernet_env)
    path.write_bytes(b"PLAIN:" + base64.b64encode(json.dumps({"OLD_API_KEY": "legacy"}).encode()))
    assert secrets_store.load_protected(fernet_env) == 1
    assert path.read_bytes().startswith(b"FERNET:")
    assert os.environ["OLD_API_KEY"] == "legacy"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_file_and_key_modes_are_owner_only(fernet_env):
    secrets_store.set_secret(fernet_env, "SOME_API_KEY", "abc")
    for path in (secrets_store.secrets_path(fernet_env), secrets_store.key_path()):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path


def test_protect_moves_env_values(fernet_env, tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("GROQ_API_KEY=gsk_live_value\nATULYA_PORT=8501\n", encoding="utf-8")
    assert secrets_store.protect(env, fernet_env) == ["GROQ_API_KEY"]
    assert "gsk_live_value" not in env.read_text(encoding="utf-8")
    assert secrets_store.load_protected(fernet_env) == 1 and os.environ["GROQ_API_KEY"] == "gsk_live_value"
