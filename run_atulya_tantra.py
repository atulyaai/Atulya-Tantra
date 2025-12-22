import sys
import os
from memory.memory_manager import MemoryManager
from core.governor import Governor
from core.engine import Engine

def main():
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
