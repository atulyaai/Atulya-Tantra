import os
import sys
import threading
import time
import logging
from core.engine import Engine
from core.dashboard import Dashboard
from core.web_server import WebServer
from core.governance import Governor
import shutil

# Configure Clean Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Launcher")

def cleanup():
    """Removes __pycache__ and redundant test artifacts."""
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))
        for f in files:
            if f.endswith(".pyc") or f.endswith(".pyo"):
                os.remove(os.path.join(root, f))

def start_web_server():
    """Starts the Web Dashboard on Port 8000."""
    try:
        server = WebServer(port=8000)
        logger.info("[UI] Web Dashboard available at http://localhost:8000")
        server.start()
    except Exception as e:
        logger.error(f"Web Server failed: {e}")

def run_engine():
    """Initializes and runs the Core Engine."""
    try:
        cleanup()
        governor = Governor()
        jarvis = Engine(None, governor) # memory=None as engine manages its organs
        logger.info("[JARVIS] Logic Pulse Active. Standing by.")
        jarvis.presence_loop()
        
    except Exception as e:
        logger.error(f"Engine Crash: {e}")

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      ATULYA TANTRA — JARVIS ACTIVATION")
    print("="*50 + "\n")
    
    # Check for models first
    if not os.path.exists(".env"):
        print("[WARNING] .env missing. Run: python tools/bootstrap.py")
        time.sleep(2)

    # 1. Launch UI (Web) as sidecar
    ui_thread = threading.Thread(target=start_web_server, daemon=True)
    ui_thread.start()
    
    # 2. Launch TUI Dashboard (Passive) as sidecar
    # Dashboard() would block if it's a real TUI (like curses), 
    # but currently it's a simple logger.
    
    # 3. Launch Engine (Blocks)
    run_engine()
