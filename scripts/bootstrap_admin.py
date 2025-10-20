#!/usr/bin/env python3
"""
Atulya Tantra - Admin Bootstrap Script
Version: 2.5.0
Generate admin JWT token for initial setup
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.auth_service import AuthService

def main():
    """Generate admin token for bootstrap"""
    print("🔑 Atulya Tantra Admin Bootstrap")
    print("=" * 40)
    
    # Initialize auth service
    auth_service = AuthService()
    
    # Generate admin token
    admin_token = auth_service.generate_admin_token(
        subject="admin",
        roles=["admin"],
        minutes=60*24  # 24 hours
    )
    
    print(f"✅ Admin JWT Token Generated:")
    print(f"Bearer {admin_token}")
    print()
    print("📋 Usage Instructions:")
    print("1. Copy the token above")
    print("2. Go to http://localhost:8000/webui/admin/")
    print("3. Paste the token in the JWT field")
    print("4. Click 'Set' to authenticate")
    print()
    print("⚠️  Keep this token secure - it has admin privileges!")
    print("⏰ Token expires in 24 hours")

if __name__ == "__main__":
    main()
