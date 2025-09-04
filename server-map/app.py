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
        start_lat: Starting latitude (required)
        start_lon: Starting longitude (required) 
        end_lat: Ending latitude (required)
        end_lon: Ending longitude (required)
        algorithm: Routing algorithm to use (optional)
                  Options: 'pg', 'osm', 'smart', 'grid', 'curved', 'direct'
                  Default: 'pg' (PostgreSQL pgRouting)
        
        OR legacy format:
        from: Start coordinate as "lat,lon" (e.g., "41.2995,69.2401")
        to: End coordinate as "lat,lon" (e.g., "41.3158,69.2785")
    
    Example:
        GET /route?start_lat=41.2995&start_lon=69.2401&end_lat=41.3158&end_lon=69.2785&algorithm=pg
        GET /route?from=41.2995,69.2401&to=41.3158,69.2785&algorithm=pg
    
    Returns:
        GeoJSON Feature with route geometry and properties
    """
    try:
        # Try new parameter format first
        start_lat = request.args.get('start_lat', type=float)
        start_lon = request.args.get('start_lon', type=float)
        end_lat = request.args.get('end_lat', type=float)
        end_lon = request.args.get('end_lon', type=float)
        algorithm = request.args.get('algorithm')
        
        # Fall back to legacy format if new format not provided
        if any(param is None for param in [start_lat, start_lon, end_lat, end_lon]):
            start_coord = request.args.get('from')
            end_coord = request.args.get('to')
            
            if not start_coord or not end_coord:
                return jsonify({
                    'error': 'Missing required parameters',
                    'message': 'Required: start_lat, start_lon, end_lat, end_lon OR from, to',
                    'examples': [
                        '/route?start_lat=41.2995&start_lon=69.2401&end_lat=41.3158&end_lon=69.2785&algorithm=pg',
                        '/route?from=41.2995,69.2401&to=41.3158,69.2785&algorithm=pg'
                    ]
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
                    'example': 'from=41.2995,69.2401&to=41.3158,69.2785'
                }), 400
        
        # Use default algorithm from config if not specified
        if algorithm is None:
            algorithm = getattr(config, 'DEFAULT_BACKEND', 'pg')
        
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
            'default': getattr(config, 'DEFAULT_BACKEND', 'pg')
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
            'default_algorithm': getattr(config, 'DEFAULT_BACKEND', 'pg')
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
            # Test coordinates (Uzbekistan - Tashkent area)
            test_routes = []
            start_lat, start_lon = 41.2995, 69.2401  # Tashkent center
            end_lat, end_lon = 41.3158, 69.2785      # Tashkent outskirts
            
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
            'default_algorithm': getattr(config, 'DEFAULT_BACKEND', 'pg'),
            'pg_routing_enabled': getattr(config, 'PG_ROUTING_ENABLED', False),
            'pg_host': getattr(config, 'PG_HOST', 'localhost'),
            'pg_db': getattr(config, 'PG_DB', 'radar_db'),
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
    """Rich, UX-focused landing page with live route demo and docs."""
    docs_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Radar2 Routing Service</title>
      <link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
      <style>
        :root {
          --bg: #0b1021; /* deep navy */
          --panel: #111634;
          --muted: #98a2b3;
          --text: #e6eaf2;
          --brand: #55d0ff;
          --accent: #a1ffbf;
          --danger: #ff7d7d;
          --code: #0f172a;
        }
        * { box-sizing: border-box; }
        body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"; background: linear-gradient(180deg, #0b1021, #0f1430 40%, #0b1021); color: var(--text); }
        .container { max-width: 1080px; margin: 0 auto; padding: 24px; }
        header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .title { font-size: 22px; font-weight: 700; letter-spacing: 0.3px; display: flex; align-items: center; gap: 10px; }
        .badge { padding: 4px 10px; border-radius: 999px; background: #13204d; color: var(--brand); font-weight: 600; font-size: 12px; }
        .grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 16px; }
        .panel { background: linear-gradient(180deg, #0f1536, #0d1230); border: 1px solid #212b57; border-radius: 12px; box-shadow: 0 6px 30px rgba(0,0,0,0.3); }
        .panel .inner { padding: 16px; }
        .row { display: flex; gap: 10px; margin-bottom: 10px; }
        label { font-size: 12px; color: var(--muted); }
        input, select { width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #273368; background: #0c122b; color: var(--text); outline: none; }
        input::placeholder { color: #6b7280; }
        .btn { padding: 10px 14px; border-radius: 10px; border: 1px solid #273368; background: #101944; color: var(--text); cursor: pointer; font-weight: 600; }
        .btn.primary { background: linear-gradient(180deg, #132b72, #101944); border-color: #2b3c7a; }
        .btn:disabled { opacity: .6; cursor: not-allowed; }
        .statbar { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }
        .chip { background: #0c122b; border: 1px solid #263166; border-radius: 999px; padding: 6px 10px; font-size: 12px; color: var(--muted); }
        .chip b { color: var(--text); }
        #map { height: 440px; border-radius: 12px; overflow: hidden; }
        pre { background: var(--code); color: #d1d5db; padding: 12px; border-radius: 8px; overflow: auto; border: 1px solid #1f2937; }
        .section-title { margin: 18px 0 10px; font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
        .legend { display:flex; gap:12px; align-items:center; font-size: 12px; color: var(--muted); }
        .sw { display:inline-block; width:22px; height:6px; border-radius: 8px; }
        .sw.route { background:#55d0ff; }
        .sw.buffer { background:#ff7d7d; opacity:.35; }
        @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
      </style>
    </head>
    <body>
      <div class="container">
        <header>
          <div class="title">🗺️ Radar2 Routing Service <span id="health" class="badge">Checking…</span></div>
          <div class="legend"><span class="sw route"></span>Route <span class="sw buffer"></span>Impact Buffer</div>
        </header>

        <div class="grid">
          <div class="panel">
            <div class="inner">
              <div class="row">
                <div style="flex:1">
                  <label>From (lat,lon)</label>
                  <input id="from" placeholder="40.39236,71.76425" />
                </div>
                <div style="flex:1">
                  <label>To (lat,lon)</label>
                  <input id="to" placeholder="40.38268,71.79549" />
                </div>
              </div>
              <div class="row">
                <div style="flex:1">
                  <label>Algorithm</label>
                  <select id="algo"></select>
                </div>
                <div style="display:flex; align-items:flex-end; gap:8px">
                  <button id="go" class="btn primary">Generate Route</button>
                  <button id="curl" class="btn">Copy cURL</button>
                </div>
              </div>
              <div class="statbar">
                <span class="chip">Distance: <b id="dist">—</b></span>
                <span class="chip">Duration: <b id="dur">—</b></span>
                <span class="chip">Provider: <b id="prov">—</b></span>
                <span class="chip">Waypoints: <b id="wps">—</b></span>
              </div>
              <div class="section-title">Map</div>
              <div id="map"></div>
              <div class="section-title">JSON Response</div>
              <pre id="out">—</pre>
            </div>
          </div>

          <div class="panel">
            <div class="inner">
              <div class="section-title">API</div>
              <p><b>GET /route</b> — Generate a route between two coordinates.</p>
              <ul>
                <li><code>?from=lat,lon</code></li>
                <li><code>?to=lat,lon</code></li>
                <li><code>?algorithm=smart|grid|curved|direct|osm</code></li>
              </ul>
              <p>Example: <code>/route?from=40.39236,71.76425&to=40.38268,71.79549&algorithm=smart</code></p>
              <div class="section-title">Endpoints</div>
              <ul>
                <li><b>GET</b> <code>/route</code></li>
                <li><b>GET</b> <code>/algorithms</code></li>
                <li><b>GET</b> <code>/health</code></li>
              </ul>
              <div class="section-title">Tips</div>
              <ul>
                <li>Use <code>osm</code> for real on‑road routing when the Uzbekistan PBF is loaded.</li>
                <li>Use <code>smart</code> for fast synthetic routes if a graph isn’t available.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
      <script>
        const map = new maplibregl.Map({
          container: 'map',
          style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
          center: [71.7761, 40.3836],
          zoom: 11
        });
        map.on('load', () => {
          map.addSource('route', { type: 'geojson', data: { type:'FeatureCollection', features:[] } });
          map.addLayer({ id:'route-line', type:'line', source:'route', paint:{ 'line-color':'#55d0ff','line-width':4,'line-opacity':0.95 } });
          map.addSource('buffer', { type: 'geojson', data: { type:'FeatureCollection', features:[] } });
          map.addLayer({ id:'buffer-fill', type:'fill', source:'buffer', paint:{ 'fill-color':'#ff7d7d','fill-opacity':0.35 } });
        });

        async function fetchHealth() {
          try { const r = await fetch('/health'); const j = await r.json();
            document.getElementById('health').textContent = j.status === 'healthy' ? 'Healthy' : 'Unhealthy';
          } catch { document.getElementById('health').textContent = 'Unknown'; }
        }

        async function loadAlgos() {
          const sel = document.getElementById('algo');
          try { const r = await fetch('/algorithms'); const j = await r.json();
            const list = j.algorithms || []; const def = j.default || 'smart';
            sel.innerHTML = '';
            list.forEach(a => { const o = document.createElement('option'); o.value = a.name; o.textContent = a.name; sel.appendChild(o); });
            if ([...sel.options].some(o => o.value === 'osm')) sel.value = 'osm'; else sel.value = def;
          } catch { sel.innerHTML = '<option value="smart">smart</option>'; }
        }

        function parseLatLon(v) {
          const parts = v.split(',').map(s => s.trim());
          if (parts.length !== 2) return null;
          let lat = parseFloat(parts[0]); let lon = parseFloat(parts[1]);
          if (Math.abs(lat) <= 90 && Math.abs(lon) > 90) { /* looks fine */ }
          else if (Math.abs(parts[1]) <= 90 && Math.abs(parts[0]) > 90) { lon = parseFloat(parts[0]); lat = parseFloat(parts[1]); }
          if (Number.isNaN(lat) || Number.isNaN(lon)) return null; return { lat, lon };
        }

        function fit(feature) {
          try {
            const coords = feature.geometry.coordinates;
            let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
            coords.forEach(([x,y])=>{ if(x<minX)minX=x; if(y<minY)minY=y; if(x>maxX)maxX=x; if(y>maxY)maxY=y; });
            map.fitBounds([[minX,minY],[maxX,maxY]], { padding: 40, duration: 600 });
          } catch {}
        }

        function buffer(feature, meters=50) {
          if (!window.turf) return null;
          try { const line = turf.lineString(feature.geometry.coordinates); return turf.buffer(line, meters, { units: 'meters' }); } catch { return null; }
        }

        async function go() {
          const from = parseLatLon(document.getElementById('from').value || '');
          const to = parseLatLon(document.getElementById('to').value || '');
          const algo = document.getElementById('algo').value || 'smart';
          if (!from || !to) { alert('Enter valid coordinates as lat,lon'); return; }
          const url = new URL('/route', window.location.origin);
          url.searchParams.set('from', `${from.lat},${from.lon}`);
          url.searchParams.set('to', `${to.lat},${to.lon}`);
          url.searchParams.set('algorithm', algo);
          document.getElementById('go').disabled = true;
          try {
            const r = await fetch(url); const j = await r.json();
            document.getElementById('out').textContent = JSON.stringify(j, null, 2);
            const s = (j.properties && (j.properties.summary || j.properties)) || {};
            document.getElementById('dist').textContent = s.distance_m ? (s.distance_m/1000).toFixed(2)+' km' : '—';
            document.getElementById('dur').textContent = s.duration_s ? (s.duration_s/60).toFixed(1)+' min' : '—';
            document.getElementById('prov').textContent = s.provider || '—';
            document.getElementById('wps').textContent = (j.geometry && j.geometry.coordinates && j.geometry.coordinates.length) || '—';
            const src = map.getSource('route'); if (src) src.setData(j);
            const bf = buffer(j, 50); const bsrc = map.getSource('buffer'); if (bsrc) bsrc.setData(bf || { type:'FeatureCollection', features:[] });
            fit(j);
          } finally { document.getElementById('go').disabled = false; }
        }

        function copyCurl() {
          const from = document.getElementById('from').value || '40.39236,71.76425';
          const to = document.getElementById('to').value || '40.38268,71.79549';
          const algo = document.getElementById('algo').value || 'smart';
          const cmd = `curl "${location.origin}/route?from=${from}&to=${to}&algorithm=${algo}"`;
          navigator.clipboard.writeText(cmd).then(()=>{ const btn = document.getElementById('curl'); const t=btn.textContent; btn.textContent='Copied!'; setTimeout(()=>btn.textContent=t, 1000); });
        }

        document.getElementById('go').addEventListener('click', go);
        document.getElementById('curl').addEventListener('click', copyCurl);
        loadAlgos(); fetchHealth();
      </script>
      <script src="https://unpkg.com/@turf/turf@6.5.0/turf.min.js"></script>
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
    logger.info(f"Default algorithm: {getattr(config, 'DEFAULT_BACKEND', 'pg')}")
    logger.info(f"CORS origins: {config.CORS_ORIGINS}")
    
    # Start Flask development server
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
