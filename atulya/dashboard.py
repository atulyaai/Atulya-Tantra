"""NP-DNA Command Center — Production Admin Panel.

Backward-compatible entry point for the Command Center Dashboard.
Redirects execution and imports to atulya.dashboard.app.
"""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from atulya.dashboard.app import app, main

if __name__ == "__main__":
    main()
