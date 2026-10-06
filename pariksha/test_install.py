"""Tests for the one-command installer (install.py) and the file-tool guards."""

from __future__ import annotations

import asyncio
import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import install as installer  # noqa: E402


def capture(fn, *args, **kwargs):
    """Run fn, returning (result, printed_text)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = fn(*args, **kwargs)
    return result, buffer.getvalue()


class TestStatusReport:
    @pytest.fixture(autouse=True)
    def _repo_env(self, monkeypatch):
        """Load the repo's .env if present, so the table reflects a real install.

        A fresh clone has no .env (it is gitignored), so tests must never rely
        on a particular key already being set.
        """
        installer.load_existing()

    def test_counts_add_up(self):
        (present, missing), out = capture(installer.status_table)
        assert present + missing == len(installer.ITEMS)
        assert present >= 0
        assert "State" in out and "How to get it" in out

    def test_every_item_is_reported_once(self):
        _, out = capture(installer.status_table)
        for item in installer.ITEMS:
            assert item.label[:44] in out, f"{item.key} missing from the status table"

    def test_env_template_leaves_dashboard_token_for_secure_generation(self):
        template = (ROOT / ".env.example").read_text(encoding="utf-8")
        assert "ATULYA_DASHBOARD_TOKEN=your_secure_auth_token_here" not in template
        assert any(line.strip() == "ATULYA_DASHBOARD_TOKEN=" for line in template.splitlines())

    def test_never_prints_a_secret_value(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_SUPERSECRETVALUE123456")
        _, out = capture(installer.status_table)
        assert "gsk_SUPERSECRETVALUE123456" not in out
        assert "3456" in out  # last-4 hint is fine

    def test_status_line_shows_only_tail_for_secrets(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaEXACTLYSECRETSYMBOL")
        item = next(i for i in installer.ITEMS if i.key == "GEMINI_API_KEY")
        assert item.is_set()
        assert "AIza" not in item.shown()
        assert "(MBOL)" in item.shown()

    def test_non_secret_shows_its_value(self, monkeypatch):
        monkeypatch.setenv("ATULYA_PORT", "9000")
        item = next(i for i in installer.ITEMS if i.key == "ATULYA_PORT")
        assert item.shown() == "set (9000)"

    def test_missing_item_has_a_hint(self):
        for item in installer.ITEMS:
            if not item.is_set():
                assert item.hint, f"{item.key} is missing but offers no way to obtain it"

    def test_brain_ready_needs_at_least_one_key(self, monkeypatch):
        for key in (
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ATULYA_OLLAMA_MODEL",
        ):
            monkeypatch.delenv(key, raising=False)
        assert installer.brain_ready() is False
        monkeypatch.setenv("GROQ_API_KEY", "x")
        assert installer.brain_ready() is True

    def test_dashboard_token_is_auto_generated(self, monkeypatch):
        """A missing dashboard token is a security hole, so setup always creates one."""
        monkeypatch.delenv("ATULYA_DASHBOARD_TOKEN", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "x")
        monkeypatch.setenv("GROQ_API_KEY", "x")
        monkeypatch.setenv("ATULYA_BRIEFING_AT", "08:00")

        from atulya import adhar

        writes: list[tuple[str, str]] = []
        monkeypatch.setattr(adhar, "set_env_value", lambda k, v, path=None: writes.append((k, v)))
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))

        changed = capture(installer.interview, quiet=False)[0]

        assert "ATULYA_DASHBOARD_TOKEN" in changed
        token = dict(writes)["ATULYA_DASHBOARD_TOKEN"]
        assert len(token) >= 32, "generated token must be strong"
        assert token not in ("your_secure_auth_token_here", "changeme")
        assert "ATULYA_TELEGRAM_BOT_TOKEN" not in dict(writes)  # nothing asked without a tty

    def test_existing_token_is_left_alone(self, monkeypatch):
        monkeypatch.setenv("ATULYA_DASHBOARD_TOKEN", "already-here-token")
        from atulya import adhar

        writes: list[tuple[str, str]] = []
        monkeypatch.setattr(adhar, "set_env_value", lambda k, v, path=None: writes.append((k, v)))
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        changed = capture(installer.interview, quiet=False)[0]
        assert "ATULYA_DASHBOARD_TOKEN" not in changed
        assert ("ATULYA_DASHBOARD_TOKEN", "already-here-token") not in writes


class TestInterview:
    def test_closed_stdin_skips_without_crashing(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        changed, out = capture(installer.interview, quiet=False)
        assert "ATULYA_BRIEFING_AT" not in changed
        assert "skipped" in out and "GEMINI_API_KEY" in out

    def test_quiet_mode_asks_nothing(self, monkeypatch):
        monkeypatch.delenv("ATULYA_BRIEFING_AT", raising=False)
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        _, out = capture(installer.interview, quiet=True)
        assert "Choose" not in out and "(" not in out.split("still needed")[-1]

    @pytest.mark.parametrize(
        "value,good", [("08:00", True), ("23:59", True), ("25:99", False), ("8am", False), ("", True)]
    )
    def test_briefing_time_validator(self, value, good):
        item = next(i for i in installer.ITEMS if i.key == "ATULYA_BRIEFING_AT")
        assert (item.validate(value) is None) is good

    @pytest.mark.parametrize("value,good", [("1484854122", True), ("-1001234", True), ("abc", False), ("12 34", False)])
    def test_telegram_id_validator(self, value, good):
        item = next(i for i in installer.ITEMS if i.key == "ATULYA_TELEGRAM_ALLOWLIST")
        assert (item.validate(value) is None) is good

    @pytest.mark.parametrize(
        "value,good",
        [("7000000001:" + "A" * 35, True), ("not-a-token", False), ("12345", False)],
    )
    def test_bot_token_validator(self, value, good):
        item = next(i for i in installer.ITEMS if i.key == "ATULYA_TELEGRAM_BOT_TOKEN")
        assert (item.validate(value) is None) is good

    @pytest.mark.parametrize("value,good", [
        ("https://atulya.example.com", True),
        ("https://atulya.example.com/", True),
        ("http://atulya.example.com", False),
        ("https://atulya.example.com/path", False),
        ("https://user:secret@atulya.example.com", False),
    ])
    def test_telegram_miniapp_public_url_validator(self, value, good):
        item = next(i for i in installer.ITEMS if i.key == "ATULYA_PUBLIC_URL")
        assert (item.validate(value) is None) is good

    def test_dashboard_builder_checks_even_an_existing_build(self, tmp_path, monkeypatch):
        web = tmp_path / "drishti"
        (web / "dist").mkdir(parents=True)
        (web / "dist" / "index.html").write_text("stale", encoding="utf-8")
        monkeypatch.setattr(installer, "ROOT", tmp_path)
        monkeypatch.setattr(installer.shutil, "which", lambda name: f"/{name}")
        calls = []
        monkeypatch.setattr(installer.subprocess, "call", lambda cmd, cwd=None: calls.append((cmd, cwd)) or 0)
        ready, out = capture(installer.build_dashboard, False)
        assert ready and "current" in out
        assert calls and calls[0][0][-1] == str(web / "build.py")


class TestPreflightAndDoctor:
    def test_preflight_reports_python_and_pip(self):
        checks = dict((c[0], c) for c in installer.preflight())
        assert checks["Python 3.10+"][1] is True
        assert "pip" in checks

    def test_doctor_runs_end_to_end_without_a_server(self):
        ready, out = capture(installer.doctor)
        assert "config file" in out
        assert isinstance(ready, bool)
        assert "at least one brain key" in out

    def test_profiles_map_to_real_extras(self):
        assert installer.PROFILE_EXTRAS["full"] == "serve,voice,control,ambient,brain"
        assert set(installer.PROFILE_EXTRAS.values()) <= {
            "serve",
            "serve,voice",
            "serve,voice,control,ambient,brain",
            "serve,brain",
        }


class TestSummaryLine:
    def test_reports_counts_and_keeps_secrets_promised(self):
        out = installer._summary(7, 3)
        assert "7 set, 3 missing" in out
        assert "secret" in out

    def test_all_configured(self):
        out = installer._summary(10, 0)
        assert "All 10 settings" in out
        assert "missing" not in out


class TestCommandLine:
    """--doctor must exit 0 and never mutate anything."""

    def test_doctor_exits_zero(self, monkeypatch):
        import subprocess
        # This test describes the no-server case. Use an unused port instead
        # of probing a real Atulya service the developer may run on port 8501.
        monkeypatch.setenv("ATULYA_PORT", "0")

        proc = subprocess.run(
            [sys.executable, "install.py", "--doctor"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "Preflight" in proc.stdout
        assert "Health check" in proc.stdout

    def test_help_exits_zero(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, "install.py", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=60
        )
        assert proc.returncode == 0
        assert "--doctor" in proc.stdout and "--profile" in proc.stdout

    def test_doctor_does_not_write_the_env_file(self, tmp_path):
        """A status report must be read-only with respect to configuration."""
        import subprocess

        env_file = ROOT / ".env"
        before = env_file.read_bytes() if env_file.exists() else b""
        subprocess.run(
            [sys.executable, "install.py", "--doctor"], cwd=ROOT, capture_output=True, text=True, timeout=180
        )
        after = env_file.read_bytes() if env_file.exists() else b""
        assert before == after


class TestHealthProbe:
    """The health probe must authenticate, so a healthy server reads as healthy."""

    @staticmethod
    def _stub_urlopen(monkeypatch, status=200, error=None):
        import urllib.request

        seen = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake(req, timeout=0):
            seen["headers"] = {k.lower(): v for k, v in dict(getattr(req, "headers", {}) or {}).items()}
            if error:
                raise error
            resp = _Resp()
            resp.status = status
            return resp

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        return seen

    def test_probe_sends_the_dashboard_token(self, monkeypatch):
        """Without the header every healthy server looked like an anonymous 401."""

        seen = self._stub_urlopen(monkeypatch, status=200)
        monkeypatch.setenv("ATULYA_DASHBOARD_TOKEN", "probe-token-123")

        ready, out = capture(installer.doctor)

        assert seen["headers"].get("x-atulya-token") == "probe-token-123"
        assert "HTTP 200" in out
        assert ready is True

    def test_probe_flags_a_rejected_token(self, monkeypatch):
        """A server that ignores ATULYA_DASHBOARD_TOKEN must be reported, not passed."""
        import urllib.error
        import urllib.request

        self._stub_urlopen(
            monkeypatch,
            error=urllib.error.HTTPError("http://x/api/health", 401, "Unauthorized", {}, io.StringIO()),
        )
        monkeypatch.setenv("ATULYA_DASHBOARD_TOKEN", "the-configured-token")

        ready, out = capture(installer.doctor)

        assert ready is False
        assert "rejected" in out and "restart" in out

    def test_probe_without_a_token_only_notes(self, monkeypatch):
        import urllib.error

        self._stub_urlopen(
            monkeypatch,
            error=urllib.error.HTTPError("http://x/api/health", 401, "Unauthorized", {}, io.StringIO()),
        )
        monkeypatch.delenv("ATULYA_DASHBOARD_TOKEN", raising=False)

        _, out = capture(installer.doctor)

        # With no token there is nothing to test: the probe must only note that,
        # never claim the server rejected us. (The overall report still fails on
        # the separate "dashboard token" check, which is the real problem.)
        probe_line = next((row for row in out.splitlines() if "running server /api/health" in row), "")
        assert "needs a token" in probe_line
        assert "rejected" not in probe_line


class TestSecretPathGuard:
    """The file tools must refuse .env and kosh/ no matter how they are called."""

    @pytest.mark.parametrize(
        "path",
        [".env", "kosh/users.json", "kosh/jwt_secret.key", "sub/kosh/channels/channels.json", "id_rsa", ".env.local"],
    )
    def test_blocked(self, path, tmp_path, monkeypatch):
        from atulya.kaushal import _is_secret_path

        monkeypatch.chdir(tmp_path)
        assert _is_secret_path((tmp_path / path).resolve()) is True

    @pytest.mark.parametrize("path", ["README.md", "atulya/sandesh.py", ".env.example"])
    def test_allowed(self, path, tmp_path, monkeypatch):
        from atulya.kaushal import _is_secret_path

        monkeypatch.chdir(tmp_path)
        assert _is_secret_path((tmp_path / path).resolve()) is False

    def test_file_read_refuses_dotenv(self, tmp_path, monkeypatch):
        from atulya.kaushal import FileReadTool

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("GROQ_API_KEY=gsk_topsecret\n", encoding="utf-8")
        result = asyncio.run(FileReadTool().execute(path=str(tmp_path / ".env")))
        assert result.success is False
        assert "restricted" in (result.error or "")

    def test_grep_never_reads_secrets_when_scanning_repo(self, tmp_path, monkeypatch):
        from atulya.kaushal import GrepTool

        monkeypatch.chdir(tmp_path)
        (tmp_path / "public.txt").write_text("needle here", encoding="utf-8")
        secret_dir = tmp_path / "kosh"
        secret_dir.mkdir()
        (secret_dir / "users.json").write_text("needle here", encoding="utf-8")
        (tmp_path / ".env").write_text("needle here", encoding="utf-8")
        result = asyncio.run(GrepTool().execute(pattern="needle", path=str(tmp_path)))
        listed = (result.output or "").splitlines()
        assert any("public.txt" in line for line in listed)
        assert not any("kosh" in line or ".env" == Path(line).name for line in listed)

    def test_file_search_hides_secret_paths(self, tmp_path, monkeypatch):
        from atulya.kaushal import FileSearchTool

        monkeypatch.chdir(tmp_path)
        (tmp_path / "keep.md").write_text("x", encoding="utf-8")
        (tmp_path / ".env").write_text("x", encoding="utf-8")
        result = asyncio.run(FileSearchTool().execute(pattern="*", path=str(tmp_path)))
        assert "keep.md" in (result.output or "")
        assert ".env" not in (result.output or "")


class TestCodeExecuteGuard:
    """The blocked-module list used to log a warning and run anyway."""

    def test_network_import_is_refused(self, tmp_path, monkeypatch):
        from atulya.kaushal import CodeExecuteTool

        monkeypatch.chdir(tmp_path)
        result = asyncio.run(CodeExecuteTool().execute(code="import socket\nprint('hi')"))
        assert result.success is False
        assert "Blocked module" in (result.error or "")

    def test_harmless_code_still_runs(self, tmp_path, monkeypatch):
        from atulya.kaushal import CodeExecuteTool

        monkeypatch.chdir(tmp_path)
        result = asyncio.run(CodeExecuteTool().execute(code="print(2 + 2)"))
        assert result.success is True
        assert "4" in (result.output or "")


class TestCorsDefault:
    def test_no_wildcard_cors_by_default(self, monkeypatch):
        monkeypatch.delenv("ATULYA_CORS_ORIGINS", raising=False)
        from atulya import raksha

        monkeypatch.setattr(raksha, "lockdown_on", lambda: False)
        # Empty list (not None) is what sevak.py turns into "no origins at all".
        assert raksha.cors_origins() in ([], None)

    def test_explicit_origins_are_respected(self, monkeypatch):
        from atulya import raksha

        monkeypatch.setenv("ATULYA_CORS_ORIGINS", "https://a.example, https://b.example")
        assert raksha.cors_origins() == ["https://a.example", "https://b.example"]
