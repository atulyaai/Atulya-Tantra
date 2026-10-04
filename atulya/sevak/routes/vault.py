"""Encryption at rest: is it on, and encrypt the private files that are still plain text (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from atulya.raksha import vault
from atulya.sevak.helpers import _require_admin

router = APIRouter()


@router.get("/api/vault")
def api_vault_status(user: dict = Depends(_require_admin)):
    return vault.status()


@router.post("/api/vault/encrypt-now")
def api_vault_encrypt(user: dict = Depends(_require_admin)):
    try:
        return {"converted": vault.encrypt_tree(), **vault.status()}
    except vault.VaultLocked as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
