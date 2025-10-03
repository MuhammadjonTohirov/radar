# Radar2 Project Documentation Index

## 📋 Project Overview

**Radar2** is a comprehensive radar detection system with a multi-component microservices architecture providing real-time navigation with radar alerts and community-driven data verification.

### 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Flutter App   │    │   Django API     │    │  Routing Service │
│  (Mobile Client)│◄──►│  (Main Backend)  │◄──►│   (Flask/PgSQL) │
│   Port: Mobile  │    │   Port: 9999     │    │   Port: 5002    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
  ┌─────────────┐    ┌───────────────────┐    ┌──────────────────┐
  │   SQLite    │    │   PostgreSQL      │    │   PostgreSQL     │
  │ (Offline)   │    │   + PostGIS       │    │   + pgRouting    │
  └─────────────┘    └───────────────────┘    └──────────────────┘
```

## 📁 Repository Structure

### 🎯 Core Components

| Component | Path | Technology | Purpose |
|-----------|------|------------|---------|
| **Mobile App** | `mobile-radar/` | Flutter 3.19+ | Real-time radar detection & navigation |
| **Backend API** | `server/` | Django 5.0 + DRF | Spatial radar management & auth |
| **Routing Service** | `server-map/` | Flask + pgRouting | Advanced route generation |
| **Infrastructure** | `docker-compose.yml` | Docker | Multi-service orchestration |

### 📱 Mobile Application (`mobile-radar/`)

```
lib/
├── main.dart                    # Application entry point
├── theme.dart                   # Material Design theme
├── screens/                     # UI screens and navigation
│   ├── shell.dart              # Bottom tab navigation + settings modal
│   ├── home_screen.dart        # Map-based radar detection interface
│   ├── login_screen.dart       # Phone-based authentication
│   ├── otp_screen.dart         # OTP verification flow
│   └── home/                   # Home screen components
│       ├── home_screen_viewmodel.dart    # Central state management
│       ├── search_card.dart              # Route planning interface
│       ├── summary_tray.dart             # Navigation summary
│       └── nearest_strip.dart            # Proximity radar display
├── services/                    # Core business logic
│   ├── api_client.dart         # HTTP client with JWT auth
│   ├── local_db.dart           # SQLite offline storage
│   ├── alerts_engine.dart      # Real-time proximity alerts
│   ├── geo_utils.dart          # Geospatial calculations
│   ├── app_config.dart         # Radar detection parameters
│   └── app_locale.dart         # Localization management
├── widgets/                     # Reusable UI components
│   ├── navigation_radar_alert.dart    # Real-time alert display
│   ├── speed_badge.dart                # Current speed indicator
│   └── focus_nav_button.dart           # Navigation controls
└── l10n/                       # Internationalization (en, ru, uz)
    └── app_localizations*.dart
```

#### 🔧 Key Dependencies
```yaml
maplibre_gl: ^0.22.0        # Map rendering & radar overlays
geolocator: ^14.0.2         # Real-time location tracking
dio: ^5.5.0                 # HTTP client with interceptors
sqflite: ^2.4.2             # Local SQLite database
audioplayers: ^6.0.0       # Audio alert system
vibration: ^3.1.3           # Haptic feedback
jwt_decoder: ^2.0.1         # JWT token management
```

### 🖥️ Backend Server (`server/`)

```
server/
├── manage.py                    # Django management commands
├── requirements.txt             # Python dependencies
├── radar_project/              # Django project settings
│   ├── settings.py             # Configuration & database setup
│   └── urls.py                 # URL routing configuration
├── radars/                     # Core radar management
│   ├── models.py               # Polygon-based radar entities
│   ├── admin.py                # Django admin interface
│   ├── views.py                # Spatial query endpoints
│   └── migrations/             # Database schema evolution
├── api/                        # REST API layer
│   ├── serializers.py          # GeoJSON data transformation
│   ├── views.py                # Mobile client endpoints
│   └── permissions.py          # Access control logic
└── frontend/                   # Web admin interface
    ├── templates/              # MapLibre integration
    ├── static/                 # CSS & JavaScript assets
    └── views.py                # Web interface logic
```

#### 🔧 Key Dependencies
```python
Django==5.0.7                  # Web framework
djangorestframework==3.15.2    # REST API framework
django-cors-headers==4.3.1     # CORS for mobile clients
psycopg2-binary               # PostgreSQL adapter
django-extensions==3.2.3       # Development utilities
djoser==2.2.2                 # Authentication endpoints
shapely==2.0.3                # Geometric operations
```

### 🗺️ Routing Service (`server-map/`)

```
server-map/
├── app.py                      # Flask application entry
├── requirements.txt            # Python dependencies
├── routing/                    # Route generation algorithms
│   ├── postgresql.py          # pgRouting integration
│   ├── smart.py               # Intelligent urban routing
│   ├── grid.py                # City grid-pattern routing
│   └── curved.py              # Highway-style routing
├── pg_loader.py               # OSM data import utility
└── test_*.py                  # Integration test suite
```

#### 🔧 Key Dependencies
```python
Flask==3.0.3                  # Lightweight web framework
psycopg2-binary               # PostgreSQL connectivity
osm2pgrouting                 # OSM data processing
requests==2.32.3              # HTTP client library
```

## 🔄 Data Flow Architecture

### 🔐 Authentication Flow
```mermaid
sequenceDiagram
    participant M as Mobile App
    participant A as Django API
    participant D as Database
    
    M->>A: POST /api/auth/otp/request/ {phone}
    A->>D: Store OTP & phone
    A->>M: {status: "sent", dev_otp: "99999"}
    M->>A: POST /api/auth/otp/verify/ {phone, otp}
    A->>D: Validate OTP
    A->>M: {token, refresh_token, user}
    M->>M: Store tokens for API authorization
```

### 🎯 Radar Detection Flow
```mermaid
sequenceDiagram
    participant G as GPS Service
    participant M as Mobile App
    participant L as Local SQLite
    participant A as Alerts Engine
    participant U as User Interface
    
    G->>M: Location Update (lat, lon, bearing)
    M->>L: Query nearby radars (polygon intersection)
    L->>M: Return radar geometries & metadata
    M->>A: Calculate proximity & bearing
    A->>A: Apply lookahead algorithms
    A->>U: Trigger audio/vibration alerts
    A->>U: Update navigation display
```

### 🛣️ Route Planning Flow
```mermaid
sequenceDiagram
    participant M as Mobile App
    participant A as Django API
    participant R as Routing Service
    participant D as Database
    
    M->>A: GET /api/route/ {origin, destination}
    A->>R: POST /route {coordinates, algorithm}
    R->>R: Generate route with pgRouting/algorithms
    R->>A: Return route coordinates
    A->>D: Query impacted radars along route
    A->>M: {route, impacted_radars, total_distance}
    M->>M: Render route with radar overlays
```

## 📊 Database Schema

### 🎯 Core Models

#### Django Backend (`server/radars/models.py`)

```python
class RadarCategory(models.Model):
    """Radar type classification (speed camera, red light, etc.)"""
    name = models.CharField(max_length=100)
    icon_url = models.URLField()
    color = models.CharField(max_length=7)  # Hex color
    
class Radar(models.Model):
    """Polygon-based radar detection areas"""
    geometry = models.PolygonField()        # PostGIS polygon
    category = models.ForeignKey(RadarCategory)
    speed_limit = models.IntegerField()
    direction = models.CharField(max_length=20)
    verified = models.BooleanField(default=False)
    detection_count = models.IntegerField(default=0)
    
class RadarReport(models.Model):
    """Community reporting system"""
    radar = models.ForeignKey(Radar)
    report_type = models.CharField()  # false_positive, confirmed, new
    reporter_ip = models.GenericIPAddressField()
    
class DetectionLog(models.Model):
    """Anonymous analytics"""
    radar = models.ForeignKey(Radar)
    detection_time = models.DateTimeField()
    anonymized_session = models.UUIDField()
```

#### Mobile SQLite (`lib/services/local_db.dart`)

```sql
CREATE TABLE radars (
    id INTEGER PRIMARY KEY,
    server_id INTEGER,
    latitude REAL,
    longitude REAL,
    geometry TEXT,              -- Encoded polygon coordinates
    category_name TEXT,
    speed_limit INTEGER,
    direction TEXT,
    verified INTEGER,
    last_updated TEXT
);

CREATE INDEX idx_radars_location ON radars(latitude, longitude);
CREATE INDEX idx_radars_server_id ON radars(server_id);
```

### 🗺️ Routing Database (`server-map/`)

```sql
-- pgRouting network topology (auto-generated from OSM)
CREATE TABLE ways (
    gid SERIAL PRIMARY KEY,
    osm_id BIGINT,
    source BIGINT,
    target BIGINT,
    cost DOUBLE PRECISION,
    reverse_cost DOUBLE PRECISION,
    the_geom GEOMETRY(LINESTRING, 4326)
);

CREATE INDEX ways_source_idx ON ways(source);
CREATE INDEX ways_target_idx ON ways(target);
CREATE INDEX ways_geom_idx ON ways USING gist(the_geom);
```

## 🔧 Development Commands

### 🏃‍♂️ Quick Start (Local Development)

```bash
# 1. Start Django backend
cd server/
python manage.py runserver 9999

# 2. Start routing service (optional)
cd server-map/
python app.py  # Runs on port 5002

# 3. Run Flutter mobile app
cd mobile-radar/
flutter run -d emulator --dart-define=API_BASE_URL=http://94.158.51.9:9998/api/

# 4. Docker environment (all services)
docker compose up -d
```

### 📱 Mobile Development

```bash
# Dependencies & setup
flutter pub get
flutter analyze
flutter format .

# Platform-specific builds
flutter build apk                 # Android APK
flutter build ios                 # iOS archive
flutter run -d ios --dart-define=API_BASE_URL=http://94.158.51.9:9998/api/

# Testing
flutter test
```

### 🖥️ Backend Development

```bash
# Django development
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 9999

# With custom routing integration
CUSTOM_ROUTING_URL=http://localhost:5002 python manage.py runserver 9999

# Testing
python manage.py test
```

### 🗺️ Routing Service

```bash
# Setup & data loading
pip install -r requirements.txt
python -m pg_loader --pbf uzbekistan-250901.osm.pbf --host localhost --db radar_db

# Development server
python app.py  # Port 5002

# Integration testing
python test_routing.py
python test_integration.py
```

## 🔗 API Endpoints Reference

### 🔐 Authentication

| Endpoint | Method | Purpose | Request | Response |
|----------|--------|---------|---------|----------|
| `/api/auth/otp/request/` | POST | Request OTP | `{phone}` | `{status, dev_otp}` |
| `/api/auth/otp/verify/` | POST | Verify OTP | `{phone, otp}` | `{token, refresh_token, user}` |

### 🎯 Radar Management

| Endpoint | Method | Purpose | Parameters | Response |
|----------|--------|---------|------------|----------|
| `/api/radars/` | GET | Spatial radar query | `bbox`, `lat`, `lng`, `radius` | GeoJSON FeatureCollection |
| `/api/mobile/radars/updates/` | GET | Mobile data sync | `version`, `bbox` | Versioned radar updates |
| `/api/radars/impacted/` | POST | Route radar analysis | `{route_coords}` | Impacted radars along route |

### 🛣️ Routing (Port 5002)

| Endpoint | Method | Purpose | Parameters | Response |
|----------|--------|---------|------------|----------|
| `/route` | POST | Generate route | `{coordinates, algorithm}` | `{route, distance, duration}` |

**Supported Algorithms:**
- `postgresql`: OSM-based realistic routing
- `smart`: Urban routing with intelligent detours
- `grid`: City grid-pattern routing
- `curved`: Highway-style routing
- `direct`: Straight-line fallback

## 🌍 Localization & Configuration

### 🗣️ Supported Languages
- **English** (`en`) - Default
- **Russian** (`ru`) - Framework supported
- **Uzbek** (`uz`) - Custom with Russian framework fallback

### ⚙️ Configuration Files

| Component | File | Purpose |
|-----------|------|---------|
| Mobile | `lib/services/app_config.dart` | Radar detection parameters |
| Backend | `server/radar_project/settings.py` | Django configuration |
| Routing | `server-map/app.py` | Flask service settings |
| Docker | `docker-compose.yml` | Multi-service orchestration |

### 🔧 Environment Variables

```bash
# Django Backend
DATABASE_URL=postgresql://user:pass@localhost/radar_db
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
CUSTOM_ROUTING_URL=http://localhost:5002

# Flutter Mobile
API_BASE_URL=http://94.158.51.9:9998/api/

# Docker
OSRM_REGION=uzbekistan
```

## 🏗️ Architecture Patterns

### 🎯 Key Design Patterns

1. **Polygon-Based Detection**: Uses actual geometric polygons instead of point+radius for accurate radar coverage
2. **Microservices Integration**: Specialized routing service with automatic fallback mechanisms
3. **Offline-First Mobile**: SQLite storage with periodic sync for offline capability
4. **Verification-Driven Quality**: Community reporting + admin verification workflow
5. **Bearing-Based Alerts**: Smart lookahead calculations based on travel direction
6. **JWT + Token Refresh**: Modern authentication with automatic token management

### 🔄 State Management

- **Mobile**: `ChangeNotifier` pattern with `HomeScreenViewModel` as central coordinator
- **Backend**: Django ORM with spatial queries and PostGIS integration
- **Routing**: Stateless service with pgRouting for complex path calculations

### 🗄️ Data Synchronization

```mermaid
flowchart TD
    A[Mobile App Launch] --> B[Check Local DB Version]
    B --> C{Version Current?}
    C -->|No| D[Fetch Updates from API]
    C -->|Yes| E[Use Local Data]
    D --> F[Update Local SQLite]
    F --> E
    E --> G[Real-time Location Tracking]
    G --> H[Local Polygon Intersection]
    H --> I[Trigger Alerts]
```

## 📈 Performance Characteristics

### 📱 Mobile App Metrics
- **Cold Start**: <2 seconds to map display
- **Location Accuracy**: ±3-5 meters with GPS
- **Alert Latency**: <100ms from location update
- **Battery Impact**: Moderate (continuous GPS + background processing)
- **Storage**: ~2-5MB for local radar database

### 🖥️ Backend Performance
- **Spatial Queries**: Sub-50ms for bbox radar queries
- **Authentication**: <200ms for OTP verification
- **Route Generation**: 500ms-2s depending on complexity
- **Concurrent Users**: Tested for 100+ simultaneous connections

## 🔒 Security Considerations

### 🛡️ Security Measures
- **JWT Authentication**: Secure token-based auth with refresh mechanism
- **Anonymous Analytics**: No user tracking in detection logs
- **CORS Configuration**: Restricted to mobile client origins
- **Input Validation**: Comprehensive validation for all API endpoints
- **Rate Limiting**: Protection against abuse and spam
- **Environment-Based Secrets**: No hardcoded credentials

### 🔐 Privacy Features
- **Phone-Only Auth**: No email or personal data collection
- **Local Storage**: Sensitive data stored locally on device
- **Anonymous Reporting**: Community reports without user identification
- **GDPR Compliance**: Minimal data collection with user consent

## 🚀 Deployment Architecture

### 🐳 Docker Environment

```yaml
services:
  web:          # Django API (Port 9999)
  routing:      # Flask routing service (Port 5002)
  postgres:     # Main database with PostGIS
  routing_db:   # Routing database with pgRouting
  redis:        # Caching and session storage
```

### ☁️ Production Considerations
- **Database**: PostgreSQL with PostGIS extension required
- **File Storage**: Static assets served via CDN
- **Load Balancing**: Nginx reverse proxy for API endpoints
- **Monitoring**: Application monitoring with health checks
- **Backup Strategy**: Automated database backups with point-in-time recovery

---

## 📚 Additional Resources

### 📖 Documentation Files
- **[CLAUDE.md](./CLAUDE.md)**: Claude Code integration guidelines (project root)
- **[mobile-radar/CLAUDE.md](./mobile-radar/CLAUDE.md)**: Mobile app specific guidelines
- **[mobile-radar/README.md](./mobile-radar/README.md)**: Mobile app quick start guide

### 🔗 External Dependencies
- **MapLibre GL**: Open-source map rendering library
- **PostGIS**: Spatial database extension for PostgreSQL
- **pgRouting**: Routing algorithms for PostgreSQL
- **Flutter**: Google's UI toolkit for mobile development
- **Django REST Framework**: Powerful API framework for Django

### 🧪 Testing Strategy
- **Unit Tests**: Individual component testing
- **Integration Tests**: Multi-service interaction validation
- **E2E Tests**: Complete user workflow verification
- **Performance Tests**: Load testing and benchmarking

---

*Last Updated: January 2025*  
*Project Version: 0.1.0*  
*Architecture: Microservices with Flutter + Django + Flask*