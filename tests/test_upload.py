"""Tests for upload route — file upload, list, download, delete."""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile


class TestUploadRoute:
    @pytest.fixture
    def mock_auth(self):
        with patch("drishti.dashboard.routes.upload._require_auth") as m:
            m.return_value = {"username": "testuser", "role": "user"}
            yield m

    @pytest.fixture
    def mock_uuid(self):
        with patch("uuid.uuid4") as m:
            m.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
            yield m

    @pytest.mark.asyncio
    async def test_upload_valid_file(self, tmp_path, mock_auth, mock_uuid):
        from drishti.dashboard.routes.upload import api_upload
        import drishti.dashboard.routes.upload as upload_mod
        upload_mod.UPLOAD_DIR = tmp_path

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"hello world")

        result = await api_upload(file=mock_file, token="token")
        assert result["ok"] is True
        assert result["filename"] == "test.txt"
        assert result["size"] == 11
        saved = tmp_path / "testuser" / "12345678123456781234567812345678.txt"
        assert saved.read_bytes() == b"hello world"

    @pytest.mark.asyncio
    async def test_upload_blocked_type(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.upload import api_upload
        import drishti.dashboard.routes.upload as upload_mod
        upload_mod.UPLOAD_DIR = tmp_path

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "evil.exe"
        mock_file.content_type = "application/x-msdownload"
        mock_file.read = AsyncMock(return_value=b"bad")

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match=r"File type.*not allowed"):
            await api_upload(file=mock_file, token="token")

    @pytest.mark.asyncio
    async def test_list_files(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.upload import api_list_files
        import drishti.dashboard.routes.upload as upload_mod
        upload_mod.UPLOAD_DIR = tmp_path

        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)
        (user_dir / "a.txt").write_text("aaa")
        (user_dir / "b.txt").write_text("bbb")

        result = await api_list_files(token="token")
        assert len(result["files"]) == 2

    @pytest.mark.asyncio
    async def test_list_files_empty(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.upload import api_list_files
        import drishti.dashboard.routes.upload as upload_mod
        upload_mod.UPLOAD_DIR = tmp_path

        result = await api_list_files(token="token")
        assert result["files"] == []

    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.upload import api_delete_file
        import drishti.dashboard.routes.upload as upload_mod
        upload_mod.UPLOAD_DIR = tmp_path

        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)
        f = user_dir / "1234.txt"
        f.write_text("data")

        result = await api_delete_file(file_id="1234.txt", token="token")
        assert result["ok"] is True
        assert not f.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.upload import api_delete_file
        import drishti.dashboard.routes.upload as upload_mod
        upload_mod.UPLOAD_DIR = tmp_path
        (tmp_path / "testuser").mkdir(parents=True)

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="not found"):
            await api_delete_file(file_id="nonexistent.txt", token="token")
