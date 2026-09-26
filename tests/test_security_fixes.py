"""Regression tests for the security review: SSRF / local file read in
web_fetch, hostname-based SSRF bypass, the exec approval crash, the HTTPS
launcher, a sign-in secret that survives restarts, and CORS."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import httpx
import pytest

PUBLIC = "93.184.215.14"


def fake_dns(table):
    def resolve(host):
        if host not in table:
            raise OSError("no such host")
        return set(table[host])
    return resolve


# ── SSRF guard ────────────────────────────────────────────────────────────

class TestSSRF:
    @pytest.fixture
    def guard(self):
        from tantra.core.security import SSRFProtection

        return SSRFProtection(resolver=fake_dns({
            "example.com": [PUBLIC], "localtest.me": ["127.0.0.1", "::1"], "mixed.test": [PUBLIC, "10.0.0.5"],
        }))

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd", "file:///D:/Atulya-Tantra/.env", "ftp://example.com/x", "gopher://example.com",
        "http://127.0.0.1:8000", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://169.254.169.254/latest/meta-data/",
        "http://10.1.2.3", "http://192.168.1.1/admin", "http://100.64.0.1", "http://0.0.0.0:8000",
        "http://localhost:8000", "http://printer.local", "http://localtest.me:8000",  # a name that points home
        "http://mixed.test", "http://does-not-resolve.test",
    ])
    def test_blocked(self, guard, url):
        assert guard.check_url(url) is False

    def test_public_allowed(self, guard):
        assert guard.check_url("https://example.com/page") is True
        assert guard.check_url(f"http://{PUBLIC}/") is True


# ── web_fetch ─────────────────────────────────────────────────────────────

class TestWebFetch:
    def make(self, handler):
        from yantra.capabilities import WebFetchTool

        return WebFetchTool(transport=httpx.MockTransport(handler),
                            resolver=fake_dns({"example.com": [PUBLIC], "evil.test": [PUBLIC], "inside.test": ["10.0.0.9"]}))

    def test_reads_public_pages(self):
        tool = self.make(lambda r: httpx.Response(200, text="<h1>hello</h1>"))
        result = asyncio.run(tool.execute("https://example.com/"))
        assert result.success and result.output == "<h1>hello</h1>"

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1:8510/api/profile", "http://inside.test/"])
    def test_refuses_local_files_and_private_addresses(self, url):
        called = []
        tool = self.make(lambda r: called.append(r) or httpx.Response(200, text="secret"))
        result = asyncio.run(tool.execute(url))
        assert not result.success and "Refused" in result.error and called == []

    def test_redirect_to_the_inside_is_refused(self):
        def handler(request):
            if request.url.host == "evil.test":
                return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
            return httpx.Response(200, text="metadata")

        result = asyncio.run(self.make(handler).execute("http://evil.test/"))
        assert not result.success and "169.254.169.254" in result.error

    def test_public_redirect_is_followed(self):
        def handler(request):
            if request.url.path == "/old":
                return httpx.Response(301, headers={"location": "/new"})
            return httpx.Response(200, text="moved here")

        result = asyncio.run(self.make(handler).execute("https://example.com/old"))
        assert result.success and result.output == "moved here"

    def test_lan_can_be_allowed_explicitly(self, monkeypatch):
        monkeypatch.setenv("ATULYA_FETCH_ALLOW_PRIVATE", "1")
        tool = self.make(lambda r: httpx.Response(200, text="router page"))
        assert asyncio.run(tool.execute("http://192.168.1.1/")).output == "router page"
        assert not asyncio.run(tool.execute("file:///etc/passwd")).success  # never files


# ── exec tool ─────────────────────────────────────────────────────────────

class TestExec:
    def test_critical_command_is_rejected_not_a_crash(self):
        from yantra.capabilities import ExecTool

        result = asyncio.run(ExecTool().execute("sudo rm -rf /", allow_exec=True, allow_list=["sudo"]))
        assert not result.success and "critical risk" in result.error

    @pytest.mark.skipif(sys.platform == "win32", reason="uses the POSIX echo")
    def test_allow_listed_command_runs(self):
        from yantra.capabilities import ExecTool

        result = asyncio.run(ExecTool().execute("echo hello", allow_exec=True, allow_list=["echo"]))
        assert result.success and result.output.strip() == "hello"


# ── HTTPS launcher ────────────────────────────────────────────────────────

def _cryptography_works() -> bool:
    probe = subprocess.run([sys.executable, "-c", "from cryptography.hazmat.primitives import serialization"],
                           capture_output=True)
    return probe.returncode == 0


@pytest.mark.skipif(not _cryptography_works(), reason="cryptography is unusable in this environment")
def test_https_launcher_generates_certificates(tmp_path, monkeypatch):
    from drishti import run_https

    monkeypatch.setattr(run_https, "CERTS_DIR", tmp_path)
    cert, key = run_https._ensure_certs()
    assert os.path.getsize(cert) > 0 and os.path.getsize(key) > 0


# ── sign-in secret ────────────────────────────────────────────────────────

class TestJwtSecret:
    def test_created_once_private_and_reused(self, tmp_path, monkeypatch):
        from drishti.dashboard import state

        path = tmp_path / "config" / "jwt_secret.key"
        monkeypatch.delenv("ATULYA_JWT_SECRET", raising=False)
        monkeypatch.setenv("ATULYA_JWT_SECRET_FILE", str(path))
        monkeypatch.setattr(state, "ADMIN_TOKEN_SOURCE", "generated_runtime")
        first = state._load_jwt_secret()
        assert len(first) >= 48 and path.read_text() == first
        if os.name == "posix":
            assert oct(path.stat().st_mode & 0o777) == "0o600"
        assert state._load_jwt_secret() == first  # a restart or another worker gets the same key

    def test_explicit_settings_win(self, tmp_path, monkeypatch):
        from drishti.dashboard import state

        monkeypatch.setenv("ATULYA_JWT_SECRET_FILE", str(tmp_path / "k"))
        monkeypatch.setenv("ATULYA_JWT_SECRET", "from-env")
        assert state._load_jwt_secret() == "from-env"
        monkeypatch.delenv("ATULYA_JWT_SECRET")
        monkeypatch.setattr(state, "ADMIN_TOKEN_SOURCE", "env")
        monkeypatch.setattr(state, "ADMIN_TOKEN", "dashboard-token")
        assert state._load_jwt_secret() == "dashboard-token"  # existing setups keep their tokens


# ── CORS ──────────────────────────────────────────────────────────────────

def test_cors_never_allows_credentials_for_any_origin():
    from fastapi.testclient import TestClient
    from drishti.dashboard.app import app

    resp = TestClient(app).get("/api/health", headers={"Origin": "https://evil.example"})
    assert resp.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in resp.headers
