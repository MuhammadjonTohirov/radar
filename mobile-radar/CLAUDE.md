# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mobile Radar is a Flutter application that provides real-time radar detection and navigation features. The app connects to a Django backend API for radar data and user authentication via phone + OTP.

## Development Commands

### Flutter Setup
- **Install dependencies**: `flutter pub get`
- **Run on Android emulator**: `flutter run -d emulator --dart-define=API_BASE_URL=http://192.168.1.124:9999/api/`
- **Run on iOS simulator**: `flutter run -d ios --dart-define=API_BASE_URL=http://192.168.1.124:9999/api/`
- **Build APK**: `flutter build apk`
- **Build iOS**: `flutter build ios`

### Code Analysis
- **Run linter**: `flutter analyze`
- **Fix formatting**: `flutter format .`

### Testing
- **Run tests**: `flutter test`

### Environment Configuration
- **API base URL**: Configured via `--dart-define API_BASE_URL` (defaults to `http://10.0.2.2:8000/api/` for Android emulator)
- **Backend requirement**: Django backend must be running on the specified API URL

## Architecture Overview

### Core Structure
- **Main App**: Entry point with localization and theme setup (`lib/main.dart`)
- **Shell Navigation**: Bottom tab navigation with settings modal (`lib/screens/shell.dart`)
- **Home Screen**: Map-based radar detection with navigation features (`lib/screens/home_screen.dart`)
- **Authentication**: Phone + OTP flow with token management (`lib/screens/login_screen.dart`, `lib/screens/otp_screen.dart`)

### Key Services
- **ApiClient** (`lib/services/api_client.dart`): HTTP client with JWT/Token auth, automatic token refresh, and API endpoint management
- **LocalDb** (`lib/services/local_db.dart`): SQLite database for offline radar data storage
- **AppConfig** (`lib/services/app_config.dart`): Configuration management for radar detection parameters (distances, thresholds, lookahead calculations)
- **AlertsEngine** (`lib/services/alerts_engine.dart`): Real-time radar proximity alerts with audio/vibration
- **GeoUtils** (`lib/services/geo_utils.dart`): Geospatial calculations (haversine distance, bearings, sector parsing)

### Map & Navigation System
- **MapLibre Integration**: Uses `maplibre_gl` for map rendering with custom radar overlays
- **Geolocator**: Real-time location tracking with different accuracy modes for navigation vs overview
- **Navigation Modes**: 
  - Overview mode: Static map with radar locations
  - Navigation mode: Real-time following with 3D camera, bearing-based lookahead, and proximity alerts
- **Radar Rendering**: Custom icons, detection sectors (polygons), and route impact visualization

### State Management
- **ViewModels**: Uses `ChangeNotifier` pattern for screen state management
- **HomeScreenViewModel** (`lib/screens/home/home_screen_viewmodel.dart`): Central state for map, location, radar data, and navigation

### Data Flow
1. **Authentication**: Phone → OTP → JWT/Token storage → API authorization
2. **Radar Data**: Backend sync → Local SQLite → Map rendering with proximity filtering
3. **Navigation**: GPS stream → Camera updates → Radar detection → Audio/vibration alerts
4. **Route Planning**: Coordinates → Backend routing → Impacted radars → Visual overlay

### Localization
- **i18n Support**: English, Russian, Uzbek with fallback handling
- **Generated**: Uses `flutter_localizations` with auto-generated delegates
- **Files**: `lib/l10n/app_localizations_*.dart` (do not edit manually)

### Configuration Details
- **Radar Detection Distances**: Configurable via `AppConfig` (alert thresholds, lookahead calculations, navigation smoothing)
- **API Endpoints**: 
  - `/auth/otp/request/` - Request OTP code
  - `/auth/otp/verify/` - Verify OTP and get tokens
  - `/mobile/radars/updates/` - Fetch radar updates with versioning
  - `/radars/impacted/` - Route planning with radar impact analysis
- **Location Accuracy**: Uses `LocationSettings` instead of deprecated `desiredAccuracy`

### UI Theme
- **Color Scheme**: Matches Django template palette (primary #417690, secondary #6c757d, danger #dc3545)
- **Material Design**: Uses Material 3 components with custom brand styling
- **Responsive**: Handles both portrait/landscape with safe area considerations

### Backend Integration
- **Authentication**: Supports both legacy Token auth and modern JWT with refresh tokens
- **Offline Capability**: SQLite storage enables offline radar viewing with periodic sync
- **Version Control**: Radar data uses version strings for incremental updates