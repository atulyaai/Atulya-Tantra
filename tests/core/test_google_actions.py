import asyncio
import base64
from email import message_from_bytes

import pytest

from tools.plugins.information import google_api


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


def test_phone_requests_are_private_and_never_report_sms_sent(project_temp_dir):
    from atulya.phone_actions import PhoneActions
    store=PhoneActions(project_temp_dir)
    item=store.add("alice","compose_sms","+911234567890","Hello")
    assert store.pending("bob")==[]
    assert not store.receipt("bob",item["id"],"composer_opened")
    with pytest.raises(ValueError):
        store.receipt("alice",item["id"],"sms_sent")
    assert store.receipt("alice",item["id"],"composer_opened")
    assert not store.pending("alice")
