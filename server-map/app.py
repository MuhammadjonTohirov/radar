"""
Radar2 Map Routing Service - Flask API Server

A lightweight Flask API server that provides routing services
for the Radar2 application without external dependencies.

Endpoints:
- GET /route - Generate route between coordinates
- GET /health - Health check
- GET /algorithms - List available algorithms
- GET /debug/test - Test endpoint with sample data (dev only)

Usage:
    python app.py

The server will start on http://localhost:5002 by default.
Configure port and other settings in config.py
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import logging
from typing import Dict, Any
import traceback

from routing_service import RoutingService
import config

# Initialize Flask application
app = Flask(__name__)

# Configure CORS to allow requests from the main Radar application
CORS(app, origins=config.CORS_ORIGINS)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOGGING['level']),
    format=config.LOGGING['format']
)
logger = logging.getLogger(__name__)

# Initialize routing service
routing_service = RoutingService()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/route', methods=['GET'])
def get_route():
    """
    Generate a route between two coordinates
    
    Query Parameters:
        from: Start coordinate as "lat,lon" (e.g., "40.7128,-74.0060")
        to: End coordinate as "lat,lon" (e.g., "40.7589,-73.9851")
        algorithm: Routing algorithm to use (optional)
                  Options: 'smart', 'grid', 'curved', 'direct'
                  Default: 'smart'
    
    Example:
        GET /route?from=40.7128,-74.0060&to=40.7589,-73.9851&algorithm=smart
    
    Returns:
        GeoJSON Feature with route geometry and properties
    """
    try:
        # Parse coordinates from query parameters
        start_coord = request.args.get('from')
        end_coord = request.args.get('to')
        algorithm = request.args.get('algorithm', config.DEFAULT_ALGORITHM)
        
        if not start_coord or not end_coord:
            return jsonify({
                'error': 'Missing required parameters',
                'message': 'Both "from" and "to" coordinates are required',
                'example': '/route?from=40.7128,-74.0060&to=40.7589,-73.9851'
            }), 400
        
        # Parse coordinate strings
        try:
            start_parts = start_coord.split(',')
            end_parts = end_coord.split(',')
            
            if len(start_parts) != 2 or len(end_parts) != 2:
                raise ValueError("Invalid coordinate format")
            
            start_lat, start_lon = float(start_parts[0]), float(start_parts[1])
            end_lat, end_lon = float(end_parts[0]), float(end_parts[1])
            
        except (ValueError, IndexError) as e:
            return jsonify({
                'error': 'Invalid coordinate format',
                'message': 'Coordinates must be in format "lat,lon"',
                'example': 'from=40.7128,-74.0060&to=40.7589,-73.9851'
            }), 400
        
        # Generate route
        route_data = routing_service.get_route(
            start_lat=start_lat,
            start_lon=start_lon, 
            end_lat=end_lat,
            end_lon=end_lon,
            algorithm=algorithm
        )
        
        # Log route generation if enabled
        if config.LOGGING.get('log_routes', False):
            logger.info(f"Generated {algorithm} route: {route_data['properties']['distance_m']:.0f}m")
        
        return jsonify(route_data)
        
    except ValueError as e:
        return jsonify({
            'error': 'Invalid input',
            'message': str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Error generating route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to generate route'
        }), 500


@app.route('/algorithms', methods=['GET'])
def get_algorithms():
    """
    Get list of available routing algorithms
    
    Returns:
        List of algorithm objects with name, description, and best use cases
    """
    try:
        algorithms = routing_service.get_available_algorithms()
        return jsonify({
            'algorithms': algorithms,
            'default': config.DEFAULT_ALGORITHM
        })
    except Exception as e:
        logger.error(f"Error getting algorithms: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to get algorithm list'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    
    Returns:
        Service status and configuration information
    """
    try:
        # Test routing service with a simple route
        test_route = routing_service.get_route(0, 0, 0.01, 0.01, 'direct')
        service_ok = test_route is not None
        
        return jsonify({
            'status': 'healthy' if service_ok else 'degraded',
            'service': 'Radar2 Routing Service',
            'version': '1.0.0',
            'algorithms_available': len(routing_service.algorithms),
            'default_algorithm': config.DEFAULT_ALGORITHM
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'Radar2 Routing Service',
            'error': str(e)
        }), 503


# =============================================================================
# DEBUG AND DEVELOPMENT ENDPOINTS
# =============================================================================

if config.DEV_SETTINGS.get('enable_debug_endpoints', False):
    
    @app.route('/debug/test', methods=['GET'])
    def debug_test():
        """
        Test endpoint with sample routing data
        
        Generates test routes using all available algorithms
        for debugging and development purposes.
        """
        try:
            # Test coordinates (New York area)
            test_routes = []
            start_lat, start_lon = 40.7128, -74.0060  # NYC
            end_lat, end_lon = 40.7589, -73.9851      # Central Park
            
            for algorithm in routing_service.algorithms.keys():
                route = routing_service.get_route(
                    start_lat, start_lon, end_lat, end_lon, algorithm
                )
                test_routes.append({
                    'algorithm': algorithm,
                    'route': route
                })
            
            return jsonify({
                'test_coordinates': {
                    'start': f"{start_lat},{start_lon}",
                    'end': f"{end_lat},{end_lon}"
                },
                'routes': test_routes
            })
            
        except Exception as e:
            return jsonify({
                'error': 'Test failed',
                'message': str(e)
            }), 500
    
    @app.route('/debug/config', methods=['GET'])
    def debug_config():
        """Show current configuration (development only)"""
        return jsonify({
            'default_algorithm': config.DEFAULT_ALGORITHM,
            'cors_origins': config.CORS_ORIGINS,
            'distance_thresholds': config.DISTANCE_THRESHOLDS,
            'speeds': config.SPEEDS,
            'debug_enabled': config.DEV_SETTINGS['enable_debug_endpoints']
        })


# =============================================================================
# ROOT ENDPOINT AND DOCUMENTATION
# =============================================================================

@app.route('/', methods=['GET'])
def index():
    """
    API documentation and service information
    """
    docs_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Radar2 Routing Service</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1, h2 { color: #333; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { color: #0066cc; font-weight: bold; }
            .url { font-family: monospace; background: #e8e8e8; padding: 2px 5px; }
            .example { background: #f0f8ff; padding: 10px; margin: 5px 0; border-radius: 3px; }
            .param { font-weight: bold; color: #d2691e; }
        </style>
    </head>
    <body>
        <h1>🗺️ Radar2 Routing Service</h1>
        <p>Lightweight routing service for generating realistic routes between GPS coordinates.</p>
        
        <h2>Available Endpoints</h2>
        
        <div class="endpoint">
            <h3><span class="method">GET</span> <span class="url">/route</span></h3>
            <p>Generate a route between two coordinates</p>
            <p><strong>Parameters:</strong></p>
            <ul>
                <li><span class="param">from</span> - Start coordinate as "lat,lon"</li>
                <li><span class="param">to</span> - End coordinate as "lat,lon"</li>
                <li><span class="param">algorithm</span> - Routing algorithm (smart, grid, curved, direct)</li>
            </ul>
            <div class="example">
                <strong>Example:</strong><br>
                <span class="url">/route?from=40.39236,-71.76425&to=40.38268,-71.79549&algorithm=smart</span>
            </div>
        </div>
        
        <div class="endpoint">
            <h3><span class="method">GET</span> <span class="url">/algorithms</span></h3>
            <p>Get list of available routing algorithms</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method">GET</span> <span class="url">/health</span></h3>
            <p>Service health check</p>
        </div>
        
        <h2>Routing Algorithms</h2>
        <ul>
            <li><strong>smart</strong> - Intelligent routing with realistic detours</li>
            <li><strong>grid</strong> - City-style routing following street grids</li>
            <li><strong>curved</strong> - Smooth curves for highways and rural roads</li>
            <li><strong>direct</strong> - Straight-line routing for basic calculations</li>
        </ul>
        
        <h2>Response Format</h2>
        <p>All route responses are in GeoJSON Feature format with route geometry and properties including distance, duration, and algorithm used.</p>
        
        <p><strong>Service Status:</strong> ✅ Running on port ''' + str(config.PORT) + '''</p>
    </body>
    </html>
    '''
    return render_template_string(docs_html)


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist',
        'available_endpoints': ['/route', '/algorithms', '/health', '/']
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500


# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == '__main__':
    logger.info("Starting Radar2 Routing Service...")
    logger.info(f"Available algorithms: {list(routing_service.algorithms.keys())}")
    logger.info(f"Default algorithm: {config.DEFAULT_ALGORITHM}")
    logger.info(f"CORS origins: {config.CORS_ORIGINS}")
    
    # Start Flask development server
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )