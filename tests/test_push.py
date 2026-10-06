import pytest

from atulya import sandesh as push


def test_push_subscriptions_are_validated_bounded_and_removable(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    sub = {"endpoint": "https://push.example/sub/1", "keys": {"p256dh": "public", "auth": "secret"}}
    with pytest.raises(ValueError):
        push.subscribe("alice", {"endpoint": "http://insecure.invalid", "keys": {}})
    push.subscribe("alice", sub)
    push.subscribe("alice", sub)
    data = push._read()
    assert len(data["alice"]) == 1
    assert data["alice"][0] == sub
    push.unsubscribe("alice", sub["endpoint"])
    assert push._read() == {}


def test_web_push_without_server_keys_is_a_safe_noop(monkeypatch):
    monkeypatch.delenv("ATULYA_VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ATULYA_VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("ATULYA_VAPID_SUBJECT", raising=False)
    assert not push.configured()
    assert push.send("admin", {"title": "test"}) == 0
