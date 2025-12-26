import http.server
import socketserver
import json
import threading
import time
import os
from pathlib import Path
from core.event_bus import bus

# Global State for API
SERVER_STATE = {
    "state": "INIT",
    "active_goal": "None",
    "last_speech": "",
    "ledger": {"success": 0, "failure": 0},
    "pulse": "",
    "events": [] # Circular buffer handled by logic
}

def event_listener(event_type, payload):
    # Update Aggregate State
    if event_type == "status":
        SERVER_STATE["state"] = payload["state"]
        if "task" in payload:
            SERVER_STATE["active_task"] = payload["task"]
    elif event_type == "speech":
        SERVER_STATE["last_speech"] = payload["text"]
    elif event_type == "ledger":
        outcome = payload["outcome"]
        SERVER_STATE["ledger"][outcome] += 1
    elif event_type == "pulse":
        SERVER_STATE["pulse"] = payload.get("goal", "")
    
    # Add to event history (Last 50)
    evt = {
        "timestamp": time.time(),
        "type": event_type,
        "payload": payload
    }
    SERVER_STATE["events"].insert(0, evt)
    if len(SERVER_STATE["events"]) > 50:
        SERVER_STATE["events"].pop()

# Subscribe immediately
bus.subscribe(event_listener)

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence server logs
        return

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            # Serve index.html
            dash_path = Path(__file__).parent.parent / "dashboard" / "index.html"
            if dash_path.exists():
                with open(dash_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"Dashboard HTML not found.")
            return

        if self.path == '/api/status':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SERVER_STATE).encode())
            return

        if self.path == '/api/events':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SERVER_STATE["events"]).encode())
            return
            
        self.send_error(404)

class WebServer:
    def __init__(self, port=8000, goal_manager=None):
        self.port = port
        self.goal_manager = goal_manager
        self.server = None
        self.thread = None

    def start(self):
        handler = DashboardHandler
        # We need to inject GoalManager logic updates if we want polling
        # But EventBus pushes updates, so we are good.
        # Except 'Active Goal' which changes internally in GoalManager?
        # Engine doesn't emit 'goal_change' yet?
        # We can poll GoalManager inside the Handler if we pass it? 
        # Hard with standard Handler class.
        # Better: Polling thread updates SERVER_STATE["active_goal"]
        if self.goal_manager:
            t = threading.Thread(target=self._poll_goals, daemon=True)
            t.start()
        
        try:
            self.server = http.server.ThreadingHTTPServer(('localhost', self.port), handler)
            print(f"[WEB] Dashboard active at http://localhost:{self.port}")
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
        except OSError as e:
            print(f"[WEB] Port {self.port} busy or error: {e}")

    def _poll_goals(self):
        while True:
            if self.goal_manager:
                goals = self.goal_manager.get_active_goals()
                SERVER_STATE["active_goal"] = goals[0]['description'] if goals else "None"
            time.sleep(1)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

