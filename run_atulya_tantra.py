import logging
import sys
from core.memory_manager import MemoryManager
from core.governor import Governor
from core.engine import Engine
from tools.maintenance import MaintenanceTool
from internal.simulator import StimulusInjector

# Configure Presence Telemetry
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
presence_handler = logging.FileHandler("logs/presence.log")
presence_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
presence_logger = logging.getLogger("PresenceAudit")
presence_logger.addHandler(presence_handler)
presence_logger.propagate = False

def main():
    # 0. Maintenance & Cleanup
    MaintenanceTool().perform()

    if len(sys.argv) < 2:
        print("Usage: python run_atulya_tantra.py \"Your task here\" [--presence]")
        return

    # Initialize components
    memory = MemoryManager()
    governor = Governor(memory)
    engine = Engine(memory, governor)
    simulator = StimulusInjector()

    # Phase I: Operational Observability
    try:
        from core.dashboard import Dashboard
        dashboard = Dashboard(engine.goal_manager)
        dashboard.start()
        
        # Phase I-2: Web Dashboard
        from core.web_server import WebServer
        web_server = WebServer(port=8000, goal_manager=engine.goal_manager)
        web_server.start()
    except ImportError:
        dashboard = None
        web_server = None
        print("Warning: Dashboard module missing.")
    except Exception as e:
        print(f"Warning: Observability failed to start: {e}")
        dashboard = None
        web_server = None

    try:
        if sys.argv[1] == "--presence":
            engine.presence_loop(simulator)
        else:
            task = sys.argv[1]
            status = engine.run_task(task)
            print(f"\n[FINAL OUTPUT] {status}")
            # Keep dashboard alive briefly to see result
            import time
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n[USER INTERRUPT]")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {str(e)}")
    finally:
        if dashboard:
            dashboard.stop()
        if web_server:
            web_server.stop()


if __name__ == "__main__":
    main()
