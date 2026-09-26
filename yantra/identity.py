"""Who a tool is acting for.

Tools run deep inside the brain's loop, far from the web request, but some of
them are personal: "check my email" must read *your* Gmail, not someone
else's. The cognitive kernel sets ``current_user`` for the duration of each
request; personal tools read it.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

current_user: ContextVar[str] = ContextVar("atulya_current_user", default="")


@contextmanager
def acting_as(user: str) -> Iterator[None]:
    token = current_user.set(user or "")
    try:
        yield
    finally:
        current_user.reset(token)
