# Radar2 Map Routing Service

A lightweight routing service that generates routes between coordinates without external dependencies.

## Overview

This service provides multiple routing algorithms to generate realistic routes between GPS coordinates:

1. **Smart Routing** - Intelligent pathfinding with road-like curves and realistic detours
2. **Grid Routing** - City-style routing following grid patterns
3. **Curved Routing** - Smooth curved paths for highways and rural roads
4. **Direct Routing** - Straight-line fallback for basic distance calculation

## Features

- 🚀 **No External Dependencies** - Pure Python implementation
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
pip install -r requirements.txt
python app.py
```

## Configuration

Edit `config.py` to customize routing behavior:

- Route complexity levels
- Speed calculations
- Algorithm parameters
- Output formatting options