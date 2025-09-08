# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Radar2 is a comprehensive radar detection system with a multi-component architecture:

1. **Django Backend** (`server/`) - PostGIS-powered REST API with polygon-based radar detection
2. **Flutter Mobile App** (`mobile-radar/`) - Real-time navigation with radar alerts and authentication
3. **Custom Routing Service** (`server-map/`) - Flask-based service with PostgreSQL pgRouting for realistic route generation
4. **Docker Infrastructure** - Multi-service containerized development environment

## Development Commands

### Django Backend (server/)
- **Install dependencies**: `pip install -r requirements.txt`
- **Run development server**: `python manage.py runserver 9999`
- **Run with custom routing**: `CUSTOM_ROUTING_URL=http://localhost:5002 python manage.py runserver 9999`
- **Database migrations**: `python manage.py makemigrations && python manage.py migrate`
- **Create superuser**: `python manage.py createsuperuser`
- **Run tests**: `python manage.py test`
- **Shell access**: `python manage.py shell`

### Flutter Mobile App (mobile-radar/)
- **Install dependencies**: `flutter pub get`
- **Run on Android**: `flutter run -d emulator --dart-define=API_BASE_URL=http://192.168.1.124:9999/api/`
- **Run on iOS**: `flutter run -d ios --dart-define=API_BASE_URL=http://192.168.1.124:9999/api/`
- **Build APK**: `flutter build apk`
- **Code analysis**: `flutter analyze`
- **Format code**: `flutter format .`
- **Run tests**: `flutter test`

### Custom Routing Service (server-map/)
- **Install dependencies**: `pip install -r requirements.txt`
- **Start service**: `python app.py` (runs on port 5002)
- **Load OSM data**: `python -m pg_loader --pbf uzbekistan-250901.osm.pbf --host localhost --db radar_db --user radar_user --password radar_pass_dev`
- **Run tests**: `python test_routing.py`

### Docker Environment
- **Start all services**: `docker compose up -d`
- **View logs**: `docker compose logs -f [service_name]`
- **Stop all services**: `docker compose down`
- **Rebuild images**: `docker compose build`
- **Run with OSRM region**: `OSRM_REGION=uzbekistan docker compose up -d`

### Integration Testing
- **Test routing integration**: `python test_integration.py`

## Architecture Overview

### Multi-Service Architecture
The system uses a microservices approach with three main components that can be developed and deployed independently:

- **Main API** (port 9999): Django REST API for radar management and mobile client endpoints
- **Routing Service** (port 5002): Specialized Flask service for route generation with multiple algorithms
- **Mobile Client**: Flutter app connecting to main API with real-time location tracking

### Django Backend Structure (`server/`)

#### Key Apps
- **`radars/`**: Core radar models with polygon-based detection areas, verification system, and analytics
- **`api/`**: REST API endpoints, serializers, and mobile client integration
- **`frontend/`**: Web-based admin interface with MapLibre integration

#### Core Models
- **`Radar`**: Polygon-based detection areas with verification workflow and analytics tracking
- **`RadarReport`**: Community reporting system for radar status updates
- **`DetectionLog`**: Anonymous analytics for radar effectiveness measurement

#### API Architecture
- **Spatial Filtering**: Bounding box and proximity-based radar queries using PostGIS
- **Authentication**: JWT and Token-based auth with OTP verification for mobile clients  
- **GeoJSON Serialization**: Direct geographic data format for map integration
- **Permission System**: Read-only for anonymous, verified radars only for non-authenticated users

### Flutter Mobile App Architecture (`mobile-radar/`)

#### Core Services
- **`ApiClient`**: HTTP client with JWT auth, token refresh, and API endpoint management
- **`LocalDb`**: SQLite for offline radar data storage with sync capabilities
- **`AlertsEngine`**: Real-time proximity detection with audio/vibration alerts
- **`GeoUtils`**: Geospatial calculations (haversine distance, bearings, sector parsing)

#### Navigation System
- **MapLibre Integration**: Custom radar overlays with detection sectors and route visualization
- **Dual Location Modes**: Overview (static) vs Navigation (real-time following with 3D camera)
- **Smart Alerts**: Bearing-based lookahead calculations with configurable thresholds

#### State Management
- **ViewModels**: ChangeNotifier pattern for screen state management
- **HomeScreenViewModel**: Central state coordination for map, location, radar data, and navigation

### Custom Routing Service Architecture (`server-map/`)

#### Routing Algorithms
- **PostgreSQL (pgRouting)**: Real road routing using OSM data with PostGIS backend
- **Smart**: Intelligent routing with realistic detours and urban/highway awareness  
- **Grid**: City-style routing following street grid patterns
- **Curved**: Smooth highway-style routing for rural roads
- **Direct**: Straight-line fallback for basic distance calculation

#### Integration Pattern
The main Django API automatically detects and uses the custom routing service when available, falling back to synthetic routing when the service is unavailable.

### Data Flow Architecture

#### Authentication Flow
1. Mobile app requests OTP for phone number
2. User enters OTP code for verification  
3. Backend returns JWT/Token pair for API authorization
4. Mobile stores tokens and handles automatic refresh

#### Radar Detection Flow
1. Background location tracking in mobile app
2. Local SQLite database stores radar data with periodic backend sync
3. Real-time proximity calculations using radar polygon sectors
4. Audio/vibration alerts triggered based on configurable thresholds
5. Anonymous detection logging for analytics

#### Route Planning Flow
1. User selects destination in mobile app
2. App requests route from main API
3. Main API delegates to custom routing service (if available) or uses fallback
4. Route coordinates returned with radar impact analysis
5. Mobile app renders route with radar overlays and impact visualization

## Configuration Details

### Environment Variables
- **Django**: `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG`, `ROUTING_PROVIDER`, `CUSTOM_ROUTING_URL`
- **Flutter**: `API_BASE_URL` (via dart-define)
- **Docker**: `OSRM_REGION` for map data selection

### Database Configuration
- **Main Database**: PostgreSQL with PostGIS extension for spatial queries
- **Mobile Database**: SQLite with geographic data types for offline capability
- **Routing Database**: PostgreSQL with pgRouting for OSM-based routing

### API Endpoints Overview
- **`/api/radars/`**: Spatial radar queries with filtering
- **`/api/auth/otp/`**: Phone-based authentication  
- **`/api/mobile/radars/updates/`**: Mobile client data sync
- **`/api/route/`**: Route generation with radar impact analysis
- **`/route` (port 5002)**: Custom routing service algorithms

### Security Considerations
- JWT tokens with refresh mechanism
- CORS configuration for mobile client access
- Permission-based access control (verified radars only for public)
- Environment-based configuration for secrets
- Anonymous analytics without user tracking

## Key Technical Patterns

### Polygon-Based Detection
Unlike simple point+radius systems, this uses actual polygon geometries for radar coverage areas, enabling irregular shapes and more accurate detection zones that match real-world radar installations.

### Microservices Integration
The routing service demonstrates a pattern for splitting complex functionality into specialized services while maintaining backward compatibility through automatic fallback mechanisms.

### Offline-First Mobile Architecture
The Flutter app prioritizes offline capability with local SQLite storage, periodic sync, and graceful degradation when backend connectivity is unavailable.

### Verification-Driven Data Quality
Community reporting and admin verification workflow ensures data quality while leveraging crowd-sourced updates for radar status and accuracy.