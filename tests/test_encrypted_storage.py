"""Tests for EncryptedStorage — encrypt, decrypt, delete, key management."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from cryptography.fernet import Fernet
    _KEY = Fernet.generate_key().decode()
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


class TestEncryptedStorage:
    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_encrypt_and_decrypt(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        store = EncryptedStorage(tmp_path, key=_KEY)
        path = store.encrypt({"secret": "value"}, "mysecret")
        assert path.exists()
        assert path.suffix == ".enc"

        data = store.decrypt("mysecret")
        assert data == {"secret": "value"}

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_decrypt_missing(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        store = EncryptedStorage(tmp_path, key=_KEY)
        assert store.decrypt("nonexistent") is None

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_delete(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        store = EncryptedStorage(tmp_path, key=_KEY)
        store.encrypt({"data": "x"}, "todelete")
        assert store.delete("todelete") is True
        assert store.delete("todelete") is False

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_delete_nonexistent(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        store = EncryptedStorage(tmp_path, key=_KEY)
        assert store.delete("nothing") is False

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_list_keys(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        store = EncryptedStorage(tmp_path, key=_KEY)
        store.encrypt({"a": 1}, "key_a")
        store.encrypt({"b": 2}, "key_b")

        keys = store.list_keys()
        assert sorted(keys) == ["key_a", "key_b"]

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_list_keys_empty(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        store = EncryptedStorage(tmp_path, key=_KEY)
        assert store.list_keys() == []

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_key_from_env_var(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        with patch("os.environ.get") as env:
            env.return_value = _KEY
            store = EncryptedStorage(tmp_path)
            store.encrypt({"x": "y"}, "test")
            assert store.decrypt("test") == {"x": "y"}

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not available")
    def test_key_file_persistence(self, tmp_path):
        from yantra.capabilities.encrypted_storage import EncryptedStorage

        s1 = EncryptedStorage(tmp_path, key=_KEY)
        s1.encrypt({"persist": "me"}, "p")

        s2 = EncryptedStorage(tmp_path, key=_KEY)
        assert s2.decrypt("p") == {"persist": "me"}
