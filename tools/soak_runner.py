import sys
import threading
import time
import json
import logging
import os
import subprocess
import datetime
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine import Engine
from core.memory_manager import MemoryManager
from core.governor import Governor
from core.event_bus import bus

# CONFIG
DEFAULT_DURATION_HOURS = 24
METRICS_FILE = "logs/soak_metrics.json"

class SoakMonitor:
    def __init__(self, duration_hours):
        self.duration_seconds = float(duration_hours) * 3600
        self.start_time = time.time()
        self.running = True
        self.metrics_history = []
        
        # System Components
        self.memory = MemoryManager()
        self.governor = Governor(self.memory)
        self.engine = Engine(self.memory, self.governor)
        
        # Internal Stats
        self.stat_pulses = 0
        self.stat_speech = 0
        self.stat_ledger_size = 0
        
        # Subscribe to EventBus for tracking
        bus.subscribe(self.handle_event)
        
        # Initialize Metrics File
        if not os.path.exists("logs"): os.makedirs("logs")
        with open(METRICS_FILE, "w") as f:
            json.dump([], f)

        # Start Web Dashboard
        try:
            from core.web_server import WebServer
            self.web_server = WebServer(port=8000, goal_manager=self.engine.goal_manager)
            self.web_server.start()
        except Exception as e:
            print(f"Warning: Web Dashboard failed: {e}")
            self.web_server = None

    def handle_event(self, event_type, payload):
        if event_type == "pulse":
            self.stat_pulses += 1
        elif event_type == "speech":
            self.stat_speech += 1
        elif event_type == "ledger":
            self.stat_ledger_size += 1

    def get_memory_usage(self):
        """Get Memory Usage in MB using tasklist (Windows)"""
        try:
            pid = os.getpid()
            output = subprocess.check_output(f"tasklist /FI \"PID eq {pid}\" /FO CSV /NH", shell=True)
            # output format: "Image Name","PID","Session Name","Session#","Mem Usage"
            # "python.exe","1234","Console","1","24,560 K"
            line = output.decode().strip()
            if not line: return 0.0
            
            parts = line.split('","')
            if len(parts) < 5: return 0.0
            
            mem_str = parts[-1].replace('"', '').replace(' K', '').replace(',', '')
            return float(mem_str) / 1024.0 # KB to MB
        except Exception:
            return 0.0

    def run_engine_thread(self):
        # Silence standard outputs for TUI cleanliness?
        # Ideally yes, but Engine prints a lot.
        # We'll rely on Dashboard-style TUI refreshing to overwrite it, 
        # or we accept mixed output.
        # For a clean Soak Test TUI, we should suppress stdout from Engine.
        # But logging handlers still write to files.
        try:
            # We use a simulator to inject stimulus if needed, but for soak we mostly wait.
            self.engine.presence_loop(simulator=None)
        except Exception as e:
            logging.error(f"Engine Crash: {e}")

    def render_tui(self, elapsed, memory_mb, threads):
        # Progress Bar
        pct = min(1.0, elapsed / self.duration_seconds)
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "=" * filled + "." * (bar_len - filled)
        
        remaining = self.duration_seconds - elapsed
        rem_str = str(datetime.timedelta(seconds=int(remaining)))
        el_str = str(datetime.timedelta(seconds=int(elapsed)))
        
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"SOAK TEST — {self.duration_seconds/3600:.1f} HOURS")
        print(f"[{bar}] {pct*100:.1f}%")
        print(f"Elapsed: {el_str} | Remaining: {rem_str}")
        print("-" * 40)
        print(f"STATE       : {self.engine.current_task_context if self.engine.current_task_context else 'IDLE/RUNNING'}")
        print(f"MEMORY      : {memory_mb:.1f} MB")
        print(f"THREADS     : {threads}")
        print("-" * 40)
        print(f"SPEECH EVTS : {self.stat_speech}")
        print(f"PULSES      : {self.stat_pulses}")
        print(f"LEDGER      : {self.stat_ledger_size} (Session)")
        try:
             # Total persistent ledger check?
             pass
        except: pass
        print("-" * 40)
        print("Press Ctrl+C to Stop Test")

    def start(self):
        print(">>> Initializing Soak Test...")
        
        # 1. Start Engine Thread
        t_eng = threading.Thread(target=self.run_engine_thread, daemon=True)
        t_eng.start()
        
        # 2. Monitor Loop
        try:
            while self.running and (time.time() - self.start_time < self.duration_seconds):
                elapsed = time.time() - self.start_time
                
                # Metrics
                mem = self.get_memory_usage()
                th_count = threading.active_count()
                
                # Log Metric
                metric = {
                    "timestamp": time.time(),
                    "elapsed": elapsed,
                    "memory_mb": mem,
                    "threads": th_count,
                    "pulses": self.stat_pulses,
                    "speech": self.stat_speech
                }
                self.metrics_history.append(metric)
                
                # Append to file (slow but safe)
                with open(METRICS_FILE, "r+") as f:
                    try:
                        current = json.load(f)
                    except: current = []
                    current.append(metric)
                    f.seek(0)
                    json.dump(current, f)
                
                # Render
                self.render_tui(elapsed, mem, th_count)
                
                time.sleep(60) # Update every minute
                
        except KeyboardInterrupt:
            print("\n[TEST STOPPED BY USER]")
        finally:
            print("\n>>> Soak Test Complete.")
            print(f"Final Duration: {str(datetime.timedelta(seconds=int(time.time() - self.start_time)))}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        hours = float(sys.argv[1])
    else:
        hours = DEFAULT_DURATION_HOURS
    
    monitor = SoakMonitor(hours)
    monitor.start()
