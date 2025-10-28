#!/usr/bin/env python3
"""
Atulya Tantra AGI - Complete Automation Setup
Runs all automation scripts and configures GitHub automatically
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
    print("🚀 Atulya Tantra AGI - Complete Automation Setup")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("Core").exists():
        print("❌ Please run this script from the Atulya-Tantra root directory")
        sys.exit(1)
    
    # Get GitHub token
    github_token = input("🔑 Enter your GitHub token (ghp_...): ").strip()
    if not github_token:
        print("❌ GitHub token is required for automation")
        sys.exit(1)
    
    # Set environment variable
    os.environ['GITHUB_TOKEN'] = github_token
    
    # Run all automation steps
    steps = [
        ("python optimize.py", "Code optimization"),
        ("python setup.py", "System setup"),
        ("python github_config.py", "GitHub configuration"),
        ("python test_simple.py", "System test")
    ]
    
    success_count = 0
    
    for command, description in steps:
        if run_command(command, description):
            success_count += 1
        print()  # Add spacing
    
    print("=" * 60)
    print(f"🎉 Automation completed: {success_count}/{len(steps)} steps successful")
    
    if success_count == len(steps):
        print("✅ All automation steps completed successfully!")
        print("\n🚀 Your repository is now fully automated:")
        print("   • Code optimization runs automatically")
        print("   • Issues are processed automatically")
        print("   • Deployments happen automatically")
        print("   • GitHub settings are configured")
        print("\n🔗 Check your repository: https://github.com/atulyaai/Atulya-Tantra")
    else:
        print("⚠️ Some steps had issues, but the system should still work")
    
    print("\n🚀 To start the system:")
    print("   python Core/api/main.py")

if __name__ == "__main__":
    main()
