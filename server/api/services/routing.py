from typing import Tuple, Dict, Any, List
from django.conf import settings
import json


class RoutingService:
    """
    Simple routing service abstraction.

    In production, integrate with a real routing engine (e.g., OSRM, Valhalla, GraphHopper)
    and return an accurate road-following route. For now, we return a straight line
    between the two coordinates as a placeholder, keeping the API contract stable.
    """

    @staticmethod
    def get_route_coords(coordinates: List[Tuple[float, float]], profile: str | None = None) -> Dict[str, Any]:
        """Return a GeoJSON Feature (LineString) through two or more coordinates.

        Args:
            coordinates: list of (lon, lat) tuples, length >= 2
        """
        print(f"DEBUG: get_route_coords called with {len(coordinates)} coordinates")
        if not coordinates or len(coordinates) < 2:
            raise ValueError('At least two coordinates are required')

        # Try external routing provider if configured
        provider = getattr(settings, 'ROUTING_PROVIDER', 'fallback')
        base_url = getattr(settings, 'ROUTING_BASE_URL', '')
        
        # Use our custom routing service first
        custom_routing_url = getattr(settings, 'CUSTOM_ROUTING_URL', 'http://localhost:5002')
        if custom_routing_url:
            try:
                print(f"DEBUG: Trying custom routing at {custom_routing_url}")
                # Map OSRM profiles to our algorithms
                algorithm_map = {
                    'driving': 'smart',
                    'driving-traffic': 'smart', 
                    'walking': 'direct',
                    'cycling': 'grid'
                }
                algorithm = algorithm_map.get(profile, profile) or 'smart'
                result = RoutingService._route_custom(custom_routing_url, coordinates, algorithm)
                print(f"DEBUG: Custom routing succeeded, provider: {result['properties']['summary']['provider']}")
                return result
            except Exception as e:
                print(f"DEBUG: Custom routing failed: {e}")
                # fall back to OSRM or straight line
                pass
        
        # Try OSRM as fallback
        if provider.lower() == 'osrm' and base_url:
            try:
                return RoutingService._route_osrm(base_url, coordinates, profile or 'driving')
            except Exception:
                # fall back to straight line on any error
                pass

        # Fallback: straight line(s) connecting given coordinates in order
        return {
            "type": "Feature",
            "properties": {
                "summary": {
                    "distance_m": RoutingService._polyline_distance(coordinates),
                    "provider": provider
                }
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for (lon, lat) in coordinates]
            }
        }

    @staticmethod
    def _route_custom(base_url: str, coordinates: List[Tuple[float, float]], algorithm: str) -> Dict[str, Any]:
        """
        Call our custom Radar2 routing service
        
        Uses the server-map routing service with multiple algorithm support
        """
        import requests
        
        if len(coordinates) < 2:
            raise ValueError("At least 2 coordinates required")
        
        # Use first and last coordinates for now (can be extended for waypoints)
        start_coord = coordinates[0]  # (lon, lat)
        end_coord = coordinates[-1]   # (lon, lat)
        
        # Convert to lat,lon format for our API
        start_str = f"{start_coord[1]},{start_coord[0]}"  # lat,lon
        end_str = f"{end_coord[1]},{end_coord[0]}"        # lat,lon
        
        url = f"{base_url.rstrip('/')}/route"
        params = {
            'from': start_str,
            'to': end_str,
            'algorithm': algorithm
        }
        
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        # Validate response format
        if data.get('type') != 'Feature' or not data.get('geometry'):
            raise RuntimeError('Invalid custom routing response')
            
        geometry = data.get('geometry', {})
        if geometry.get('type') != 'LineString' or not geometry.get('coordinates'):
            raise RuntimeError('Invalid custom routing geometry')
        
        # Update properties to match expected format
        properties = data.get('properties', {})
        
        # Reformat to match Django API expected structure
        formatted_properties = {
            "summary": {
                "distance_m": properties.get('distance_m', 0),
                "duration_s": properties.get('duration_s', 0),
                "provider": 'radar2-custom',
                "algorithm": properties.get('algorithm', algorithm),
                "route_type": properties.get('route_type', 'unknown')
            }
        }
        
        return {
            'type': 'Feature',
            'properties': formatted_properties,
            'geometry': geometry
        }

    @staticmethod
    def _route_osrm(base_url: str, coordinates: List[Tuple[float, float]], profile: str) -> Dict[str, Any]:
        """Call OSRM HTTP API for multi-point route and return a GeoJSON Feature LineString.

        `{base_url}/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2};...` with `overview=full&geometries=geojson`.
        """
        import requests
        coord_str = ';'.join([f"{lon},{lat}" for (lon, lat) in coordinates])
        url = f"{base_url.rstrip('/')}/route/v1/{profile}/{coord_str}"
        params = {
            'overview': 'full',
            'geometries': 'geojson',
            'alternatives': 'false',
            'steps': 'false',
        }
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get('routes') or []
        if not routes:
            raise RuntimeError('No OSRM route')
        r0 = routes[0]
        geom = r0.get('geometry') or {}
        if geom.get('type') != 'LineString' or not geom.get('coordinates'):
            raise RuntimeError('Invalid OSRM geometry')
        feature = {
            'type': 'Feature',
            'properties': {
                'summary': {
                    'distance_m': r0.get('distance'),
                    'duration_s': r0.get('duration'),
                    'provider': 'osrm'
                }
            },
            'geometry': geom
        }
        return feature

    @staticmethod
    def _polyline_distance(coords: List[Tuple[float, float]]) -> float:
        total = 0.0
        for i in range(1, len(coords)):
            total += RoutingService._approx_distance_meters(coords[i-1], coords[i])
        return total

    @staticmethod
    def _approx_distance_meters(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        """Rudimentary equirectangular approximation of great-circle distance."""
        import math
        lon1, lat1 = map(math.radians, a)
        lon2, lat2 = map(math.radians, b)
        x = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
        y = (lat2 - lat1)
        R = 6371000.0
        return math.hypot(x, y) * R
