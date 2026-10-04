"""Tests for OpenAI-compatible route — model listing."""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestOpenAIRoute:
    def test_list_models(self):
        from atulya.sevak.routes.openai import list_models

        with patch("atulya.sevak.helpers.ADMIN_TOKEN", "test-token"):
            with patch("atulya.sevak.routes.openai._model_registry") as reg:
                reg.return_value = [{"id": "model-1", "object": "model"}, {"id": "model-2", "object": "model"}]
                result = list_models(authorization="Bearer test-token")

        assert result["object"] == "list"
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "model-1"

    def test_list_models_no_auth(self):
        from atulya.sevak.routes.openai import list_models
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            list_models(authorization=None)
        assert exc.value.status_code == 401

    def test_list_models_bad_auth(self):
        from atulya.sevak.routes.openai import list_models
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            list_models(authorization="Invalid")
        assert exc.value.status_code == 401
