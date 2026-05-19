"""NP-DNA Dashboard Main Application.

Assembles the FastAPI application by mounting sub-routers, serving the
HTML front-end, and starting the web server.
"""
from __future__ import annotations
import logging
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from atulya.dashboard.state import _ROOT, ADMIN_TOKEN, ADMIN_TOKEN_SOURCE
from atulya.dashboard.routes import auth, system, model, train, chat, cortex

logger = logging.getLogger("atulya.dashboard.app")

app = FastAPI(title="NP-DNA Command Center")

# Register all modular routers
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(model.router)
app.include_router(train.router)
app.include_router(chat.router)
app.include_router(cortex.router)


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    p = _ROOT / "atulya" / "dashboard_ui.html"
    return HTMLResponse(
        p.read_text(encoding="utf-8") if p.exists() else "<h1>UI not found</h1>"
    )


def main():
    print("\n  NP-DNA Command Center")
    print("  http://localhost:8501\n")
    if not os.environ.get("ATULYA_DASHBOARD_TOKEN"):
        print(f"  Session token: {ADMIN_TOKEN}")
        print(f"  Token source: {ADMIN_TOKEN_SOURCE}\n")
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="warning")


if __name__ == "__main__":
    main()
