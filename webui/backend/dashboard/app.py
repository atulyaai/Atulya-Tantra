"""FastAPI dashboard app."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from webui.backend.dashboard.helpers import _checkpoint_index, _load_cached_model
from webui.backend.dashboard.routes import auth, automation, chat, cortex, model, openai, system, train

logger = logging.getLogger(__name__)


def _warm_latest_model() -> None:
    try:
        path = _checkpoint_index().get("latest")
        if path:
            _load_cached_model(path)
    except Exception as exc:
        logger.warning("Dashboard model warmup skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_latest_model, daemon=True).start()
    yield


app = FastAPI(title="Atulya Tantra Dashboard", lifespan=lifespan)

for module in (auth, system, model, train, chat, cortex, automation, openai):
    app.include_router(module.router)


dist = Path(__file__).resolve().parents[2] / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="webui")


