#!/usr/bin/env python3
"""
Atulya Tantra AGI - One-Click Automation
Automatically sets up, optimizes, and runs the system
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command: str, description: str) -> bool:
    """Run a command and return success status"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False

def main():
    """Main automation script"""
    print("🚀 Atulya Tantra AGI - One-Click Automation")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("Core").exists():
        print("❌ Please run this script from the Atulya-Tantra root directory")
        sys.exit(1)
    
    # Run optimization
    print("\n📋 Step 1: Code Optimization")
    run_command("python optimize.py", "Code optimization")
    
    # Run setup
    print("\n📋 Step 2: System Setup")
    run_command("python setup.py", "System setup")
    
    # Quick test
    print("\n📋 Step 3: Quick Test")
    run_command("python test_simple.py", "System test")
    
    print("\n" + "=" * 50)
    print("🎉 Automation completed!")
    print("\n🚀 To start the system:")
    print("   python Core/api/main.py")
    print("   or")
    print("   python tantra.py")

if __name__ == "__main__":
    main()
