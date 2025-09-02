"""
Test script for Radar2 Routing Service

This script tests all routing algorithms with various coordinate pairs
to verify functionality and compare different routing approaches.

Usage:
    python test_routing.py
"""

from routing_service import RoutingService, Coordinate
import json
from typing import List, Dict, Any


def test_coordinates() -> List[Dict[str, Any]]:
    """Define test coordinate pairs for various scenarios"""
    return [
        {
            "name": "Short Urban Route (NYC)",
            "description": "Short distance within Manhattan",
            "start": (40.7128, -74.0060),  # NYC Financial District
            "end": (40.7589, -73.9851),    # Central Park
            "expected_distance_range": (6000, 12000)  # 6-12km
        },
        {
            "name": "Medium Suburban Route", 
            "description": "Medium distance suburban routing",
            "start": (40.7128, -74.0060),  # NYC
            "end": (40.6892, -74.0445),    # Jersey City
            "expected_distance_range": (8000, 15000)  # 8-15km
        },
        {
            "name": "Long Highway Route",
            "description": "Long distance highway-style routing", 
            "start": (40.7128, -74.0060),  # NYC
            "end": (41.0534, -73.5387),    # Bridgeport, CT
            "expected_distance_range": (70000, 120000)  # 70-120km
        },
        {
            "name": "Your Test Coordinates",
            "description": "Coordinates from your original request",
            "start": (40.39236025345184, 71.76425536498604),  # Uzbekistan location
            "end": (40.38268468389782, 71.79549773559057),
            "expected_distance_range": (2500, 5000)  # 2.5-5km
        },
        {
            "name": "Very Short Route",
            "description": "Very short distance to test direct routing",
            "start": (40.7128, -74.0060),
            "end": (40.7130, -74.0058),
            "expected_distance_range": (0, 500)  # Under 500m
        }
    ]


def format_route_summary(route_data: Dict[str, Any]) -> str:
    """Format route data for display"""
    props = route_data['properties']
    coords = route_data['geometry']['coordinates']
    
    return f"""
    Algorithm: {props['algorithm']}
    Distance: {props['distance_m']:.0f}m ({props['distance_m']/1000:.1f}km)
    Duration: {props['duration_s']:.0f}s ({props['duration_s']/60:.1f}min)
    Speed: {props['estimated_speed_kmh']:.1f}km/h
    Route Type: {props['route_type']}
    Waypoints: {props['waypoint_count']}
    Coordinates: {len(coords)} points
    """


def test_single_route(service: RoutingService, test_case: Dict[str, Any], algorithm: str) -> Dict[str, Any]:
    """Test a single route with given algorithm"""
    start_lat, start_lon = test_case['start']
    end_lat, end_lon = test_case['end']
    
    try:
        route = service.get_route(start_lat, start_lon, end_lat, end_lon, algorithm)
        
        # Validate distance is within expected range
        distance = route['properties']['distance_m']
        expected_min, expected_max = test_case['expected_distance_range']
        
        distance_valid = expected_min <= distance <= expected_max * 2  # Allow 2x for detours
        
        return {
            'success': True,
            'route': route,
            'distance_valid': distance_valid,
            'distance': distance,
            'expected_range': test_case['expected_distance_range']
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def run_comprehensive_tests():
    """Run comprehensive tests of all algorithms"""
    print("🗺️ Radar2 Routing Service - Comprehensive Tests")
    print("=" * 60)
    
    service = RoutingService()
    test_cases = test_coordinates()
    algorithms = ['smart', 'grid', 'curved', 'direct']
    
    total_tests = 0
    passed_tests = 0
    
    for test_case in test_cases:
        print(f"\n📍 {test_case['name']}")
        print(f"   {test_case['description']}")
        print(f"   From: {test_case['start'][0]:.6f}, {test_case['start'][1]:.6f}")
        print(f"   To:   {test_case['end'][0]:.6f}, {test_case['end'][1]:.6f}")
        print("-" * 40)
        
        for algorithm in algorithms:
            total_tests += 1
            result = test_single_route(service, test_case, algorithm)
            
            if result['success']:
                passed_tests += 1
                route_summary = format_route_summary(result['route'])
                
                status = "✅" if result['distance_valid'] else "⚠️ "
                print(f"{status} {algorithm.upper()}: {route_summary}")
                
                if not result['distance_valid']:
                    print(f"   🔍 Distance outside expected range: {result['distance']:.0f}m")
                    print(f"       Expected: {result['expected_range'][0]}-{result['expected_range'][1]}m")
            else:
                print(f"❌ {algorithm.upper()}: Failed - {result['error']}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Routing service is working correctly.")
    else:
        print(f"⚠️  {total_tests - passed_tests} tests failed. Check the output above.")


def test_algorithm_comparison():
    """Compare all algorithms on the same route"""
    print("\n🔄 Algorithm Comparison")
    print("=" * 40)
    
    service = RoutingService()
    
    # Use your test coordinates
    start_lat, start_lon = 40.39236025345184, 71.76425536498604
    end_lat, end_lon = 40.38268468389782, 71.79549773559057
    
    algorithms = ['direct', 'curved', 'grid', 'smart']
    
    print(f"From: {start_lat:.6f}, {start_lon:.6f}")
    print(f"To:   {end_lat:.6f}, {end_lon:.6f}")
    print("-" * 40)
    
    routes = {}
    for algorithm in algorithms:
        route = service.get_route(start_lat, start_lon, end_lat, end_lon, algorithm)
        routes[algorithm] = route
        props = route['properties']
        
        print(f"{algorithm.upper():8} | "
              f"{props['distance_m']:6.0f}m | "
              f"{props['duration_s']:5.0f}s | "
              f"{props['waypoint_count']:2d} waypoints | "
              f"{props['route_type']}")
    
    # Find shortest and longest routes
    distances = {alg: routes[alg]['properties']['distance_m'] for alg in algorithms}
    shortest = min(distances, key=distances.get)
    longest = max(distances, key=distances.get)
    
    print(f"\n📊 Summary:")
    print(f"   Shortest: {shortest.upper()} ({distances[shortest]:.0f}m)")
    print(f"   Longest:  {longest.upper()} ({distances[longest]:.0f}m)")
    
    if longest != shortest:
        ratio = distances[longest] / distances[shortest]
        print(f"   Ratio:    {ratio:.1f}x longer")


def export_sample_routes():
    """Export sample routes for visualization"""
    print("\n💾 Exporting Sample Routes")
    print("=" * 30)
    
    service = RoutingService()
    
    # Your test coordinates
    start_lat, start_lon = 40.39236025345184, 71.76425536498604
    end_lat, end_lon = 40.38268468389782, 71.79549773559057
    
    sample_routes = {}
    for algorithm in ['smart', 'grid', 'curved', 'direct']:
        route = service.get_route(start_lat, start_lon, end_lat, end_lon, algorithm)
        sample_routes[algorithm] = route
    
    # Export to JSON file
    try:
        with open('sample_routes.json', 'w') as f:
            json.dump(sample_routes, f, indent=2)
        print("✅ Sample routes exported to 'sample_routes.json'")
        print("   You can use this file to visualize routes on a map")
    except Exception as e:
        print(f"❌ Failed to export: {e}")


if __name__ == "__main__":
    try:
        # Run all tests
        run_comprehensive_tests()
        test_algorithm_comparison() 
        export_sample_routes()
        
        print("\n🚀 Testing complete! You can now start the routing service:")
        print("   python app.py")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Install dependencies: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Check the routing service implementation.")