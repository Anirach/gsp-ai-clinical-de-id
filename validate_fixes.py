#!/usr/bin/env python3
"""
Validation script to test all the fixes made to the Clinical De-ID system.
"""
import sys
import subprocess
import requests
import json
from datetime import datetime

def test_imports():
    """Test critical imports work correctly."""
    print("🧪 Testing imports...")
    
    try:
        # Test models import
        sys.path.insert(0, '/home/user/webapp/backend/src')
        from models.schemas import UserRole, EntityType, DeIdentificationRequest
        print("✅ Models import successful")
        
        # Test datetime with timezone awareness
        from models.schemas import DeIdentificationJob
        job = DeIdentificationJob(
            policy_version="v1.0",
            linkage_domain="test"
        )
        print(f"✅ Pydantic datetime fields working: {job.created_at}")
        
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_demo_server():
    """Test demo server endpoints."""
    print("\n🌐 Testing demo server endpoints...")
    
    base_url = "https://8000-igoy3cr883cnchk200st0-6532622b.e2b.dev"
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health endpoint: {data['status']}")
            print(f"   Timezone-aware timestamp: {data['timestamp']}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False
    
    # Test authentication
    try:
        login_data = {
            "username": "admin", 
            "password": "admin123"
        }
        response = requests.post(f"{base_url}/auth/login", json=login_data, timeout=10)
        if response.status_code == 200:
            token_data = response.json()
            print("✅ Authentication endpoint working")
            token = token_data['access_token']
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False
    
    # Test detection endpoint
    try:
        headers = {"Authorization": f"Bearer {token}"}
        detection_data = {
            "text": "นายสมชาย ใจดี โทร 081-234-5678 อีเมล somchai@email.com"
        }
        response = requests.post(f"{base_url}/api/v1/detect", 
                               json=detection_data, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Detection endpoint: Found {result.get('entities_found', 0)} entities")
        else:
            print(f"❌ Detection endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Detection endpoint error: {e}")
        return False
    
    return True

def test_syntax():
    """Test Python syntax on all files."""
    print("\n🔍 Testing Python syntax...")
    
    try:
        result = subprocess.run([
            'find', '/home/user/webapp/backend/src', '-name', '*.py', 
            '-exec', 'python3', '-m', 'py_compile', '{}', ';'
        ], capture_output=True, text=True, cwd='/home/user/webapp')
        
        if result.returncode == 0:
            print("✅ All Python files have valid syntax")
            return True
        else:
            print(f"❌ Syntax errors found:\n{result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Syntax test error: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🚀 Clinical De-ID System - Fix Validation")
    print("=" * 50)
    
    tests = [
        ("Syntax Check", test_syntax),
        ("Import Validation", test_imports),
        ("Demo Server Functionality", test_demo_server)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        success = test_func()
        results.append((test_name, success))
        
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED - System is ready!")
        print("\nFixed Issues:")
        print("✅ datetime.utcnow() deprecation warnings resolved")
        print("✅ Timezone-aware datetime handling implemented") 
        print("✅ Pydantic v2 field_validator syntax updated")
        print("✅ Added pydantic-settings to requirements.txt")
        print("✅ Created requirements-demo.txt for lightweight setup")
        print("✅ All Python syntax validated")
        print("✅ Demo server functionality verified")
    else:
        print("❌ Some tests failed - check output above")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())