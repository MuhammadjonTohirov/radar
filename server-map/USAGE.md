# Radar2 Routing Service - Usage Guide

Complete guide for using the Radar2 Routing Service to generate routes between GPS coordinates.

## Quick Start

### 1. Install Dependencies

```bash
cd server-map
pip install -r requirements.txt
```

### 2. Load Uzbekistan OSM into PostgreSQL (no Docker)

Requires PostgreSQL with PostGIS and pgRouting, plus `osm2pgrouting`.

```bash
python -m pg_loader --pbf server-map/uzbekistan-250901.osm.pbf \
  --host localhost --port 5432 --db radar_db --user radar_user \
  --password radar_pass_dev --schema public --clean
```

### 3. Start the Service

```bash
python app.py
```

The service starts on `http://localhost:5002` and prefers `pg` backend.

### 3. Test the Service

```bash
# Test with your coordinates
curl "http://localhost:5002/route?from=40.39236025345184,71.76425536498604&to=40.38268468389782,71.79549773559057&algorithm=smart"
```

## API Reference

### GET /route

Generate a route between two coordinates.

**Parameters:**
- `from` (required): Start coordinate as "lat,lon"
- `to` (required): End coordinate as "lat,lon"  
- `algorithm` (optional): Routing algorithm to use
  - `pg` (default): PostgreSQL pgRouting (real roads from OSM)
  - `smart`: Intelligent routing with realistic detours
  - `grid`: City-style grid routing
  - `curved`: Smooth highway-style routing
  - `direct`: Straight-line routing

**Example Request:**
```bash
GET /route?from=40.7128,-74.0060&to=40.7589,-73.9851&algorithm=smart
```

**Example Response:**
```json
{
  "type": "Feature",
  "properties": {
    "distance_m": 8547.2,
    "duration_s": 876.4,
    "algorithm": "smart",
    "waypoint_count": 6,
    "estimated_speed_kmh": 35.0,
    "route_type": "urban"
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [-74.0060, 40.7128],
      [-74.0023, 40.7205],
      [-73.9934, 40.7341],
      [-73.9886, 40.7456],
      [-73.9851, 40.7589]
    ]
  }
}
```

### GET /algorithms

Get list of available routing algorithms.

**Example Response:**
```json
{
  "algorithms": [
    {
      "name": "smart",
      "description": "Intelligent routing with realistic detours and urban/highway awareness",
      "best_for": "General purpose routing with realistic paths"
    },
    {
      "name": "grid",
      "description": "City-style routing following street grid patterns", 
      "best_for": "Urban areas with regular street grids"
    }
  ],
  "default": "smart"
}
```

### GET /health

Service health check.

**Example Response:**
```json
{
  "status": "healthy",
  "service": "Radar2 Routing Service",
  "version": "1.0.0",
  "algorithms_available": 5,
  "default_algorithm": "pg"
}
```

## Algorithm Comparison

### Smart Algorithm
- **Best for:** General purpose routing
- **Features:** Realistic detours, urban/highway awareness
- **Route style:** Follows likely road patterns with intelligent curves

### Grid Algorithm  
- **Best for:** City routing with regular street grids
- **Features:** Right-angle turns, block-by-block navigation
- **Route style:** Manhattan-style grid patterns

### Curved Algorithm
- **Best for:** Highway and rural routing
- **Features:** Smooth curves, minimal sharp turns
- **Route style:** Gentle curves suitable for high-speed roads

### Direct Algorithm
- **Best for:** Basic distance calculation
- **Features:** Straight-line path
- **Route style:** Direct path between points

## Configuration

Edit `config.py` to customize routing behavior:

```python
# Change default algorithm
DEFAULT_ALGORITHM = 'grid'

# Adjust smart routing behavior
SMART_ROUTING = {
    'detour_factor': 1.3,        # More detours
    'waypoint_density': 0.5,     # More detailed routes
    'urban_factor': 1.5,         # Higher urban complexity
}

# Modify speed calculations
SPEEDS = {
    'urban': 30,        # Slower urban speeds
    'highway': 90,      # Faster highway speeds
}
```

## Integration with Main Radar API

### Update Django Routing Service

Replace the OSRM integration in your main API:

```python
# In api/services/routing.py
import requests

def get_route_coords(coordinates, profile=None):
    """Get route from our custom routing service"""
    start_lat, start_lon = coordinates[0][1], coordinates[0][0] 
    end_lat, end_lon = coordinates[1][1], coordinates[1][0]
    
    url = f"http://localhost:5002/route"
    params = {
        'from': f"{start_lat},{start_lon}",
        'to': f"{end_lat},{end_lon}",
        'algorithm': 'smart'
    }
    
    response = requests.get(url, params=params, timeout=5)
    response.raise_for_status()
    return response.json()
```

### Test Integration

```bash
# Test your main API with the new routing service
curl "http://localhost:9999/api/route/?from=71.76425536498604,40.39236025345184&to=71.79549773559057,40.38268468389782"
```

## Testing

### Run Comprehensive Tests

```bash
python test_routing.py
```

This will test all algorithms with various coordinate pairs and generate a `sample_routes.json` file for visualization.

### Manual Testing

Test individual algorithms:

```bash
# Test smart routing
curl "http://localhost:5002/route?from=40.39236,71.76425&to=40.38268,71.79549&algorithm=smart"

# Test grid routing  
curl "http://localhost:5002/route?from=40.39236,71.76425&to=40.38268,71.79549&algorithm=grid"

# Compare with direct routing
curl "http://localhost:5002/route?from=40.39236,71.76425&to=40.38268,71.79549&algorithm=direct"
```

## Troubleshooting

### Common Issues

1. **Port 5002 already in use**
   ```bash
   # Change port in config.py
   PORT = 5003
   ```

2. **Import errors**
   ```bash
   pip install -r requirements.txt
   ```

3. **CORS errors from main app**
   ```python
   # Add your app's URL to config.py
   CORS_ORIGINS = [
       'http://localhost:9999',  # Your server port
       'http://localhost:8000'   # Django dev server
   ]
   ```

4. **Unrealistic route distances**
   - Adjust `detour_factor` in config.py
   - Try different algorithms for your use case

### Debug Endpoints

When running in development mode:

```bash
# Test all algorithms
GET /debug/test

# View configuration
GET /debug/config
```

## Performance Notes

- **Smart algorithm:** Most realistic but slightly slower
- **Direct algorithm:** Fastest for simple distance calculation
- **Grid/Curved algorithms:** Good balance of realism and performance
- **Coordinate limit:** Routes are limited to 200 coordinates for performance

## Next Steps

1. **Visualize Routes:** Use the generated GeoJSON with mapping libraries
2. **Cache Routes:** Implement caching for frequently requested routes  
3. **Add Traffic:** Integrate real-time traffic data for duration calculation
4. **Custom Algorithms:** Implement domain-specific routing algorithms

The service is designed to be lightweight, fast, and easily extensible for your specific routing needs.
