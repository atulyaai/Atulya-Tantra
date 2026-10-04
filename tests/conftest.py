"""Global test configuration."""
from __future__ import annotations

import os
import tempfile

# Keep assistant state (routines, profiles, tokens…) out of the working tree.
_STATE = tempfile.mkdtemp(prefix="atulya-test-state-")
os.environ.setdefault("ATULYA_AGENT_DATA_DIR", os.path.join(_STATE, "agent"))
os.environ.setdefault("ATULYA_ROUTINES_FILE", os.path.join(_STATE, "routines.json"))
os.environ.setdefault("ATULYA_PROFILE_DIR", os.path.join(_STATE, "profiles"))
os.environ.setdefault("ATULYA_GOOGLE_DIR", os.path.join(_STATE, "google"))
os.environ.setdefault("ATULYA_SNAPSHOT_DIR", os.path.join(_STATE, "snapshots"))
os.environ.setdefault("ATULYA_JWT_SECRET_FILE", os.path.join(_STATE, "jwt_secret.key"))
