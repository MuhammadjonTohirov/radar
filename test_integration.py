#!/usr/bin/env python3
"""
Test script to verify routing integration between main API and server-map service

This script tests the integration between your main Django API and the 
new custom routing service without requiring Django setup.
"""

import requests
import json

def test_custom_routing_service():
    """Test the custom routing service directly"""
    print("🗺️ Testing Custom Routing Service")
    print("=" * 40)
    
    url = "http://localhost:5002/route"
    params = {
        'from': '40.39066059187596,71.75859053954719',
        'to': '40.38314234350446,71.80425246581603', 
        'algorithm': 'smart'
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Custom routing service working!")
        print(f"   Algorithm: {data['properties']['algorithm']}")
        print(f"   Distance: {data['properties']['distance_m']:.1f}m")
        print(f"   Duration: {data['properties']['duration_s']:.1f}s")
        print(f"   Provider: radar2-custom")
        return True
        
    except Exception as e:
        print(f"❌ Custom routing service failed: {e}")
        return False

def test_main_api():
    """Test the main API routing endpoint"""
    print("\n🎯 Testing Main API Integration") 
    print("=" * 40)
    
    url = "http://localhost:9999/api/route/"
    params = {
        'from': '71.75859053954719,40.39066059187596',
        'to': '71.80425246581603,40.38314234350446'
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        provider = data['properties']['summary'].get('provider', 'unknown')
        distance = data['properties']['summary']['distance_m']
        
        print(f"📡 Main API Response:")
        print(f"   Provider: {provider}")
        print(f"   Distance: {distance:.1f}m")
        
        if provider == 'radar2-custom':
            print("✅ Main API is using custom routing service!")
            return True
        else:
            print("⚠️  Main API is still using fallback routing")
            print("💡 You need to restart your Django server to pick up the changes")
            return False
            
    except Exception as e:
        print(f"❌ Main API test failed: {e}")
        return False

def show_restart_instructions():
    """Show instructions for restarting the Django server"""
    print("\n🔧 How to Enable Custom Routing in Your Main API:")
    print("=" * 50)
    print("1. Stop your Django server (port 9999)")
    print("2. Make sure the routing service is running (port 5002):")
    print("   cd server-map && source venv/bin/activate && python app.py")
    print("3. Restart your Django server with the routing service URL:")
    print("   CUSTOM_ROUTING_URL=http://localhost:5002 python manage.py runserver 9999")
    print("")
    print("Or add this to your environment:")
    print("   export CUSTOM_ROUTING_URL=http://localhost:5002")
    print("")
    print("Then test with:")
    print("   curl 'http://localhost:9999/api/route/?from=71.758,40.391&to=71.804,40.383'")

def main():
    print("🚀 Radar2 Routing Integration Test")
    print("=" * 50)
    
    # Test custom routing service
    custom_working = test_custom_routing_service()
    
    if not custom_working:
        print("\n❌ Custom routing service is not running.")
        print("Start it with: cd server-map && source venv/bin/activate && python app.py")
        return
    
    # Test main API integration
    main_api_working = test_main_api()
    
    if not main_api_working:
        show_restart_instructions()
    else:
        print("\n🎉 Everything is working perfectly!")
        print("Your main API is now using the custom routing service!")

if __name__ == "__main__":
    main()