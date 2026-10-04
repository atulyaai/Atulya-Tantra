"""Backward-compatibility shim — lockdown functions now live in atulya.security."""
from atulya.security import bind_host, cors_origins, lockdown_on  # noqa: F401
