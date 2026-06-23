"""Tests for notifications route — subscribe, unsubscribe, test."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestNotifications:
    @pytest.fixture
    def mock_auth(self):
        with patch("drishti.dashboard.routes.notifications._require_auth") as m:
            m.return_value = {"username": "testuser"}
            yield m

    @pytest.fixture
    def mock_admin(self):
        with patch("drishti.dashboard.helpers._require_admin") as m:
            m.return_value = {"username": "admin", "role": "admin"}
            yield m

    def test_subscribe(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.notifications import subscribe
        import drishti.dashboard.routes.notifications as notif_mod
        notif_mod.SUBS_FILE = tmp_path / "subs.json"

        result = subscribe({"subscription": {"endpoint": "https://push.test"}}, token="t")
        assert result == {"ok": True}

        data = json.loads((tmp_path / "subs.json").read_text())
        assert data["testuser"] == [{"endpoint": "https://push.test"}]

    def test_subscribe_no_subscription(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.notifications import subscribe
        import drishti.dashboard.routes.notifications as notif_mod
        notif_mod.SUBS_FILE = tmp_path / "subs.json"

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="subscription"):
            subscribe({}, token="t")

    def test_unsubscribe(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.notifications import unsubscribe
        import drishti.dashboard.routes.notifications as notif_mod
        subs_file = tmp_path / "subs.json"
        notif_mod.SUBS_FILE = subs_file
        subs_file.write_text(json.dumps({"testuser": [{"endpoint": "https://push.test"}]}))

        result = unsubscribe({"subscription": {"endpoint": "https://push.test"}}, token="t")
        assert result == {"ok": True}
        data = json.loads(subs_file.read_text())
        assert data["testuser"] == []

    def test_unsubscribe_no_file(self, tmp_path, mock_auth):
        from drishti.dashboard.routes.notifications import unsubscribe
        import drishti.dashboard.routes.notifications as notif_mod
        notif_mod.SUBS_FILE = tmp_path / "subs.json"

        result = unsubscribe({"subscription": {"endpoint": "x"}}, token="t")
        assert result == {"ok": True}

    def test_test_notification(self, tmp_path, mock_auth, mock_admin):
        from drishti.dashboard.routes.notifications import test_notification
        import drishti.dashboard.routes.notifications as notif_mod
        notif_mod.SUBS_FILE = tmp_path / "subs.json"

        result = test_notification({"title": "Hi", "message": "Test"}, token="t")
        assert result.status_code == 200
        body = json.loads(result.body)
        assert body["title"] == "Hi"
        assert body["message"] == "Test"
