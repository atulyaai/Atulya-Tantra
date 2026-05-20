"""NP-DNA Dashboard Automation Routes.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from fastapi import APIRouter, Header, Request

from atulya.dashboard.state import OUTPUTS_DIR
from atulya.dashboard.helpers import _require_admin, _check_request_origin

logger = logging.getLogger("atulya.dashboard.routes.automation")
router = APIRouter()

AUTOMATION_CONFIG = OUTPUTS_DIR / "automation_config.json"


@router.get("/api/automation/config")
def get_automation_config(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    if AUTOMATION_CONFIG.exists():
        return json.loads(AUTOMATION_CONFIG.read_text(encoding="utf-8"))
    return {"webhook_url": "", "webhook_auth": "", "slack_webhook": ""}


@router.post("/api/automation/config")
def save_automation_config(
    body: dict,
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    config = {
        "webhook_url": str(body.get("webhook_url", "")),
        "webhook_auth": str(body.get("webhook_auth", "")),
        "slack_webhook": str(body.get("slack_webhook", "")),
    }
    AUTOMATION_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    AUTOMATION_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"status": "saved", "config": config}
