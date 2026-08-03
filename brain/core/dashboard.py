import threading
import time
import os
import sys
from core.event_bus import bus

class Dashboard:
    def __init__(self, goal_manager):
        self.goal_manager = goal_manager
        self.state = {
            "status": "INIT",
            "active_task": "None",
            "last_speech": "",
            "ledger_success": 0,
            "ledger_failure": 0,
            "pulse_msg": ""
        }
        self.running = False
        
        # Subscribe to events
        bus.subscribe(self.handle_event)

    def handle_event(self, event_type, payload):
        if event_type == "status":
            self.state["status"] = payload["state"]
            self.state["active_task"] = payload.get("task", "")
        elif event_type == "speech":
            self.state["last_speech"] = payload["text"]
        elif event_type == "ledger":
            if payload["outcome"] == "success":
                self.state["ledger_success"] += 1
            else:
                self.state["ledger_failure"] += 1
        elif event_type == "pulse":
            self.state["pulse_msg"] = f"Reminder for: {payload['goal']}"

    def render_loop(self):
        self.running = True
        while self.running:
            self.render()
            time.sleep(0.5)

    def render(self):
        # Clear screen (Windows 'cls', Linux 'clear')
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Fetch latest goal info live
        active_goals = self.goal_manager.get_active_goals()
        goal_text = active_goals[0]['description'] if active_goals else "No Active Goal"
        
        width = 60
        sep = "-" * width
        
        print(f"+{sep}+")
        print(f"| ATULYA TANTRA - OPERATIONAL OBSERVABILITY{' ' * (width - 39)}|")
        print(f"+{sep}+")
        print(f"| STATUS : {self.state['status']:<48} |")
        print(f"| GOAL   : {goal_text[:48]:<48} |")
        print(f"| TASK   : {self.state['active_task'][:48]:<48} |")
        print(f"+{sep}+")
        last_sp = self.state['last_speech']
        if len(last_sp) > 55: last_sp = last_sp[:52] + "..."
        print(f"| SPEECH : {last_sp:<48} |")
        print(f"+{sep}+")
        print(f"| LEDGER : SUCCESS {self.state['ledger_success']:<3} | FAILURE {self.state['ledger_failure']:<3}{' ' * 23} |")
        if self.state['pulse_msg']:
            print(f"| PULSE  : {self.state['pulse_msg'][:48]:<48} |")
        else:
            print(f"| PULSE  : {'Waiting...':<48} |")
        print(f"+{sep}+")
        print("(Press Ctrl+C to stop system)")

    def start(self):
        t = threading.Thread(target=self.render_loop, daemon=True)
        t.start()
        
    def stop(self):
        self.running = False

