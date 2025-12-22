import logging
from core.memory_manager import MemoryManager
from core.governor import Governor
from core.engine import Engine
from tools.maintenance import MaintenanceTool

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
        print("Usage: python run_atulya_tantra.py \"Your task here\"")
        return

    task = sys.argv[1]
    
    # Initialize components
    memory = MemoryManager()
    governor = Governor(memory)
    engine = Engine(memory, governor)
    
    # Run the loop
    try:
        status = engine.run_task(task)
        print(f"\n[FINAL OUTPUT] {status}")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {str(e)}")

if __name__ == "__main__":
    main()
