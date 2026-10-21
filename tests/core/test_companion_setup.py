import httpx
import pytest

from tools import companion_setup


def test_setup_verifies_only_paired_credential_and_rejects_unsafe_origins(monkeypatch):
    original = httpx.Client
    def handler(request):
        assert request.url.path == "/api/agents/register"
        assert request.headers["Authorization"] == "Bearer test-device-token"
        return httpx.Response(200, json={"name": "This-PC", "registered": True})
    monkeypatch.setattr(companion_setup.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert companion_setup.verify_connection("https://atulya.example", "test-device-token") == "This-PC"
    for url in ["http://atulya.example", "https://user:pass@atulya.example", "https://atulya.example?token=bad"]:
        with pytest.raises(ValueError):
            companion_setup.verify_connection(url, "test-device-token")
