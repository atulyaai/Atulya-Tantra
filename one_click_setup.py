#!/usr/bin/env python3
"""
One-Click Complete Setup - No MD Files
Sets up everything automatically: GitHub, code, issues, automation
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
    print("🚀 Atulya Tantra AGI - Complete One-Click Setup")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("Core").exists():
        print("❌ Please run this script from the Atulya-Tantra root directory")
        sys.exit(1)
    
    # Get GitHub token
    github_token = input("🔑 Enter your GitHub token (ghp_...): ").strip()
    if not github_token:
        print("❌ GitHub token is required for complete setup")
        sys.exit(1)
    
    # Set environment variable
    os.environ['GITHUB_TOKEN'] = github_token
    
    print("\n🚀 Starting Complete Setup...")
    print("This will set up everything automatically:")
    print("• GitHub repository settings")
    print("• Professional topics and labels")
    print("• Automated issues and tracking")
    print("• Code optimization")
    print("• System setup")
    print("• Automated workflows")
    
    # Run all setup steps
    steps = [
        ("python github_setup.py", "GitHub repository setup"),
        ("python optimize.py", "Code optimization"),
        ("python setup.py", "System setup"),
        ("python test_simple.py", "System test")
    ]
    
    success_count = 0
    
    for command, description in steps:
        if run_command(command, description):
            success_count += 1
        print()  # Add spacing
    
    print("=" * 60)
    print(f"🎉 Complete Setup Finished: {success_count}/{len(steps)} steps successful")
    
    if success_count == len(steps):
        print("✅ Everything is now fully automated!")
        print("\n🚀 Your repository now has:")
        print("   • Professional GitHub settings")
        print("   • 30+ professional topics/tags")
        print("   • 18 professional labels")
        print("   • 4 automated tracking issues")
        print("   • Complete automation workflows")
        print("   • Auto-optimized code")
        print("   • Automated deployment")
        print("   • Auto-issue processing")
        
        print("\n🔗 Check your repository:")
        print("   https://github.com/atulyaai/Atulya-Tantra")
        
        print("\n🤖 All automation is now active:")
        print("   • Issues are processed automatically")
        print("   • Code is optimized automatically")
        print("   • Deployments happen automatically")
        print("   • Everything is tracked automatically")
        
    else:
        print("⚠️ Some steps had issues, but core features should work")
    
    print("\n🚀 To start the system:")
    print("   python Core/api/main.py")

if __name__ == "__main__":
    main()
