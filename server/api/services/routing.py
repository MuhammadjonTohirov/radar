from typing import Tuple, Dict, Any, List, Optional
from django.conf import settings
import json
import math


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

        # Try PostgreSQL/pgRouting first if enabled
        if getattr(settings, 'ROUTING_USE_PGROUTING', False):
            try:
                if len(coordinates) >= 2:
                    feature = RoutingService._route_pgr(coordinates[0], coordinates[-1])
                    if feature:
                        return feature
            except Exception as e:
                print(f"DEBUG: pgRouting failed: {e}")

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
    def _route_pgr(start: Tuple[float, float], end: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Route using PostgreSQL + pgRouting over OSM data loaded into tables
        created by osm2pgrouting (ways, ways_vertices_pgr).

        Args:
            start: (lon, lat)
            end:   (lon, lat)
        Returns GeoJSON Feature or None if routing unavailable.
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db = settings.DATABASES['default']
        if not db.get('ENGINE', '').endswith('postgresql') and 'postgis' not in db.get('ENGINE', ''):
            return None

        schema = getattr(settings, 'ROUTING_PG_SCHEMA', 'public')
        snap_tol_m = int(getattr(settings, 'ROUTING_SNAP_TOLERANCE_M', 2000))

        conn = psycopg2.connect(
            dbname=db.get('NAME'), user=db.get('USER'), password=db.get('PASSWORD'),
            host=db.get('HOST') or 'localhost', port=db.get('PORT') or '5432'
        )
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Detect geometry column names (the_geom or geom)
                cur.execute(
                    f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema=%s AND table_name='ways_vertices_pgr'
                          AND column_name IN ('the_geom','geom')
                    LIMIT 1
                    """,
                    (schema,)
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("ways_vertices_pgr not found or missing geometry column")
                v_geom = row['column_name']

                cur.execute(
                    f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema=%s AND table_name='ways' AND column_name IN ('the_geom','geom')
                    LIMIT 1
                    """,
                    (schema,)
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("ways not found or missing geometry column")
                e_geom = row['column_name']

                # Snap start/end to nearest graph vertices within tolerance
                cur.execute(
                    f"""
                    SELECT id
                    FROM {schema}.ways_vertices_pgr
                    ORDER BY {v_geom} <-> ST_SetSRID(ST_Point(%s, %s), 4326)
                    LIMIT 1
                    """,
                    (start[0], start[1])
                )
                srow = cur.fetchone()
                cur.execute(
                    f"""
                    SELECT id
                    FROM {schema}.ways_vertices_pgr
                    ORDER BY {v_geom} <-> ST_SetSRID(ST_Point(%s, %s), 4326)
                    LIMIT 1
                    """,
                    (end[0], end[1])
                )
                erow = cur.fetchone()
                if not srow or not erow:
                    return None
                source_id, target_id = int(srow['id']), int(erow['id'])

                # Compute path using dijkstra with length as cost
                cur.execute(
                    f"""
                    WITH
                    path AS (
                        SELECT * FROM pgr_dijkstra(
                            $$
                            SELECT id, source, target, length AS cost
                            FROM {schema}.ways
                            $$,
                            %s, %s, directed := true
                        )
                    ),
                    geom_path AS (
                        SELECT ST_LineMerge(ST_Union(w.{e_geom})) AS geom,
                               SUM(w.length) AS total_len
                        FROM path p
                        JOIN {schema}.ways w ON p.edge = w.id
                        WHERE p.edge <> -1
                    )
                    SELECT ST_AsGeoJSON(geom) AS geojson, COALESCE(total_len, 0) AS total_len
                    FROM geom_path
                    """,
                    (source_id, target_id)
                )
                prow = cur.fetchone()
                if not prow or not prow.get('geojson'):
                    return None
                gj = json.loads(prow['geojson'])
                coords = gj.get('coordinates') or []
                # If MultiLineString, flatten
                if gj.get('type') == 'MultiLineString':
                    flat: List[List[float]] = []
                    for seg in coords:
                        flat.extend(seg)
                    coords = flat
                distance_m = float(prow.get('total_len') or 0.0)

                # Ensure exact endpoints as provided
                if coords:
                    coords[0] = [start[0], start[1]]
                    coords[-1] = [end[0], end[1]]

                feature = {
                    'type': 'Feature',
                    'properties': {
                        'summary': {
                            'distance_m': distance_m if distance_m > 0 else RoutingService._polyline_distance([(c[0], c[1]) for c in coords]),
                            'provider': 'pgRouting',
                        }
                    },
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': coords,
                    }
                }
                return feature
        finally:
            conn.close()

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


class ExternalOSRMService:
    """Client for an external OSRM-like service (remote host).

    Builds a GeoJSON Feature LineString by concatenating step geometries when
    overview is false, or by using the top-level route geometry when available.
    """

    @staticmethod
    def get_route(coordinates: List[Tuple[float, float]], profile: str | None = None,
                  base_url: str | None = None,
                  steps: bool = True,
                  overview: str = 'false',
                  geometries: str = 'geojson') -> Dict[str, Any]:
        import requests
        if not coordinates or len(coordinates) < 2:
            raise ValueError('At least two coordinates are required')

        base = base_url or getattr(settings, 'REMOTE_OSRM_BASE_URL', '')
        prof = profile or getattr(settings, 'REMOTE_OSRM_DEFAULT_PROFILE', 'driving')
        if not base:
            raise RuntimeError('REMOTE_OSRM_BASE_URL is not configured')

        # Build path coords in lon, lat order
        coord_str = ';'.join([f"{lon},{lat}" for (lon, lat) in coordinates])
        url = f"{base.rstrip('/')}/route/v1/{prof}/{coord_str}"
        params = {
            'overview': overview,
            'steps': 'true' if steps else 'false',
            'geometries': geometries,
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get('routes') or []
        if not routes:
            raise RuntimeError('No routes in external OSRM response')
        route0 = routes[0]

        # Prefer top-level geometry if available
        geometry = route0.get('geometry')
        coords: List[List[float]] = []
        if geometry and geometry.get('type') == 'LineString' and geometry.get('coordinates'):
            coords = geometry['coordinates']
        else:
            # Build from steps when overview=false
            for leg in route0.get('legs', []) or []:
                for step in leg.get('steps', []) or []:
                    g = step.get('geometry') or {}
                    c = g.get('coordinates') or []
                    if not c:
                        continue
                    if not coords:
                        coords.extend(c)
                    else:
                        coords.extend(c[1:])

        if not coords:
            raise RuntimeError('No geometry coordinates in external OSRM response')

        feature = {
            'type': 'Feature',
            'properties': {
                'summary': {
                    'distance_m': route0.get('distance'),
                    'duration_s': route0.get('duration'),
                    'provider': 'osrm-remote',
                }
            },
            'geometry': {
                'type': 'LineString',
                'coordinates': coords
            }
        }
        return feature
