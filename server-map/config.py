"""
Configuration settings for Radar2 Routing Service

This file contains all configurable parameters for route generation algorithms.
Modify these values to customize routing behavior for different scenarios.
"""

# =============================================================================
# SERVER CONFIGURATION
# =============================================================================

# Flask server settings
HOST = '0.0.0.0'
PORT = 5002
DEBUG = True

# CORS settings - allow requests from main radar app
CORS_ORIGINS = [
    'http://localhost:8000',   # Django dev server
    'http://localhost:9999',   # Your custom server
    'http://127.0.0.1:8000',
    'http://127.0.0.1:9999'
]

# =============================================================================
# OSM GRAPH BACKEND (OPTIONAL)
# =============================================================================

# Path to local OSM PBF file (e.g., Uzbekistan extract). If provided and
# dependencies are installed, the routing service can use a real road graph.
OSM_PBF_PATH = 'server-map/uzbekistan-250901.osm.pbf'

# Select routing backend/algorithm default. Options:
#  - 'osm'      -> use OSM graph (pyrosm+networkx) when available
#  - 'smart'    -> synthetic smart algorithm (default fallback)
#  - 'grid'/'curved'/'direct' -> other synthetic algorithms
DEFAULT_ALGORITHM = 'smart'
DEFAULT_BACKEND = 'osm'

# =============================================================================
# ROUTING ALGORITHM PARAMETERS
# =============================================================================

# Default routing algorithm ('smart', 'grid', 'curved', 'direct')
DEFAULT_ALGORITHM = 'smart'

# Smart routing configuration
SMART_ROUTING = {
    'detour_factor': 1.2,       # Route length multiplier (1.0 = straight line, 1.5 = 50% longer)
    'waypoint_density': 0.3,    # Waypoints per km (higher = more detailed route)
    'urban_factor': 1.4,        # Extra detour factor for city routing
    'highway_factor': 1.1,      # Minimal detour for highway-style routing
    'curve_smoothness': 0.7,    # How smooth the curves are (0-1)
}

# Grid routing configuration (city-style)
GRID_ROUTING = {
    'block_size_km': 0.5,       # Average city block size in kilometers
    'grid_alignment': 0.8,      # How strictly routes follow grid (0-1)
    'diagonal_preference': 0.3,  # Tendency to use diagonal streets
}

# Curved routing configuration (highways/rural)
CURVED_ROUTING = {
    'curve_intensity': 0.5,     # How pronounced curves are (0-1)
    'segment_length_km': 2.0,   # Length of each curve segment
    'variation_factor': 0.2,    # Random variation in curve direction
}

# =============================================================================
# SPEED AND TIME CALCULATIONS  
# =============================================================================

# Average speeds for different route types (km/h)
SPEEDS = {
    'urban': 35,        # City driving with traffic lights
    'suburban': 50,     # Suburban roads
    'highway': 80,      # Highway/motorway
    'rural': 60,        # Country roads
}

# Speed calculation factors
SPEED_FACTORS = {
    'traffic_multiplier': 0.7,      # Reduce speed for traffic simulation
    'intersection_delay': 15,       # Extra seconds per intersection
    'turn_penalty': 5,              # Extra seconds per significant turn
}

# =============================================================================
# GEOGRAPHIC CALCULATIONS
# =============================================================================

# Earth radius for distance calculations (meters)
EARTH_RADIUS_M = 6371000

# Coordinate precision (decimal places)
COORD_PRECISION = 6

# Distance thresholds
DISTANCE_THRESHOLDS = {
    'min_route_distance': 50,       # Minimum distance for complex routing (meters)
    'urban_threshold': 5000,        # Distance below which to use urban routing (meters)  
    'highway_threshold': 20000,     # Distance above which to prefer highway routing (meters)
}

# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

# GeoJSON output settings
GEOJSON_CONFIG = {
    'include_waypoints': True,      # Include intermediate waypoints in output
    'simplify_tolerance': 0.0001,   # Coordinate simplification tolerance
    'max_coordinates': 200,         # Maximum coordinates in output (for performance)
}

# Property fields to include in route response
ROUTE_PROPERTIES = [
    'distance_m',           # Total distance in meters
    'duration_s',           # Estimated duration in seconds  
    'algorithm',            # Algorithm used for routing
    'waypoint_count',       # Number of waypoints generated
    'estimated_speed_kmh',  # Average estimated speed
    'route_type',           # Type of route (urban/suburban/highway/rural)
]

# =============================================================================
# DEBUGGING AND LOGGING
# =============================================================================

# Logging configuration
LOGGING = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_routes': False,    # Log detailed route information (can be verbose)
}

# Development settings
DEV_SETTINGS = {
    'enable_debug_endpoints': True,     # Enable /debug/* endpoints
    'validate_coordinates': True,       # Validate input coordinates
    'cache_routes': False,              # Cache generated routes (disabled for development)
}
