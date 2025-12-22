import sys
import os
import time
import logging

# Add current directory to path for imports
sys.path.append(os.getcwd())

from core.memory_manager import MemoryManager
from core.governor import Governor
from core.engine import Engine
from internal.simulator import StimulusInjector

def verify_presence():
    print("=== Phase 0.5 Presence Simulation Verification ===")
    
    # 1. Setup
    memory = MemoryManager()
    governor = Governor(memory)
    engine = Engine(memory, governor)
    simulator = StimulusInjector()
    
    # Configure presence logger for stdout visibility in this test
    presence_logger = logging.getLogger("PresenceAudit")
    presence_logger.addHandler(logging.StreamHandler(sys.stdout))
    
    # 2. Scenario: Noise Filtering (Low Priority)
    print("\n[SCENARIO 1] Noise Filtering")
    simulator.inject("SYSTEM_TIMER", "Background pulse signal", interrupt=False) # Priority 1
    signals = simulator.get_signals()
    for s in signals:
        engine.receive_signal(s)
    
    # Check if engine wakes for priority 1? No, current threshold in presence_loop is 1, so it Wakes.
    # But let's check filtering.
    interrupt = engine.check_interrupts(current_priority=5) # Typical execution threshold
    if not interrupt:
        print("SUCCESS: Noise signal (Priority 1) did not preempt standard cognitive threshold (5).")
    
    # 3. Scenario: Priority Interrupt & Preemption
    print("\n[SCENARIO 2] Priority Preemption")
    
    # Inject a steady task
    print("Step 1: Injecting Background Task...")
    simulator.inject("USER_DIRECT", "Generate a complex architecture report", interrupt=False) # Priority 5
    
    # Inject a High-Priority Interrupt
    print("Step 2: Injecting Emergency Interrupt...")
    simulator.inject("USER_DIRECT", "ABORT and read the manual", interrupt=True) # Priority 10
    
    signals = simulator.get_signals()
    for s in signals:
        engine.receive_signal(s)
    
    # Verify interrupt detection
    interrupt = engine.check_interrupts(current_priority=5)
    if interrupt and interrupt['sensor'] == "USER_DIRECT" and interrupt['priority'] == 10:
        print(f"SUCCESS: High-priority interrupt detected: {interrupt['stimulus']}")
    
    # 4. Simulation Execution: Interrupt & Resumption
    print("\n[SCENARIO 3] Interrupt & Resumption Execution Proof")
    # This will use the actual Engine.run_task logic
    
    # We'll inject the background task, start it, then mid-run inject the interrupt.
    # To simulate "mid-run", we rely on the receive_signal being called while run_task is active.
    
    # Setup background task
    bg_task = "Analyze project dependencies"
    
    # Manual trigger of interrupt during run_task execution is hard in single thread,
    # so we'll pre-inject the interrupt but keep it in buffer.
    
    print("Simulating: Running BG Task -> Mid-run Interrupt -> Preemption -> Resumption")
    
    # Inject interrupt that will be picked up by mid-strategy check in Engine.run_task
    simulator.inject("USER_DIRECT", "EMERGENCY: Check disk space", interrupt=True) 
    for s in simulator.get_signals():
        engine.receive_signal(s)
        
    status = engine.run_task(bg_task)
    print(f"\n[FINAL ENGINE OUTPUT] {status}")

if __name__ == "__main__":
    verify_presence()
