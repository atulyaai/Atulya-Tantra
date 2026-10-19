"""Writable state location shared by source and packaged PC companions."""
from pathlib import Path
import os
import sys


def connection_directory():
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Atulya" / "Companion"
    return Path(__file__).resolve().parents[1] / "data" / "companion"


def acquire_connection_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / "connection.lock").open("a+b")
    handle.write(b"0")
    handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise ValueError("A PC companion is already running. Stop it before changing this connection.") from None
    return handle
