"""Tests for EncryptedStorage â€” encryption/decryption of values and DB."""

import tempfile
import os
import sqlite3
import pytest


class TestEncryptedStorage:
    """Tests for EncryptedStorage using authenticated encryption."""

    def test_requires_key(self):
        from tantra.core.encryption import EncryptedStorage
        with pytest.raises(ValueError):
            EncryptedStorage()

    def test_custom_key(self):
        from tantra.core.encryption import EncryptedStorage
        es = EncryptedStorage(key="my-secret-key-42")
        assert es is not None

    def test_encrypt_decrypt_roundtrip(self):
        from tantra.core.encryption import EncryptedStorage
        es = EncryptedStorage(key="test-key")
        original = "my-sensitive-data-123"
        encrypted = es.encrypt_value(original)
        assert encrypted != original
        assert isinstance(encrypted, str)
        decrypted = es.decrypt_value(encrypted)
        assert decrypted == original

    def test_different_keys_produce_different_ciphertext(self):
        from tantra.core.encryption import EncryptedStorage
        es1 = EncryptedStorage(key="key-1")
        es2 = EncryptedStorage(key="key-2")
        original = "hello world"
        c1 = es1.encrypt_value(original)
        c2 = es2.encrypt_value(original)
        assert c1 != c2

    def test_encrypt_empty_string(self):
        from tantra.core.encryption import EncryptedStorage
        es = EncryptedStorage(key="test")
        encrypted = es.encrypt_value("")
        decrypted = es.decrypt_value(encrypted)
        assert decrypted == ""

    def test_decrypt_wrong_key_fails(self):
        from tantra.core.encryption import EncryptedStorage
        es = EncryptedStorage(key="correct-key")
        encrypted = es.encrypt_value("secret")
        es2 = EncryptedStorage(key="wrong-key")
        with pytest.raises(Exception):
            es2.decrypt_value(encrypted)

    def test_encrypt_db_creates_enc_prefix(self):
        from tantra.core.encryption import EncryptedStorage
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            # Create a DB with sensitive column
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE secrets (id INTEGER, api_key TEXT, name TEXT)")
            conn.execute("INSERT INTO secrets VALUES (1, 'sk-12345', 'test')")
            conn.commit()
            conn.close()

            es = EncryptedStorage(key="db-key")
            es.encrypt_db(db_path)

            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT api_key FROM secrets WHERE id=1").fetchone()
            assert row[0].startswith("enc:")
            conn.close()

    def test_decrypt_db_restores_values(self):
        from tantra.core.encryption import EncryptedStorage
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE config (id INTEGER, api_token TEXT, label TEXT)")
            conn.execute("INSERT INTO config VALUES (1, 'tok-abc', 'myconfig')")
            conn.commit()
            conn.close()

            es = EncryptedStorage(key="db-key")
            es.encrypt_db(db_path)
            es.decrypt_db(db_path)

            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT api_token FROM config WHERE id=1").fetchone()
            assert row[0] == "tok-abc"
            conn.close()

    def test_encrypt_nonexistent_db(self):
        from tantra.core.encryption import EncryptedStorage
        es = EncryptedStorage(key="test")
        # Should not crash
        es.encrypt_db("/nonexistent/path/db.sqlite")
        es.decrypt_db("/nonexistent/path/db.sqlite")
