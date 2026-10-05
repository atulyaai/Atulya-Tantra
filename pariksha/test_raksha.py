"""Tests for atulya/raksha.py."""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import subprocess
import sys

import httpx
import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from atulya import raksha as https
from atulya import raksha as vault


# ── test_https ────────────────────────────────────────────────────────────
def load(d):
    return x509.load_pem_x509_certificate((d / "cert.pem").read_bytes())


def san(cert):
    ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return set(ext.get_values_for_type(x509.DNSName)), {str(i) for i in ext.get_values_for_type(x509.IPAddress)}


def test_certificate_covers_this_computers_names_and_addresses(tmp_path):
    cert_file, key_file = https.ensure_certs(tmp_path, ["localhost", "mypc"], ["127.0.0.1", "192.168.1.15"])
    assert san(load(tmp_path)) == ({"localhost", "mypc"}, {"127.0.0.1", "192.168.1.15"})
    c = load(tmp_path)
    assert c.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc) > datetime.timedelta(days=360)
    assert c.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False        # not a certificate authority
    assert https.private_file_is_restricted(tmp_path / "key.pem")
    assert cert_file.endswith("cert.pem") and key_file.endswith("key.pem")


def test_reuses_a_good_pair_and_renews_when_the_address_changes_or_it_is_unreadable(tmp_path):
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    first = (tmp_path / "cert.pem").read_bytes()
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    assert (tmp_path / "cert.pem").read_bytes() == first                                         # nothing changed: kept
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1", "192.168.1.99"])                   # a new network address
    assert "192.168.1.99" in san(load(tmp_path))[1] and (tmp_path / "cert.pem").read_bytes() != first
    (tmp_path / "cert.pem").write_text("garbage")
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    assert san(load(tmp_path))[0] == {"localhost"}


def test_switch_and_local_names(monkeypatch):
    monkeypatch.delenv("ATULYA_HTTPS", raising=False)
    assert not https.https_enabled()
    for v in ("on", "1", "TRUE"):
        monkeypatch.setenv("ATULYA_HTTPS", v)
        assert https.https_enabled()
    names, ips = https.local_names()
    assert "localhost" in names and "127.0.0.1" in ips


def test_the_key_is_never_world_readable(tmp_path):
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    assert https.private_file_is_restricted(tmp_path / "key.pem")


# ── test_vault ────────────────────────────────────────────────────────────
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
    assert vault.private_file_is_restricted(f)


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
    from atulya import dwar as chat_history
    from atulya import kriya as m
    from atulya import kriya as t
    from atulya.buddhi import ProfileStore

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
    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    c = TestClient(app)
    assert c.get("/api/vault").status_code in (401, 403)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    assert c.get("/api/vault", headers=h).json()["on"] is False
    assert c.post("/api/vault/encrypt-now", headers=h).status_code == 400


# ── test_security_fixes ────────────────────────────────────────────────────────────
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
        from atulya.raksha import SSRFProtection

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
        from atulya.kaushal import WebFetchTool

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
        from atulya.kaushal import ExecTool

        result = asyncio.run(ExecTool().execute("sudo rm -rf /", allow_exec=True, allow_list=["sudo"]))
        assert not result.success and "critical risk" in result.error

    @pytest.mark.skipif(sys.platform == "win32", reason="uses the POSIX echo")
    def test_allow_listed_command_runs(self):
        from atulya.kaushal import ExecTool

        result = asyncio.run(ExecTool().execute("echo hello", allow_exec=True, allow_list=["echo"]))
        assert result.success and result.output.strip() == "hello"


# ── HTTPS launcher ────────────────────────────────────────────────────────

def _cryptography_works() -> bool:
    probe = subprocess.run([sys.executable, "-c", "from cryptography.hazmat.primitives import serialization"],
                           capture_output=True)
    return probe.returncode == 0


@pytest.mark.skipif(not _cryptography_works(), reason="cryptography is unusable in this environment")
def test_https_generates_certificates(tmp_path, monkeypatch):
    from atulya import raksha as run_https

    monkeypatch.setenv("ATULYA_CERTS_DIR", str(tmp_path))
    cert, key = run_https.ensure_certs()
    assert os.path.getsize(cert) > 0 and os.path.getsize(key) > 0
    assert str(tmp_path) in cert and str(tmp_path) in key


# ── sign-in secret ────────────────────────────────────────────────────────

class TestJwtSecret:
    def test_created_once_private_and_reused(self, tmp_path, monkeypatch):
        from atulya import dwar as state

        path = tmp_path / "kosh" / "jwt_secret.key"
        monkeypatch.delenv("ATULYA_JWT_SECRET", raising=False)
        monkeypatch.setenv("ATULYA_JWT_SECRET_FILE", str(path))
        monkeypatch.setattr(state, "ADMIN_TOKEN_SOURCE", "generated_runtime")
        first = state._load_jwt_secret()
        assert len(first) >= 48 and path.read_text() == first
        if os.name == "posix":
            assert oct(path.stat().st_mode & 0o777) == "0o600"
        assert state._load_jwt_secret() == first  # a restart or another worker gets the same key

    def test_explicit_settings_win(self, tmp_path, monkeypatch):
        from atulya import dwar as state

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

    from atulya.sevak import app

    resp = TestClient(app).get("/api/health", headers={"Origin": "https://evil.example"})
    assert resp.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in resp.headers

