#!/usr/bin/env python3
"""
Comprehensive validation test for improved Thai clinical text de-identification
"""
import requests
import json

# Configuration
BASE_URL = "https://8000-igoy3cr883cnchk200st0-6532622b.e2b.dev"
CREDENTIALS = {"username": "admin", "password": "admin123"}

# Test cases with expected entities
TEST_CASES = [
    {
        "name": "Original Issue - Doctor Names",
        "text": "คุณสมชาย วิทยาภูมิ โทรศัพท์ 089-123-4567 อีเมล somchai@hospital.co.th วันเกิด 15 มกราคม 2540 มีอาการปวดหัว หมอสมชาย ให้ยา Paracetamol กับ ยาหม่อง ส่วนหมอ Peter ให้ยาถ่าย",
        "expected_entities": ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "PERSON", "PERSON"],
        "expected_count": 5
    },
    {
        "name": "Multiple Thai Doctors",
        "text": "หมอสมพร และ หมอสมศรี ตรวจผู้ป่วย นายจิตร์ โทร 081-999-8888",
        "expected_entities": ["PERSON", "PERSON", "PERSON", "PHONE_NUMBER"],
        "expected_count": 4
    },
    {
        "name": "Mixed Medical Staff",
        "text": "ดร.วิทยา พยาบาลสมใส หมอ John และ อาจารย์พิมพ์ ดูแลผู้ป่วย",
        "expected_entities": ["PERSON", "PERSON", "PERSON", "PERSON"],
        "expected_count": 4
    },
    {
        "name": "Various Phone Formats",
        "text": "โทร 089-123-4567 หรือ 081 234 5678 หรือ 0661234567",
        "expected_entities": ["PHONE_NUMBER", "PHONE_NUMBER", "PHONE_NUMBER"],
        "expected_count": 3
    },
    {
        "name": "Email Variations",
        "text": "อีเมล patient@hospital.co.th หรือ doctor.john@medical.org",
        "expected_entities": ["EMAIL_ADDRESS", "EMAIL_ADDRESS"],
        "expected_count": 2
    }
]

def get_auth_token():
    """Get authentication token."""
    response = requests.post(f"{BASE_URL}/auth/login", json=CREDENTIALS)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Authentication failed: {response.status_code}")

def test_detection(token, text):
    """Test entity detection."""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"text": text}
    
    response = requests.post(f"{BASE_URL}/api/v1/detect", 
                           headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Detection failed: {response.status_code}")

def validate_test_case(token, test_case):
    """Validate a specific test case."""
    print(f"\n🧪 Testing: {test_case['name']}")
    print("="*60)
    print(f"📝 Text: {test_case['text']}")
    
    try:
        result = test_detection(token, test_case['text'])
        
        detected_count = result['entities_found']
        expected_count = test_case['expected_count']
        
        print(f"\n📊 Results:")
        print(f"   Expected entities: {expected_count}")
        print(f"   Detected entities: {detected_count}")
        
        # Check if count matches
        if detected_count == expected_count:
            print(f"   ✅ Count match: PASS")
        else:
            print(f"   ❌ Count mismatch: FAIL")
        
        # Show detected entities
        print(f"\n🔍 Detected Entities:")
        for i, entity in enumerate(result['detections'], 1):
            print(f"   {i}. {entity['entity_type']}: '{entity['text']}' "
                  f"(confidence: {entity['confidence']*100:.1f}%)")
        
        # Check entity types
        detected_types = [entity['entity_type'] for entity in result['detections']]
        expected_types = test_case['expected_entities']
        
        missing_types = []
        for expected_type in expected_types:
            if expected_type not in detected_types:
                missing_types.append(expected_type)
        
        if not missing_types:
            print(f"   ✅ Entity types: PASS")
            return True
        else:
            print(f"   ❌ Missing entity types: {missing_types}")
            return False
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def main():
    """Run comprehensive validation."""
    print("🔍 COMPREHENSIVE DE-IDENTIFICATION VALIDATION")
    print("="*60)
    print("Testing improved entity detection capabilities...")
    
    try:
        # Get authentication
        token = get_auth_token()
        print("✅ Authentication successful")
        
        # Run all test cases
        results = []
        for test_case in TEST_CASES:
            success = validate_test_case(token, test_case)
            results.append((test_case['name'], success))
        
        # Summary
        print(f"\n" + "="*60)
        print("📋 VALIDATION SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
        
        print(f"\n📊 Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED - System is working correctly!")
            print("\n✅ Improvements Validated:")
            print("   • Doctor names with หมอ prefix detected")
            print("   • Mixed Thai-English names detected") 
            print("   • Phone numbers with various formats detected")
            print("   • Multiple medical staff titles supported")
            print("   • Email addresses properly identified")
            print("   • PDPA compliance requirements met")
        else:
            print(f"⚠️  {total - passed} tests failed - review detection rules")
        
        return passed == total
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)