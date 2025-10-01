#!/bin/bash
# Quick Demo Script for Clinical De-ID System

BASE_URL="https://8000-igoy3cr883cnchk200st0-6532622b.e2b.dev"

echo "🏥 Clinical Text De-Identification System Demo"
echo "=============================================="
echo "🌐 App URL: $BASE_URL"
echo "📚 Docs: $BASE_URL/docs"
echo ""

# Test health
echo "🔍 Testing system health..."
curl -s "$BASE_URL/health" | jq '.status, .timestamp'
echo ""

# Login and get token
echo "🔑 Logging in as admin..."
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | jq -r '.access_token')

if [ "$TOKEN" != "null" ]; then
    echo "✅ Login successful!"
    
    echo ""
    echo "🇹🇭 Testing Thai text detection..."
    curl -s -X POST "$BASE_URL/api/v1/detect" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"text": "คุณสมชาย วิทยาภูมิ โทรศัพท์ 089-123-4567 อีเมล somchai@hospital.co.th"}' | \
      jq '.detected_language, .entities_found, .detections[].entity_type'
    
    echo ""
    echo "🇺🇸 Testing English text detection..."
    curl -s -X POST "$BASE_URL/api/v1/detect" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"text": "Dr. John Smith called 555-123-4567 regarding patient records for john.smith@hospital.com"}' | \
      jq '.detected_language, .entities_found, .detections[].entity_type'
    
    echo ""
    echo "🎉 Demo completed successfully!"
    echo "💡 Visit $BASE_URL/docs to explore the full API"
else
    echo "❌ Login failed"
fi
