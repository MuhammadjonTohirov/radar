# Radar2 Map Routing Service

A lightweight routing service that generates routes between coordinates. Supports real on-road routing via PostgreSQL (PostGIS + pgRouting) using the included Uzbekistan OSM extract.

## Overview

This service provides multiple routing algorithms to generate realistic routes between GPS coordinates:

1. **PostgreSQL (pgRouting)** - Accurate routing over OSM ways stored in PostgreSQL
2. **Smart Routing** - Intelligent pathfinding with road-like curves and realistic detours
3. **Grid Routing** - City-style routing following grid patterns
4. **Curved Routing** - Smooth curved paths for highways and rural roads
5. **Direct Routing** - Straight-line fallback for basic distance calculation

## Features

- 🐘 **PostgreSQL-backed** - Uses pgRouting + PostGIS for real roads
- 🚀 **No External Services** - Runs locally, no Docker required
- 🗺️ **Multiple Algorithms** - Different routing styles for various scenarios  
- 📍 **Realistic Routes** - Generates believable paths that follow road patterns
- 🔧 **Configurable** - Adjustable parameters for different routing needs
- 📊 **Detailed Metrics** - Distance, estimated duration, and route complexity
- 🌐 **GeoJSON Output** - Standard format for easy integration with mapping libraries

## Quick Start

```python
from routing_service import RoutingService

# Create routing service
router = RoutingService()

# Generate route
route = router.get_route(
    start_lat=40.39236025345184, 
    start_lon=71.76425536498604,
    end_lat=40.38268468389782, 
    end_lon=71.79549773559057,
    algorithm='smart'  # or 'grid', 'curved', 'direct'
)

print(f"Distance: {route['properties']['distance_m']:.0f}m")
print(f"Duration: {route['properties']['duration_s']:.0f}s")
```

## API Endpoints

- `GET /route` - Generate route between coordinates
- `GET /health` - Service health check
- `GET /algorithms` - List available routing algorithms

## Installation

```bash
cd server-map
# Minimal install for PostgreSQL backend only (no heavy builds)
pip install -r requirements.txt

# Load Uzbekistan OSM into PostgreSQL (requires osm2pgrouting installed on your system)
python -m pg_loader --pbf server-map/uzbekistan-250901.osm.pbf \
  --host localhost --port 5432 --db radar_db --user radar_user \
  --password radar_pass_dev --schema public --clean

# Start the routing service
python app.py
```

## Configuration

Edit `config.py` to set PostgreSQL connection and behavior:

- `PG_ROUTING_ENABLED=True` (default)
- `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`, `PG_SCHEMA`
- `DEFAULT_BACKEND='pg'` (preferred)

You can still tune synthetic algorithm behavior:

- Route complexity levels
- Speed calculations
- Algorithm parameters
- Output formatting options
