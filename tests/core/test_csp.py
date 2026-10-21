"""AUDIT S4: a real CSP (scripts and connections from this origin only) and no inline scripts in the page."""
import asyncio
import re
from pathlib import Path

import httpx

from atulya.server import CONTENT_SECURITY_POLICY, create_app
from atulya.settings import Settings

WEBUI = Path(__file__).resolve().parents[2] / "webui"


def _directives(policy: str) -> dict[str, list[str]]:
    return {part.split()[0]: part.split()[1:] for part in (p.strip() for p in policy.split(";")) if part}


def test_policy_is_strict():
    rules = _directives(CONTENT_SECURITY_POLICY)
    assert rules["default-src"] == ["'self'"]
    assert rules["connect-src"] == ["'self'"]
    assert rules["script-src"][0] == "'self'"
    assert "'unsafe-inline'" not in rules["script-src"] and "'unsafe-eval'" not in rules["script-src"]
    assert all(src.startswith("https://") or src in {"'self'", "'wasm-unsafe-eval'"} for src in rules["script-src"])
    assert rules["object-src"] == ["'none'"] and rules["frame-ancestors"] == ["'none'"]


def test_page_has_no_inline_scripts_or_handlers():
    html = (WEBUI / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<script\b[^>]*>", html):
        assert "src=" in tag, tag
    assert not re.search(r"\son[a-z]+\s*=", html), "inline event handler attribute"


def test_header_is_sent(project_temp_dir):
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
                        models_dir=project_temp_dir / "models", model_provider="", model_name="",
                        model_base_url="", model_api_key="")
    app = create_app(settings)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            return await client.get("/api/health")

    assert asyncio.run(run()).headers["content-security-policy"] == CONTENT_SECURITY_POLICY
