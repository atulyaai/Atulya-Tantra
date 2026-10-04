"""Backward-compatibility shim — lockdown functions now live in atulya.raksha.security."""
from atulya.raksha.security import bind_host, cors_origins, lockdown_on  # noqa: F401
