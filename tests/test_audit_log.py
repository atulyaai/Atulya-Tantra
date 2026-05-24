"""Tests for TamperEvidentLog — hash-chained audit logging."""

import os
import tempfile
import json


class TestTamperEvidentLog:
    """Tests for integrity-verified audit log using SHA-256 chaining."""

    def test_append(self):
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            log = TamperEvidentLog(os.path.join(tmp, "audit.log"))
            entry = log.append("user.login", {"user": "admin", "ip": "127.0.0.1"})
            assert entry.action == "user.login"
            assert entry.entry_hash
            assert entry.entry_hash != "0" * 64

    def test_multiple_entries(self):
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            log = TamperEvidentLog(os.path.join(tmp, "audit.log"))
            e1 = log.append("action1", {"x": 1})
            e2 = log.append("action2", {"x": 2})
            e3 = log.append("action3", {"x": 3})
            assert e1.previous_hash == "0" * 64
            assert e2.previous_hash == e1.entry_hash
            assert e3.previous_hash == e2.entry_hash
            assert e1.entry_hash != e2.entry_hash
            assert e2.entry_hash != e3.entry_hash

    def test_verify_integrity(self):
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            log = TamperEvidentLog(os.path.join(tmp, "audit.log"))
            log.append("cmd.exec", {"cmd": "ls"})
            log.append("file.read", {"path": "/etc/passwd"})
            assert log.verify() is True

    def test_verify_fails_after_tamper(self):
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit.log")
            log = TamperEvidentLog(log_path)
            log.append("safe", {"msg": "original"})
            # Tamper the file directly
            with open(log_path, "r") as f:
                content = f.read()
            content = content.replace("original", "tampered")
            with open(log_path, "w") as f:
                f.write(content)
            assert log.verify() is False

    def test_verify_no_file(self):
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            log = TamperEvidentLog(os.path.join(tmp, "nonexistent.log"))
            assert log.verify() is True

    def test_len(self):
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            log = TamperEvidentLog(os.path.join(tmp, "audit.log"))
            assert len(log) == 0
            log.append("a", {})
            assert len(log) == 1
            log.append("b", {})
            assert len(log) == 2

    def test_load_last_hash_from_existing(self):
        """Re-initializing should restore last hash from existing log."""
        from tantra.core.audit_log import TamperEvidentLog
        with tempfile.TemporaryDirectory() as tmp:
            lp = os.path.join(tmp, "audit.log")
            log1 = TamperEvidentLog(lp)
            e1 = log1.append("first", {"v": 1})
            log2 = TamperEvidentLog(lp)
            e2 = log2.append("second", {"v": 2})
            assert e2.previous_hash == e1.entry_hash
