"""Twilio callback authentication and outbound TwiML safety."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.datastructures import FormData
from starlette.requests import Request


def _request(path: str = "/api/twilio/sms", query: bytes = b"") -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "server": ("internal", 443),
        "client": ("127.0.0.1", 1234),
        "root_path": "",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": [(b"host", b"internal")],
    })


def test_twilio_callback_requires_configured_secret(monkeypatch):
    from atulya.dwar import _validate_twilio_webhook

    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        _validate_twilio_webhook(_request(), FormData({"Body": "hi"}))
    assert exc.value.status_code == 503


def test_twilio_callback_rejects_missing_or_invalid_signature(monkeypatch):
    from atulya.dwar import _validate_twilio_webhook

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setenv("ATULYA_TWILIO_PUBLIC_BASE_URL", "https://voice.example.test")
    with pytest.raises(HTTPException) as missing:
        _validate_twilio_webhook(_request(), FormData({"Body": "hi"}))
    assert missing.value.status_code == 403

    request = _request()
    request.scope["headers"].append((b"x-twilio-signature", b"invalid"))
    with pytest.raises(HTTPException) as invalid:
        _validate_twilio_webhook(request, FormData({"Body": "hi"}))
    assert invalid.value.status_code == 403


def test_twilio_callback_validates_public_url_and_query(monkeypatch):
    from twilio.request_validator import RequestValidator
    from atulya.dwar import _validate_twilio_webhook

    secret = "test-auth-token"
    base_url = "https://voice.example.test"
    path = "/api/twilio/sms"
    query = b"account=one"
    params = {"From": "+15551234567", "Body": "hello"}
    signature = RequestValidator(secret).compute_signature(f"{base_url}{path}?account=one", params)
    request = _request(path, query)
    request.scope["headers"].append((b"x-twilio-signature", signature.encode()))
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", secret)
    monkeypatch.setenv("ATULYA_TWILIO_PUBLIC_BASE_URL", base_url)

    _validate_twilio_webhook(request, FormData(params))


def test_outbound_call_text_cannot_inject_twi_ml():
    from atulya.kriya import _twilio_say_twiml

    assert _twilio_say_twiml("Hi <Redirect>https://evil.test</Redirect> & bye") == (
        "<Response><Say>Hi &lt;Redirect&gt;https://evil.test&lt;/Redirect&gt; &amp; bye</Say></Response>"
    )
