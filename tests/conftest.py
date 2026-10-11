from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# Tests must never load real speech or chat models in the background.
os.environ["ATULYA_PRELOAD"] = "0"


@pytest.fixture
def project_temp_dir():
    """Create disposable test data inside the project workspace."""
    with TemporaryDirectory(prefix="atulya-test-", dir=Path.cwd()) as directory:
        yield Path(directory)


def authenticate_test_admin(client, app) -> None:
    """Issue a test-only server session for API route tests."""
    token = app.state.auth_store.create_session("admin")
    client.cookies.set("atulya_session", token)
