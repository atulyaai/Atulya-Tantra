"""Writable state location shared by source and packaged PC companions."""
from pathlib import Path
import os
import sys


def connection_directory():
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Atulya" / "Companion"
    return Path(__file__).resolve().parents[1] / "data" / "companion"
