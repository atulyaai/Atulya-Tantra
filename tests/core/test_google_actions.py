import asyncio
import base64
from email import message_from_bytes

import pytest
import httpx

from tools.plugins.information import google_api


def test_google_tokens_follow_data_dir_loaded_after_module_import(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    google_api.save_connection("alice", {"refresh_token": "test-refresh", "scope": google_api.READ})
    assert google_api.connection_status("alice")["connected"]
    assert (project_temp_dir / "google_tokens.json").is_file()


def test_calendar_delete_accepts_real_empty_204_response(monkeypatch):
    async def token(*args):
        return "test-token"
    monkeypatch.setattr(google_api, "get_access_token", token)
    original = httpx.AsyncClient
    def handler(request):
        assert request.method == "DELETE"
        return httpx.Response(204)
    monkeypatch.setattr(google_api.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler)))
    assert "Deleted Google Calendar event evt123" in asyncio.run(google_api.calendar_delete("admin", "evt123"))


def test_gmail_send_has_real_receipt_and_rejects_header_injection(monkeypatch):
    recorded=[]
    async def request(user,method,url,**kwargs):
        recorded.append((user,method,url,kwargs))
        return {"id":"provider-id"}
    monkeypatch.setattr(google_api,"_request",request)
    result=asyncio.run(google_api.gmail_send("alice","bob@example.com","Hello","Body"))
    assert "provider-id" in result and "Recipient delivery is not verified" in result
    encoded=recorded[0][3]["json"]["raw"]
    email=message_from_bytes(base64.urlsafe_b64decode(encoded))
    assert email["To"] == "bob@example.com" and email["Subject"] == "Hello"
    with pytest.raises(ValueError):
        asyncio.run(google_api.gmail_send("alice","bob@example.com\r\nBcc:evil@example.com","Hello","Body"))
    assert len(recorded)==1


def test_google_actions_do_not_claim_success_without_provider_id(monkeypatch):
    async def request(*args,**kwargs):
        return {}
    monkeypatch.setattr(google_api,"_request",request)
    with pytest.raises(ValueError,match="receipt"):
        asyncio.run(google_api.gmail_send("alice","bob@example.com","Hello","Body"))
    with pytest.raises(ValueError,match="event ID"):
        asyncio.run(google_api.calendar_create("alice","Meeting","2026-11-01T12:00:00+05:30"))
    with pytest.raises(ValueError):
        asyncio.run(google_api.calendar_create("alice","Meeting","2026-11-01T12:00:00"))


def test_phone_requests_are_private_and_record_a_real_sms_receipt(project_temp_dir):
    from atulya.phone_actions import PhoneActions
    store=PhoneActions(project_temp_dir)
    item=store.add("alice","compose_sms","+911234567890","Hello")
    assert store.pending("bob")==[]
    assert not store.receipt("bob",item["id"],"composer_opened")
    with pytest.raises(ValueError):
        store.receipt("alice",item["id"],"delivered")
    sent=store.add("alice","compose_sms","+911234567890","Hello")
    assert store.receipt("alice",sent["id"],"sms_sent")
    assert store.receipt("alice",item["id"],"composer_opened")
    assert not store.pending("alice")
