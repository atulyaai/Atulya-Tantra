import httpx
import pytest

from tools.device_companion import execute, poll_once


@pytest.mark.parametrize("kind", ["send_sms", "place_call", "say"])
def test_unimplemented_actions_cannot_report_execution(kind):
    with pytest.raises(ValueError):
        execute(kind, "test")


def test_lost_receipt_response_retries_receipt_without_repeating_action():
    calls, receipts = [], []
    first = True

    def handler(request):
        nonlocal first
        if request.url.path.endswith("/poll"):
            return httpx.Response(200, json={"jobs": [{"id": "job1", "kind": "ping"}]} if not calls else {"jobs": []})
        receipts.append(request.content)
        if first:
            first = False
            raise httpx.ReadError("Lost accepted response")
        return httpx.Response(200, json={"ok": True})

    def executor(kind, detail, folder):
        calls.append(kind)
        return "pong"

    pending = {}
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://test") as client:
        with pytest.raises(httpx.ReadError):
            poll_once(client, executor=executor, pending=pending)
        assert poll_once(client, executor=executor, pending=pending) == [{"id": "job1", "success": True}]
    assert calls == ["ping"]
    assert receipts[0] == receipts[1]
    assert not pending


def test_failed_device_action_posts_failed_receipt():
    import json
    results = []
    def handler(request):
        if request.url.path.endswith("/poll"):
            return httpx.Response(200, json={"jobs": [{"id": "job1", "kind": "send_sms"}]})
        results.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://test") as client:
        assert poll_once(client) == [{"id": "job1", "success": False}]
    assert results[0]["success"] is False
    assert "cannot execute" in results[0]["output"]


def test_notification_text_cannot_be_executed_as_powershell(monkeypatch):
    from tools import device_companion
    commands = []
    monkeypatch.setattr(device_companion, "SYSTEM", "Windows")
    monkeypatch.setattr(device_companion.subprocess, "Popen", lambda command, **kwargs: commands.append(command))
    payload = 'hello "; $(Get-Secret); `n bad'
    result = execute("display_message", payload)
    assert "accepted" in result
    assert payload not in commands[0][-1]
    assert "Get-Secret" not in commands[0][-1]
