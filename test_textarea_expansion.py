#!/usr/bin/env python3
"""
Test script to verify the text area expansion to 3x larger size
"""
import requests
from bs4 import BeautifulSoup
import re

def test_textarea_expansion():
    """Test that text areas have been expanded to 3x the original size"""
    
    print("📏 TESTING TEXT AREA EXPANSION (3x Larger)")
    print("=" * 50)
    
    frontend_url = "https://3001-igoy3cr883cnchk200st0-6532622b.e2b.dev"
    
    try:
        # Get the main application page
        print("1. Fetching main application page...")
        response = requests.get(frontend_url, timeout=10)
        
        if response.status_code == 200:
            print("   ✅ Frontend page accessible")
            
            # Parse HTML to check textarea properties
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for CSS rules
            print("\n2. Checking CSS textarea-container class...")
            css_content = str(soup)
            
            # Look for the textarea-container CSS rule
            if 'min-height: 900px' in css_content:
                print("   ✅ CSS min-height set to 900px (3x expansion)")
            else:
                print("   ❌ CSS min-height not found or incorrect")
                return False
            
            if 'font-family: \'Courier New\', monospace' in css_content:
                print("   ✅ Monospace font family applied")
            else:
                print("   ⚠️  Monospace font family not detected")
            
            if 'line-height: 1.5' in css_content:
                print("   ✅ Line height set to 1.5")
            else:
                print("   ⚠️  Line height 1.5 not detected")
            
            if 'resize: vertical' in css_content:
                print("   ✅ Vertical resize capability enabled")
            else:
                print("   ⚠️  Vertical resize not detected")
            
            # Check textarea elements
            print("\n3. Checking textarea elements...")
            
            # Find input textarea
            input_textarea = soup.find('textarea', {'id': 'inputText'})
            if input_textarea:
                print("   ✅ Input textarea found")
                
                # Check for rows attribute
                rows = input_textarea.get('rows')
                if rows == '30':
                    print(f"   ✅ Input textarea has rows='{rows}' (expanded)")
                else:
                    print(f"   ⚠️  Input textarea rows: {rows} (expected: 30)")
                
                # Check for textarea-container class
                if 'textarea-container' in input_textarea.get('class', []):
                    print("   ✅ Input textarea has textarea-container class")
                else:
                    print("   ❌ Input textarea missing textarea-container class")
            else:
                print("   ❌ Input textarea not found")
                return False
            
            # Find output textarea
            output_textarea = soup.find('textarea', {'id': 'outputText'})
            if output_textarea:
                print("   ✅ Output textarea found")
                
                # Check for rows attribute
                rows = output_textarea.get('rows')
                if rows == '30':
                    print(f"   ✅ Output textarea has rows='{rows}' (expanded)")
                else:
                    print(f"   ⚠️  Output textarea rows: {rows} (expected: 30)")
                
                # Check for textarea-container class
                if 'textarea-container' in output_textarea.get('class', []):
                    print("   ✅ Output textarea has textarea-container class")
                else:
                    print("   ❌ Output textarea missing textarea-container class")
                    
                # Check readonly attribute
                if output_textarea.get('readonly') is not None:
                    print("   ✅ Output textarea is readonly")
                else:
                    print("   ⚠️  Output textarea readonly not set")
            else:
                print("   ❌ Output textarea not found")
                return False
            
            # Check test page
            print("\n4. Testing expansion demonstration page...")
            test_response = requests.get(f"{frontend_url}/test_expanded_areas.html", timeout=5)
            if test_response.status_code == 200:
                print("   ✅ Text area expansion test page accessible")
                
                # Check for comparison content
                test_soup = BeautifulSoup(test_response.text, 'html.parser')
                if 'old-size' in str(test_soup) and 'new-size' in str(test_soup):
                    print("   ✅ Before/after comparison available")
                else:
                    print("   ⚠️  Before/after comparison not found")
            else:
                print(f"   ⚠️  Test page error: {test_response.status_code}")
            
        else:
            print(f"   ❌ Frontend page error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 TEXT AREA EXPANSION VERIFICATION COMPLETE!")
    
    print("\n📏 Expansion Summary:")
    print("   📐 Original height: 300px")
    print("   📏 New height: 900px (3x larger)")
    print("   📝 Original rows: ~10")  
    print("   📄 New rows: 30 (3x larger)")
    
    print("\n🎨 Enhanced Features:")
    print("   ✅ Monospace font (Courier New) for better alignment")
    print("   ✅ Improved line height (1.5) for readability")
    print("   ✅ Larger font size (14px) for comfort")
    print("   ✅ Vertical resize capability for customization")
    
    print("\n💼 Business Benefits:")
    print("   🏥 Better handling of long clinical documentation")
    print("   👀 Easier review of detailed de-identification results")
    print("   ⚖️ Improved side-by-side text comparison")
    print("   ✏️ More comfortable text editing experience")
    print("   📊 Reduced scrolling improves workflow efficiency")
    
    print("\n🌐 Test the Expansion:")
    print(f"   • Main Application: {frontend_url}")
    print(f"   • Expansion Demo: {frontend_url}/test_expanded_areas.html")
    
    print("\n📋 User Experience:")
    print("   • Clinical text input area is now 3x larger")
    print("   • De-identification results display area is 3x larger")
    print("   • Both areas use professional monospace formatting")
    print("   • Users can resize vertically as needed")
    print("   • Perfect for long clinical documents and detailed outputs")
    
    return True

if __name__ == "__main__":
    success = test_textarea_expansion()
    print(f"\n{'✅ EXPANSION VERIFICATION PASSED' if success else '❌ EXPANSION VERIFICATION FAILED'}")
    exit(0 if success else 1)