#!/usr/bin/env python3
"""
Simple API test to verify endpoints work
"""

import requests
import json

def test_api():
    """Test API endpoints directly"""
    base_url = "http://127.0.0.1:8000"
    
    print("🧪 Testing API Endpoints")
    print("=" * 40)
    
    # Test 1: Health endpoint
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Admin health
    print("\n2. Testing admin health...")
    try:
        response = requests.get(f"{base_url}/api/admin/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Chat endpoint with JSON
    print("\n3. Testing chat endpoint (JSON)...")
    try:
        data = {"message": "Hello, test message"}
        response = requests.post(
            f"{base_url}/api/chat/",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Chat endpoint with form data
    print("\n4. Testing chat endpoint (Form)...")
    try:
        data = {"message": "Hello, test message"}
        response = requests.post(
            f"{base_url}/api/chat/",
            data=data
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 5: Conversations endpoint
    print("\n5. Testing conversations endpoint...")
    try:
        response = requests.get(f"{base_url}/api/chat/conversations")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_api()
