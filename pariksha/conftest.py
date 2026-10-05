"""Global test configuration."""
from __future__ import annotations

import os
import tempfile

import pytest

# Keep assistant state (routines, profiles, tokens…) out of the working tree.
_STATE = tempfile.mkdtemp(prefix="atulya-test-state-")
os.environ.setdefault("ATULYA_AGENT_DATA_DIR", os.path.join(_STATE, "agent"))
os.environ.setdefault("ATULYA_DEVICES_DIR", os.path.join(_STATE, "devices"))
os.environ.setdefault("ATULYA_ROUTINES_FILE", os.path.join(_STATE, "routines.json"))
os.environ.setdefault("ATULYA_PROFILE_DIR", os.path.join(_STATE, "profiles"))
os.environ.setdefault("ATULYA_GOOGLE_DIR", os.path.join(_STATE, "google"))
os.environ.setdefault("ATULYA_SNAPSHOT_DIR", os.path.join(_STATE, "snapshots"))
os.environ.setdefault("ATULYA_SIMULATED_HOME", "on")  # tests use the pretend lights; real use never does
os.environ.setdefault("ATULYA_JWT_SECRET_FILE", os.path.join(_STATE, "jwt_secret.key"))


@pytest.fixture(autouse=True)
def _isolate_http_rate_limit():
    """Give each API test a fresh client bucket; keep explicit limiter tests self-contained."""
    from atulya.sevak import _CREDENTIAL_STORE, _RATE_STORE

    _RATE_STORE.clear()
    _CREDENTIAL_STORE.clear()
    yield
    _RATE_STORE.clear()
    _CREDENTIAL_STORE.clear()
