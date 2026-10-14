"""Opt-in outbound laptop and PC companion.

Delegates to the unified tools.device_companion module.
Set ATULYA_AGENT_URL, ATULYA_AGENT_TOKEN (from Devices pairing) and optionally
ATULYA_AGENT_FOLDER (one approved folder). Stop the process or revoke its device
to disconnect.
"""
from tools.device_companion import execute, main

__all__ = ["execute", "main"]

if __name__ == "__main__":
    main()
