"""
Radar2 Routing Service - Core routing algorithms

This module contains the main routing logic with multiple algorithms
for generating realistic routes between GPS coordinates.

Algorithms:
- Smart: Intelligent routing with realistic detours and curves
- Grid: City-style routing following street grid patterns  
- Curved: Smooth curved routes for highways and rural areas
- Direct: Straight-line fallback for basic routing

Author: Radar2 Development Team
"""

import math
import random
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import config


@dataclass
class Coordinate:
    """Represents a GPS coordinate with latitude and longitude"""
    lat: float
    lon: float
    
    def __post_init__(self):
        """Validate coordinate values"""
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"Invalid latitude: {self.lat}")
        if not (-180 <= self.lon <= 180):
            raise ValueError(f"Invalid longitude: {self.lon}")
    
    def to_tuple(self) -> Tuple[float, float]:
        """Convert to (lon, lat) tuple for GeoJSON format"""
        return (self.lon, self.lat)


class GeographyUtils:
    """Utility functions for geographic calculations"""
    
    @staticmethod
    def haversine_distance(coord1: Coordinate, coord2: Coordinate) -> float:
        """
        Calculate the great circle distance between two points
        Returns distance in meters
        """
        lat1, lon1 = math.radians(coord1.lat), math.radians(coord1.lon)
        lat2, lon2 = math.radians(coord2.lat), math.radians(coord2.lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return config.EARTH_RADIUS_M * c
    
    @staticmethod
    def bearing(coord1: Coordinate, coord2: Coordinate) -> float:
        """
        Calculate the initial bearing from coord1 to coord2
        Returns bearing in degrees (0-360)
        """
        lat1, lon1 = math.radians(coord1.lat), math.radians(coord1.lon)
        lat2, lon2 = math.radians(coord2.lat), math.radians(coord2.lon)
        
        dlon = lon2 - lon1
        
        y = math.sin(dlon) * math.cos(lat2)
        x = (math.cos(lat1) * math.sin(lat2) - 
             math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
        
        bearing = math.atan2(y, x)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing
    
    @staticmethod
    def destination_point(coord: Coordinate, distance_m: float, bearing_deg: float) -> Coordinate:
        """
        Calculate destination point given start point, distance and bearing
        """
        lat1 = math.radians(coord.lat)
        lon1 = math.radians(coord.lon)
        bearing_rad = math.radians(bearing_deg)
        
        angular_distance = distance_m / config.EARTH_RADIUS_M
        
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular_distance) +
            math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing_rad)
        )
        
        lon2 = lon1 + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1),
            math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2)
        )
        
        return Coordinate(math.degrees(lat2), math.degrees(lon2))
    
    @staticmethod
    def interpolate_coordinates(coord1: Coordinate, coord2: Coordinate, fraction: float) -> Coordinate:
        """
        Interpolate between two coordinates
        fraction: 0.0 = coord1, 1.0 = coord2
        """
        lat = coord1.lat + (coord2.lat - coord1.lat) * fraction
        lon = coord1.lon + (coord2.lon - coord1.lon) * fraction
        return Coordinate(lat, lon)


class RouteGenerator:
    """Base class for route generation algorithms"""
    
    def __init__(self):
        self.utils = GeographyUtils()
    
    def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
        """Generate route waypoints between start and end coordinates"""
        raise NotImplementedError("Subclasses must implement generate_route")
    
    def calculate_route_metrics(self, waypoints: List[Coordinate], algorithm: str) -> Dict[str, Any]:
        """Calculate metrics for a generated route"""
        if len(waypoints) < 2:
            return self._empty_metrics(algorithm)
        
        # Calculate total distance
        total_distance = 0
        for i in range(len(waypoints) - 1):
            total_distance += self.utils.haversine_distance(waypoints[i], waypoints[i + 1])
        
        # Determine route type based on distance and characteristics
        route_type = self._determine_route_type(total_distance, waypoints)
        
        # Calculate estimated speed and duration
        avg_speed_kmh = config.SPEEDS[route_type]
        
        # Apply speed factors
        avg_speed_kmh *= config.SPEED_FACTORS['traffic_multiplier']
        duration_hours = total_distance / 1000 / avg_speed_kmh
        duration_s = duration_hours * 3600
        
        # Add intersection and turn penalties
        turn_count = len(waypoints) - 2  # Waypoints between start and end
        duration_s += turn_count * config.SPEED_FACTORS['turn_penalty']
        
        return {
            'distance_m': round(total_distance, 1),
            'duration_s': round(duration_s, 1),
            'algorithm': algorithm,
            'waypoint_count': len(waypoints),
            'estimated_speed_kmh': round(avg_speed_kmh, 1),
            'route_type': route_type,
        }
    
    def _determine_route_type(self, distance_m: float, waypoints: List[Coordinate]) -> str:
        """Determine the type of route based on distance and characteristics"""
        if distance_m < config.DISTANCE_THRESHOLDS['urban_threshold']:
            return 'urban'
        elif distance_m > config.DISTANCE_THRESHOLDS['highway_threshold']:
            return 'highway'
        elif len(waypoints) > 10:  # Many waypoints suggests complex city routing
            return 'suburban'
        else:
            return 'rural'
    
    def _empty_metrics(self, algorithm: str) -> Dict[str, Any]:
        """Return empty metrics for invalid routes"""
        return {
            'distance_m': 0,
            'duration_s': 0,
            'algorithm': algorithm,
            'waypoint_count': 0,
            'estimated_speed_kmh': 0,
            'route_type': 'unknown',
        }


class SmartRouter(RouteGenerator):
    """
    Smart routing algorithm that generates realistic routes with intelligent detours
    
    This algorithm creates believable routes by:
    - Adding realistic detours based on distance
    - Following likely road patterns
    - Adjusting complexity based on urban vs highway routing
    """
    
    def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
        distance = self.utils.haversine_distance(start, end)
        
        # Use direct route for very short distances
        if distance < config.DISTANCE_THRESHOLDS['min_route_distance']:
            return [start, end]
        
        # Determine routing style based on distance
        if distance < config.DISTANCE_THRESHOLDS['urban_threshold']:
            return self._generate_urban_route(start, end, distance)
        elif distance > config.DISTANCE_THRESHOLDS['highway_threshold']:
            return self._generate_highway_route(start, end, distance)
        else:
            return self._generate_suburban_route(start, end, distance)
    
    def _generate_urban_route(self, start: Coordinate, end: Coordinate, distance: float) -> List[Coordinate]:
        """Generate urban route with more waypoints and detours"""
        config_urban = config.SMART_ROUTING
        detour_factor = config_urban['urban_factor']
        waypoint_density = config_urban['waypoint_density']
        
        # Calculate number of waypoints
        num_waypoints = max(3, int(distance / 1000 * waypoint_density * 3))  # More waypoints for urban
        
        return self._generate_curved_waypoints(start, end, num_waypoints, detour_factor)
    
    def _generate_highway_route(self, start: Coordinate, end: Coordinate, distance: float) -> List[Coordinate]:
        """Generate highway route with minimal detours"""
        config_smart = config.SMART_ROUTING
        detour_factor = config_smart['highway_factor']
        waypoint_density = config_smart['waypoint_density']
        
        # Fewer waypoints for highway routes
        num_waypoints = max(2, int(distance / 1000 * waypoint_density * 0.5))
        
        return self._generate_curved_waypoints(start, end, num_waypoints, detour_factor)
    
    def _generate_suburban_route(self, start: Coordinate, end: Coordinate, distance: float) -> List[Coordinate]:
        """Generate suburban route with moderate complexity"""
        config_smart = config.SMART_ROUTING
        detour_factor = config_smart['detour_factor']
        waypoint_density = config_smart['waypoint_density']
        
        num_waypoints = max(2, int(distance / 1000 * waypoint_density))
        
        return self._generate_curved_waypoints(start, end, num_waypoints, detour_factor)
    
    def _generate_curved_waypoints(self, start: Coordinate, end: Coordinate, 
                                   num_waypoints: int, detour_factor: float) -> List[Coordinate]:
        """Generate waypoints with realistic curves and detours"""
        if num_waypoints <= 2:
            return [start, end]
        
        waypoints = [start]
        base_bearing = self.utils.bearing(start, end)
        total_distance = self.utils.haversine_distance(start, end)
        
        # Generate intermediate waypoints
        for i in range(1, num_waypoints - 1):
            progress = i / (num_waypoints - 1)
            
            # Base position along straight line
            base_point = self.utils.interpolate_coordinates(start, end, progress)
            
            # Add realistic detour
            detour_distance = total_distance * (detour_factor - 1) * 0.3
            detour_bearing = base_bearing + random.uniform(-45, 45)
            
            # Create curved offset using sine wave for natural curves
            curve_offset = math.sin(progress * math.pi) * detour_distance
            final_bearing = detour_bearing + random.uniform(-20, 20)
            
            waypoint = self.utils.destination_point(base_point, curve_offset, final_bearing)
            waypoints.append(waypoint)
        
        waypoints.append(end)
        return waypoints


class GridRouter(RouteGenerator):
    """
    Grid routing algorithm for city-style routing
    
    Simulates city street grid patterns with right-angle turns
    and block-by-block navigation typical of urban areas.
    """
    
    def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
        config_grid = config.GRID_ROUTING
        block_size_m = config_grid['block_size_km'] * 1000
        
        distance = self.utils.haversine_distance(start, end)
        
        if distance < config.DISTANCE_THRESHOLDS['min_route_distance']:
            return [start, end]
        
        # Calculate grid-based waypoints
        lat_diff = end.lat - start.lat
        lon_diff = end.lon - start.lon
        
        # Approximate number of blocks to traverse
        blocks_lat = abs(lat_diff) / (block_size_m / 111000)  # Rough lat degree conversion
        blocks_lon = abs(lon_diff) / (block_size_m / (111000 * math.cos(math.radians(start.lat))))
        
        total_blocks = int(blocks_lat + blocks_lon)
        
        if total_blocks <= 2:
            return [start, end]
        
        waypoints = [start]
        current = start
        
        # Generate grid-like waypoints
        for i in range(1, min(total_blocks, 15)):  # Limit waypoints for performance
            progress = i / total_blocks
            
            # Alternate between moving in lat and lon directions (grid pattern)
            if i % 2 == 1:  # Move in longitude direction
                new_lon = start.lon + (lon_diff * progress)
                new_coord = Coordinate(current.lat, new_lon)
            else:  # Move in latitude direction  
                new_lat = start.lat + (lat_diff * progress)
                new_coord = Coordinate(new_lat, current.lon)
            
            waypoints.append(new_coord)
            current = new_coord
        
        waypoints.append(end)
        return waypoints


class CurvedRouter(RouteGenerator):
    """
    Curved routing algorithm for smooth highway and rural routes
    
    Generates smooth curved paths suitable for highway driving
    with gentle curves and minimal sharp turns.
    """
    
    def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
        config_curved = config.CURVED_ROUTING
        segment_length_m = config_curved['segment_length_km'] * 1000
        
        distance = self.utils.haversine_distance(start, end)
        
        if distance < segment_length_m:
            return [start, end]
        
        num_segments = int(distance / segment_length_m)
        num_segments = min(num_segments, 20)  # Limit for performance
        
        if num_segments <= 1:
            return [start, end]
        
        waypoints = [start]
        base_bearing = self.utils.bearing(start, end)
        
        # Generate smooth curves
        for i in range(1, num_segments):
            progress = i / num_segments
            
            # Base position
            base_point = self.utils.interpolate_coordinates(start, end, progress)
            
            # Add smooth curve using cosine function
            curve_intensity = config_curved['curve_intensity']
            curve_offset = math.cos(progress * 2 * math.pi) * distance * curve_intensity * 0.1
            
            # Vary the curve direction slightly
            bearing_variation = config_curved['variation_factor'] * random.uniform(-30, 30)
            curve_bearing = base_bearing + 90 + bearing_variation  # Perpendicular offset
            
            curved_point = self.utils.destination_point(base_point, abs(curve_offset), curve_bearing)
            waypoints.append(curved_point)
        
        waypoints.append(end)
        return waypoints


class DirectRouter(RouteGenerator):
    """
    Direct routing algorithm - straight line between points
    
    Fallback algorithm that provides simple straight-line routing
    for basic distance and direction calculation.
    """
    
    def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
        return [start, end]


class RoutingService:
    """
    Main routing service that coordinates different routing algorithms
    
    This is the primary interface for route generation, providing
    a unified API across all routing algorithms.
    """
    
    def __init__(self):
        self.algorithms = {
            'smart': SmartRouter(),
            'grid': GridRouter(),
            'curved': CurvedRouter(),
            'direct': DirectRouter(),
        }
        # Register PostgreSQL-backed router if available (preferred)
        self._register_pg_router_if_available()
        # Register OSM-backed router if PBF exists and deps are present
        self._register_osm_router_if_available()
    
    def get_route(self, start_lat: float, start_lon: float, 
                  end_lat: float, end_lon: float, 
                  algorithm: str = None) -> Dict[str, Any]:
        """
        Generate a route between two coordinates
        
        Args:
            start_lat: Starting latitude
            start_lon: Starting longitude
            end_lat: Ending latitude
            end_lon: Ending longitude
            algorithm: Routing algorithm to use ('smart', 'grid', 'curved', 'direct')
            
        Returns:
            GeoJSON Feature with route geometry and properties
        """
        if algorithm is None:
            # Prefer configured backend; fall back to synthetic
            preferred = getattr(config, 'DEFAULT_BACKEND', None)
            if preferred and preferred in self.algorithms:
                algorithm = preferred
            else:
                algorithm = getattr(config, 'FALLBACK_ALGORITHM', 'smart')
        
        if algorithm not in self.algorithms:
            raise ValueError(f"Unknown algorithm: {algorithm}. Available: {list(self.algorithms.keys())}")
        
        # Validate coordinates
        if config.DEV_SETTINGS['validate_coordinates']:
            try:
                start = Coordinate(start_lat, start_lon)
                end = Coordinate(end_lat, end_lon)
            except ValueError as e:
                raise ValueError(f"Invalid coordinates: {e}")
        else:
            start = Coordinate(start_lat, start_lon)
            end = Coordinate(end_lat, end_lon)
        
        # Generate route using selected algorithm
        router = self.algorithms[algorithm]
        waypoints = router.generate_route(start, end)
        
        # Calculate route metrics
        metrics = router.calculate_route_metrics(waypoints, algorithm)
        
        # Convert to GeoJSON format
        geojson_feature = self._create_geojson_feature(waypoints, metrics)
        
        return geojson_feature
    
    def _create_geojson_feature(self, waypoints: List[Coordinate], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Convert waypoints and metrics to GeoJSON Feature format"""
        coordinates = [coord.to_tuple() for coord in waypoints]
        
        # Simplify coordinates if too many (for performance)
        max_coords = config.GEOJSON_CONFIG['max_coordinates']
        if len(coordinates) > max_coords:
            step = len(coordinates) // max_coords
            coordinates = coordinates[::step]
            coordinates.append(waypoints[-1].to_tuple())  # Always include end point
        
        feature = {
            "type": "Feature",
            "properties": metrics,
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }
        
        return feature
    
    def get_available_algorithms(self) -> List[Dict[str, str]]:
        """Return list of available routing algorithms with descriptions"""
        algs = [
            {
                "name": "pg",
                "description": "pgRouting over PostgreSQL/PostGIS using imported OSM ways",
                "best_for": "Accurate on-road routing in Uzbekistan extract"
            },
            {
                "name": "smart",
                "description": "Intelligent routing with realistic detours and urban/highway awareness",
                "best_for": "General purpose routing with realistic paths"
            },
            {
                "name": "grid", 
                "description": "City-style routing following street grid patterns",
                "best_for": "Urban areas with regular street grids"
            },
            {
                "name": "curved",
                "description": "Smooth curved routes suitable for highways and rural areas", 
                "best_for": "Highway and rural routing with gentle curves"
            },
            {
                "name": "direct",
                "description": "Straight-line routing for basic distance calculation",
                "best_for": "Simple distance and bearing calculations"
            }
        ]
        if 'osm' in self.algorithms:
            algs.insert(0, {
                "name": "osm",
                "description": "OSM graph-based routing using local PBF (real roads)",
                "best_for": "Accurate on-road routing within provided map area"
            })
        return algs

    # ---------------------------------------------------------------------
    # OSM Graph-backed Router Registration
    # ---------------------------------------------------------------------
    def _register_osm_router_if_available(self):
        """Register an OSM-backed router if local PBF and deps are available."""
        try:
            pbf = getattr(config, 'OSM_PBF_PATH', None)
            if not pbf:
                return
            # Attempt to import heavy deps lazily
            from pyrosm import OSM  # type: ignore
            import networkx as nx  # type: ignore
            from scipy.spatial import cKDTree  # type: ignore
            import pandas as pd  # type: ignore

            class OSMGraphRouter(RouteGenerator):
                def __init__(self, pbf_path: str):
                    super().__init__()
                    self.pbf_path = pbf_path
                    self.G = None  # networkx.DiGraph
                    self._nodes_df = None
                    self._kdtree = None
                    self._node_coords = None  # ndarray [[lon,lat],...]
                    self._load_graph()

                def _load_graph(self):
                    osm = OSM(self.pbf_path)
                    # Get driving network edges and nodes
                    edges = osm.get_network(network_type='driving')
                    nodes = osm.get_network(network_type='driving', nodes=True)
                    if nodes is None or edges is None or len(edges) == 0:
                        raise RuntimeError('Empty OSM network from PBF')

                    import networkx as nx
                    G = nx.DiGraph()

                    # Build node dataframe with id, lon, lat
                    if 'id' in nodes.columns:
                        nid = 'id'
                    elif 'osmid' in nodes.columns:
                        nid = 'osmid'
                    else:
                        raise RuntimeError('Unrecognized node id column in nodes')
                    if 'lon' not in nodes.columns or 'lat' not in nodes.columns:
                        raise RuntimeError('Nodes must contain lon/lat columns')

                    nodes = nodes[[nid, 'lon', 'lat']].rename(columns={nid: 'id'})
                    for row in nodes.itertuples(index=False):
                        G.add_node(row.id, lon=float(row.lon), lat=float(row.lat))

                    # Helper to parse speed
                    def _speed_kmh(val):
                        try:
                            if isinstance(val, (int, float)):
                                return float(val)
                            s = str(val)
                            if 'mph' in s.lower():
                                num = float(''.join(ch for ch in s if ch.isdigit() or ch=='.'))
                                return num * 1.60934
                            num = float(''.join(ch for ch in s if ch.isdigit() or ch=='.'))
                            return num
                        except Exception:
                            return 50.0

                    # Build edges with travel_time weight
                    use_len = 'length' in edges.columns
                    for row in edges.itertuples(index=False):
                        u = getattr(row, 'u', None)
                        v = getattr(row, 'v', None)
                        if u is None or v is None:
                            continue
                        length = getattr(row, 'length', None)
                        if length is None:
                            # compute haversine between nodes as fallback
                            try:
                                n1 = G.nodes[u]
                                n2 = G.nodes[v]
                                length = self.utils.haversine_distance(Coordinate(n1['lat'], n1['lon']), Coordinate(n2['lat'], n2['lon']))
                            except Exception:
                                length = 0.0
                        speed = _speed_kmh(getattr(row, 'maxspeed', 50))
                        # meters per second
                        speed_mps = max(5.0, speed * 1000 / 3600)
                        travel_time = (length or 0.0) / speed_mps
                        G.add_edge(u, v, length=length or 0.0, travel_time=travel_time)
                        # Add reverse if not explicitly oneway
                        oneway = getattr(row, 'oneway', False)
                        if not oneway:
                            G.add_edge(v, u, length=length or 0.0, travel_time=travel_time)

                    # KDTree for nearest node queries
                    import numpy as np
                    node_coords = []
                    node_ids = []
                    for nid, data in G.nodes(data=True):
                        node_coords.append([float(data['lon']), float(data['lat'])])
                        node_ids.append(nid)
                    node_coords = np.array(node_coords)
                    self._kdtree = cKDTree(node_coords)
                    self._node_coords = node_coords
                    self._node_ids = node_ids
                    self.G = G

                def _nearest_node(self, coord: Coordinate, max_radius_m: float = 1000.0) -> Optional[int]:
                    if self._kdtree is None:
                        return None
                    # rough lon/lat degree to meters scale near equator
                    # compute distance haversine for nearest few candidates
                    import numpy as np
                    dist, idx = self._kdtree.query([coord.lon, coord.lat], k=5)
                    if isinstance(idx, np.ndarray):
                        candidates = idx
                    else:
                        candidates = [idx]
                    best = None
                    best_d = float('inf')
                    for i in candidates:
                        lon, lat = self._node_coords[i]
                        d = self.utils.haversine_distance(coord, Coordinate(lat, lon))
                        if d < best_d:
                            best_d = d
                            best = self._node_ids[i]
                    if best_d <= max_radius_m:
                        return best
                    return None

                def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
                    if self.G is None:
                        return [start, end]
                    # Snap to nearest nodes
                    u = self._nearest_node(start)
                    v = self._nearest_node(end)
                    if u is None or v is None:
                        # fall back to straight line if snapping fails
                        return [start, end]
                    import networkx as nx
                    try:
                        path = nx.shortest_path(self.G, u, v, weight='travel_time')
                    except Exception:
                        path = None
                    if not path:
                        return [start, end]
                    coords: List[Coordinate] = []
                    for nid in path:
                        data = self.G.nodes[nid]
                        coords.append(Coordinate(data['lat'], data['lon']))
                    # Ensure exact endpoints
                    if coords:
                        coords[0] = start
                        coords[-1] = end
                    return coords

            try:
                router = OSMGraphRouter(pbf)
                self.algorithms['osm'] = router
                # If backend prefers OSM by default, set DEFAULT_ALGORITHM
                if getattr(config, 'DEFAULT_BACKEND', '').lower() == 'osm':
                    # Keep DEFAULT_ALGORITHM as-is for explicit algorithm choice,
                    # but users can pass algorithm=osm to force it.
                    pass
            except Exception:
                # If graph building fails, ignore and keep synthetic routers only
                pass
        except Exception:
            # Dependencies not installed or other error – silently skip.
            return

    # ---------------------------------------------------------------------
    # PostgreSQL pgRouting-backed Router Registration
    # ---------------------------------------------------------------------
    def _register_pg_router_if_available(self):
        """Register a PostgreSQL-backed router using pgRouting if available."""
        try:
            if not getattr(config, 'PG_ROUTING_ENABLED', False):
                return
            import psycopg2  # noqa: F401
            from psycopg2.extras import RealDictCursor  # noqa: F401

            class PGRoutingRouter(RouteGenerator):
                def __init__(self):
                    super().__init__()
                    self.host = config.PG_HOST
                    self.port = config.PG_PORT
                    self.db = config.PG_DB
                    self.user = config.PG_USER
                    self.password = config.PG_PASSWORD
                    self.schema = config.PG_SCHEMA
                    self.snap_tol_m = getattr(config, 'PG_SNAP_TOLERANCE_M', 2000)
                    self._validate_schema_name()

                def _conn(self):
                    import psycopg2
                    return psycopg2.connect(
                        dbname=self.db,
                        user=self.user,
                        password=self.password,
                        host=self.host,
                        port=self.port,
                    )

                def _validate_schema_name(self):
                    # basic safeguard: allow alnum + underscore only
                    import re
                    if not re.fullmatch(r"[A-Za-z0-9_]+", self.schema):
                        raise ValueError("Invalid PG_SCHEMA; use alphanumerics/underscore only")

                def _geom_cols(self, cur):
                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema=%s AND table_name='ways_vertices_pgr'
                          AND column_name IN ('the_geom','geom')
                        LIMIT 1
                        """,
                        (self.schema,)
                    )
                    row = cur.fetchone()
                    if not row:
                        raise RuntimeError("ways_vertices_pgr missing; load OSM via osm2pgrouting")
                    v_geom = row['column_name']

                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema=%s AND table_name='ways'
                          AND column_name IN ('the_geom','geom')
                        LIMIT 1
                        """,
                        (self.schema,)
                    )
                    row = cur.fetchone()
                    if not row:
                        raise RuntimeError("ways table missing; load OSM via osm2pgrouting")
                    e_geom = row['column_name']
                    return v_geom, e_geom

                def generate_route(self, start: Coordinate, end: Coordinate, **kwargs) -> List[Coordinate]:
                    import json as _json
                    from psycopg2.extras import RealDictCursor
                    conn = self._conn()
                    try:
                        with conn.cursor(cursor_factory=RealDictCursor) as cur:
                            v_geom, e_geom = self._geom_cols(cur)

                            # Nearest vertices
                            cur.execute(
                                f"""
                                SELECT id FROM {self.schema}.ways_vertices_pgr
                                ORDER BY {v_geom} <-> ST_SetSRID(ST_Point(%s, %s), 4326)
                                LIMIT 1
                                """,
                                (start.lon, start.lat)
                            )
                            srow = cur.fetchone()
                            cur.execute(
                                f"""
                                SELECT id FROM {self.schema}.ways_vertices_pgr
                                ORDER BY {v_geom} <-> ST_SetSRID(ST_Point(%s, %s), 4326)
                                LIMIT 1
                                """,
                                (end.lon, end.lat)
                            )
                            erow = cur.fetchone()
                            if not srow or not erow:
                                return [start, end]
                            source_id, target_id = int(srow['id']), int(erow['id'])

                            # Shortest path by length
                            cur.execute(
                                f"""
                                WITH path AS (
                                    SELECT * FROM pgr_dijkstra(
                                        $$
                                        SELECT gid AS id, source, target, length AS cost
                                        FROM {self.schema}.ways
                                        $$,
                                        %s, %s, directed := true
                                    )
                                ),
                                geom_path AS (
                                    SELECT ST_LineMerge(ST_Union(w.{e_geom})) AS geom
                                    FROM path p
                                    JOIN {self.schema}.ways w ON p.edge = w.gid
                                    WHERE p.edge <> -1
                                )
                                SELECT ST_AsGeoJSON(geom) AS geojson
                                FROM geom_path
                                """,
                                (source_id, target_id)
                            )
                            prow = cur.fetchone()
                            if not prow or not prow.get('geojson'):
                                return [start, end]
                            gj = _json.loads(prow['geojson'])
                            coords = gj.get('coordinates') or []
                            if gj.get('type') == 'MultiLineString':
                                flat = []
                                for seg in coords:
                                    flat.extend(seg)
                                coords = flat
                            # Convert to Coordinate list
                            waypoints: List[Coordinate] = []
                            for lon, lat in coords:
                                waypoints.append(Coordinate(lat, lon))
                            if waypoints:
                                waypoints[0] = start
                                waypoints[-1] = end
                            if not waypoints:
                                return [start, end]
                            return waypoints
                    finally:
                        conn.close()

            # Register geometric routing with umap database
            class UmapGeometricRouter(RouteGenerator):
                def __init__(self):
                    super().__init__()
                    self.host = config.PG_HOST
                    self.port = config.PG_PORT
                    self.db = config.PG_DB
                    self.user = config.PG_USER
                    self.password = config.PG_PASSWORD
                    self.schema = config.PG_SCHEMA

                def generate_route(self, start, end):
                    """Generate route using closest road projection approach"""
                    print(f"UmapGeometricRouter: Routing from {start.lat},{start.lon} to {end.lat},{end.lon}")
                    import psycopg2
                    from psycopg2.extras import RealDictCursor
                    import json as _json
                    import math

                    try:
                        conn = psycopg2.connect(
                            host=self.host,
                            port=self.port,
                            dbname=self.db,
                            user=self.user,
                            password=self.password
                        )
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        
                        # Find the road closest to start point and project onto it
                        start_lon, start_lat = start.lon, start.lat
                        end_lon, end_lat = end.lon, end.lat
                        
                        # Get the best route using direct PostGIS road projection
                        cur.execute(f"""
                            WITH route_corridor AS (
                                -- Get roads in a corridor between start and end points
                                SELECT 
                                    ogc_fid,
                                    name,
                                    fclass,
                                    way,
                                    ST_Transform(way, 4326) as way_4326,
                                    CASE 
                                        WHEN fclass IN ('motorway', 'trunk') THEN 1
                                        WHEN fclass IN ('primary', 'secondary') THEN 2  
                                        WHEN fclass IN ('tertiary', 'unclassified') THEN 3
                                        WHEN fclass IN ('residential', 'living_street') THEN 4
                                        ELSE 5
                                    END as priority
                                FROM {self.schema}.planet_osm_roads 
                                WHERE ST_DWithin(
                                    ST_Transform(way, 4326),
                                    ST_MakeLine(
                                        ST_SetSRID(ST_Point(%s, %s), 4326),
                                        ST_SetSRID(ST_Point(%s, %s), 4326)  
                                    ),
                                    0.015  -- 1.5km buffer around direct line
                                )
                                AND fclass NOT IN ('footway', 'path', 'steps', 'cycleway')
                            ),
                            best_route AS (
                                -- Find the road that provides the best connection
                                SELECT 
                                    r.*,
                                    ST_LineLocatePoint(r.way_4326, ST_SetSRID(ST_Point(%s, %s), 4326)) as start_fraction,
                                    ST_LineLocatePoint(r.way_4326, ST_SetSRID(ST_Point(%s, %s), 4326)) as end_fraction,
                                    ST_Distance(r.way_4326, ST_SetSRID(ST_Point(%s, %s), 4326)) as start_distance,
                                    ST_Distance(r.way_4326, ST_SetSRID(ST_Point(%s, %s), 4326)) as end_distance
                                FROM route_corridor r
                                ORDER BY 
                                    (ST_Distance(r.way_4326, ST_SetSRID(ST_Point(%s, %s), 4326)) + 
                                     ST_Distance(r.way_4326, ST_SetSRID(ST_Point(%s, %s), 4326))) * r.priority
                                LIMIT 1
                            )
                            SELECT 
                                name,
                                fclass,
                                start_fraction,
                                end_fraction,
                                start_distance,
                                end_distance,
                                ST_AsGeoJSON(
                                    CASE 
                                        WHEN start_fraction <= end_fraction THEN
                                            ST_LineSubstring(way_4326, start_fraction, end_fraction)
                                        ELSE 
                                            ST_Reverse(ST_LineSubstring(way_4326, end_fraction, start_fraction))
                                    END
                                ) as route_geometry
                            FROM best_route
                        """, (start_lon, start_lat, end_lon, end_lat, 
                              start_lon, start_lat, end_lon, end_lat,
                              start_lon, start_lat, end_lon, end_lat,
                              start_lon, start_lat, end_lon, end_lat))
                        
                        result = cur.fetchone()
                        
                        if not result or not result['route_geometry']:
                            # Fallback: return direct line if no suitable road found
                            return [start, end]
                        
                        # Parse the road geometry
                        geom = _json.loads(result['route_geometry'])
                        
                        if geom['type'] != 'LineString' or not geom['coordinates']:
                            return [start, end]
                        
                        # Convert coordinates to waypoints
                        coords = geom['coordinates']
                        waypoints = [start]  # Always start with exact start point
                        
                        # Add road points (sample every few points to avoid too much detail)
                        step = max(1, len(coords) // 20)  # Max 20 intermediate points
                        for i in range(0, len(coords), step):
                            lon, lat = coords[i]
                            waypoints.append(Coordinate(lat, lon))
                        
                        # Ensure we have the final point
                        if len(coords) > 1:
                            final_lon, final_lat = coords[-1]
                            waypoints.append(Coordinate(final_lat, final_lon))
                            
                        waypoints.append(end)  # Always end with exact end point
                        
                        return waypoints
                        
                    except Exception as e:
                        import traceback
                        print(f"Geometric routing error: {e}")
                        print(f"Traceback: {traceback.format_exc()}")
                        return [start, end]
                    finally:
                        if 'conn' in locals():
                            conn.close()

                def _haversine_distance(self, coord1, coord2):
                    """Calculate distance between two coordinates in meters"""
                    import math
                    
                    lat1, lon1 = math.radians(coord1.lat), math.radians(coord1.lon)
                    lat2, lon2 = math.radians(coord2.lat), math.radians(coord2.lon)
                    
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    
                    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                    c = 2 * math.asin(math.sqrt(a))
                    r = 6371000  # Earth's radius in meters
                    
                    return c * r

            # Try a quick connectivity check
            router = PGRoutingRouter()
            # Best-effort: only register; runtime will handle errors gracefully
            self.algorithms['pg'] = router
        except Exception:
            # If anything fails, skip PG router registration silently
            return
