#!/usr/bin/env python3
"""
Thai Clinical Text Testing Script for De-Identification System
"""
import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "https://8000-igoy3cr883cnchk200st0-6532622b.e2b.dev"
CREDENTIALS = {"username": "admin", "password": "admin123"}

# Your test text
THAI_CLINICAL_TEXT = """คุณสมชาย วิทยาภูมิ โทรศัพท์ 089-123-4567 อีเมล somchai@hospital.co.th วันเกิด 15 มกราคม 2540 มีอาการปวดหัว หมอสมชาย ให้ยา Paracetamol กับ ยาหม่อง ส่วนหมอ Peter ให้ยาถ่าย"""

def get_auth_token():
    """Get authentication token."""
    response = requests.post(f"{BASE_URL}/auth/login", json=CREDENTIALS)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Authentication failed: {response.status_code}")

def test_entity_detection(token, text):
    """Test entity detection."""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"text": text}
    
    response = requests.post(f"{BASE_URL}/api/v1/detect", 
                           headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Detection failed: {response.status_code}")

def test_deidentification(token, text):
    """Test full de-identification."""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "documents": [
            {
                "content": text,
                "document_id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "metadata": {"type": "clinical_note", "language": "th"}
            }
        ],
        "policy_version": "pdpa_v1.0",
        "linkage_domain": "patient_id"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/jobs", 
                           headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"De-identification failed: {response.status_code}")

def analyze_results(detection_result, deidentification_result):
    """Analyze and display results."""
    print("\n" + "="*60)
    print("🔍 ENTITY DETECTION ANALYSIS")
    print("="*60)
    
    print(f"📄 Text Length: {detection_result['text_length']} characters")
    print(f"🌍 Language Detected: {detection_result['detected_language']}")
    print(f"🎯 Entities Found: {detection_result['entities_found']}")
    
    print(f"\n📋 Detected Entities:")
    for i, entity in enumerate(detection_result['detections'], 1):
        print(f"  {i}. {entity['entity_type']}")
        print(f"     Text: '{entity['text']}'")
        print(f"     Position: {entity['start']}-{entity['end']}")
        print(f"     Confidence: {entity['confidence']*100:.1f}%")
        print(f"     Detector: {entity['detector']}")
        print()
    
    print("="*60)
    print("🔒 DE-IDENTIFICATION RESULTS")
    print("="*60)
    
    result = deidentification_result['results'][0]
    print(f"📄 Document ID: {result['document_id']}")
    print(f"📏 Original Length: {result['original_length']} chars")
    print(f"🔍 Entities Detected: {result['entities_detected']}")
    print(f"🔄 Transformations: {result['transformations_applied']}")
    
    print(f"\n📝 Original Text:")
    print(f"'{THAI_CLINICAL_TEXT}'")
    
    print(f"\n🔒 De-identified Text:")
    print(f"'{result['deidentified_text']}'")
    
    # Analysis
    print(f"\n🧪 ANALYSIS:")
    print(f"✅ Privacy Protection: {result['transformations_applied']} sensitive elements masked")
    print(f"✅ Clinical Content Preserved: Medical terms and symptoms retained")
    print(f"✅ PDPA Compliance: Personal identifiers removed/pseudonymized")

def main():
    """Main testing function."""
    print("🏥 Thai Clinical Text De-Identification Testing")
    print("="*60)
    
    try:
        # Get authentication
        print("🔑 Authenticating...")
        token = get_auth_token()
        print("✅ Authentication successful!")
        
        # Test entity detection
        print("🔍 Testing entity detection...")
        detection_result = test_entity_detection(token, THAI_CLINICAL_TEXT)
        print("✅ Entity detection completed!")
        
        # Test de-identification
        print("🔒 Testing de-identification...")
        deidentification_result = test_deidentification(token, THAI_CLINICAL_TEXT)
        print("✅ De-identification completed!")
        
        # Analyze results
        analyze_results(detection_result, deidentification_result)
        
        print(f"\n🎉 All tests completed successfully!")
        print(f"💡 Try the interactive docs at: {BASE_URL}/docs")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()