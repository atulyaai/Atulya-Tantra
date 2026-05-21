"""NP-DNA Dashboard Main Application.

Assembles the FastAPI application by mounting sub-routers, serving the
HTML front-end, and starting the web server.
"""
from __future__ import annotations
import logging
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from atulya.dashboard.state import _ROOT, ADMIN_TOKEN, ADMIN_TOKEN_SOURCE
from atulya.dashboard.routes import auth, system, model, train, chat, cortex, automation, openai

logger = logging.getLogger("atulya.dashboard.app")

app = FastAPI(title="NP-DNA Command Center")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-Atulya-Token", "Content-Type"],
)

# Register all modular routers
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(model.router)
app.include_router(train.router)
app.include_router(chat.router)
app.include_router(cortex.router)
app.include_router(automation.router)
app.include_router(openai.router)


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    p = _ROOT / "atulya" / "dashboard_ui.html"
    if not p.exists():
        return HTMLResponse("<h1>UI not found</h1>")
    
    content = p.read_text(encoding="utf-8")
    response = HTMLResponse(content)
    # Prevent browser caching of UI
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def main():
    print("\n  NP-DNA Command Center")
    print("  http://localhost:8501\n")
    if not os.environ.get("ATULYA_DASHBOARD_TOKEN"):
        print(f"  Session token: {ADMIN_TOKEN}")
        print(f"  Token source: {ADMIN_TOKEN_SOURCE}\n")
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="warning")


if __name__ == "__main__":
    main()
