from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import asyncio
import threading
import time
from pathlib import Path
from core.event_bus import bus

app = FastAPI(title="Atulya Tantra Dashboard API")

# Global State for API (Internal Cache)
SERVER_STATE = {
    "state": "INIT",
    "active_goal": "None",
    "last_speech": "",
    "ledger": {"success": 0, "failure": 0},
    "pulse": "",
    "events": []  # Last 50 events
}

# WebSocket connections
active_connections: list[WebSocket] = []

async def broadcast_event(event_type: str, payload: dict):
    """Notify all connected WebSockets of a new event."""
    message = json.dumps({
        "timestamp": time.time(),
        "type": event_type,
        "payload": payload
    })
    
    # Update internal state cache
    if event_type == "status":
        SERVER_STATE["state"] = payload["state"]
        if "task" in payload:
            SERVER_STATE["active_task"] = payload["task"]
    elif event_type == "speech":
        SERVER_STATE["last_speech"] = payload["text"]
    elif event_type == "ledger":
        outcome = payload["outcome"]
        SERVER_STATE["ledger"][outcome] += 1
    
    # Add to history
    evt = {
        "timestamp": time.time(),
        "type": event_type,
        "payload": payload
    }
    SERVER_STATE["events"].insert(0, evt)
    if len(SERVER_STATE["events"]) > 50:
        SERVER_STATE["events"].pop()

    # Broadcast
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception:
            # Handle stale connections
            active_connections.remove(connection)

def event_listener(event_type, payload):
    """Bridge EventBus to Asyncio Loop."""
    # Since EventBus emits from sync threads, we need to bridge to the server's loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(broadcast_event(event_type, payload))

# Subscribe immediately
bus.subscribe(event_listener)

@app.get("/")
async def get_dashboard():
    dash_path = Path(__file__).parent.parent / "dashboard" / "index.html"
    if dash_path.exists():
        with open(dash_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="Dashboard HTML not found.")

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=SERVER_STATE)

@app.get("/api/events")
async def get_events():
    return JSONResponse(content=SERVER_STATE["events"])

@app.post("/api/command")
async def post_command(data: dict):
    command = data.get("command")
    if not command:
        return JSONResponse(content={"error": "No command provided"}, status_code=400)
    
    # Bridge to the Engine
    # Note: In the future, we will have a persistent Engine instance
    # For now, we emit an event that the Engine might be listening for if in presence loop
    bus.emit("external_command", {"command": command})
    return JSONResponse(content={"status": "command_received", "command": command})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

class WebServer:
    def __init__(self, port=8000, goal_manager=None):
        self.port = port
        self.goal_manager = goal_manager
        self.config = uvicorn.Config(app=app, host="0.0.0.0", port=self.port, log_level="info")
        self.server = uvicorn.Server(self.config)
        self.thread = None

    def start(self):
        print(f"[WEB] FastAPI Dashboard active at http://localhost:{self.port}")
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        
        if self.goal_manager:
            threading.Thread(target=self._poll_goals, daemon=True).start()

    def _poll_goals(self):
        while True:
            if self.goal_manager:
                goals = self.goal_manager.get_active_goals()
                SERVER_STATE["active_goal"] = goals[0]['description'] if goals else "None"
            time.sleep(1)

    def stop(self):
        self.server.should_exit = True
