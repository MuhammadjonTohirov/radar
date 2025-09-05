from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timezone as dt_timezone
from django.conf import settings
from radars.models import Radar, RadarReport, DetectionLog
from .serializers import RadarSerializer, RadarReportSerializer, DetectionLogSerializer, RadarDeltaSerializer
from .filters import RadarFilter
from .services.routing import RoutingService, ExternalOSRMService
from django.contrib.auth.models import User
from django.db.models import Max
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken

# Import GIS modules only if available
if getattr(settings, 'HAS_GIS', False):
    try:
        from django.contrib.gis.geos import Polygon, Point
        from django.contrib.gis.measure import Distance
        HAS_GIS_SUPPORT = True
    except ImportError:
        HAS_GIS_SUPPORT = False
else:
    HAS_GIS_SUPPORT = False


class RadarViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing radar data with spatial filtering
    """
    queryset = Radar.objects.filter(active=True)
    serializer_class = RadarSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = RadarFilter
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by bounding box if provided
        bbox = self.request.query_params.get('bbox')
        if bbox and HAS_GIS_SUPPORT:
            try:
                min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
                bbox_polygon = Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))
                queryset = queryset.filter(center__within=bbox_polygon)
            except (ValueError, TypeError):
                # Invalid bbox format, ignore filter
                pass
        elif bbox and not HAS_GIS_SUPPORT:
            # Simple coordinate-based filtering for non-GIS mode
            try:
                min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
                queryset = queryset.filter(
                    center_lat__gte=min_lat,
                    center_lat__lte=max_lat,
                    center_lon__gte=min_lon,
                    center_lon__lte=max_lon
                )
            except (ValueError, TypeError):
                pass
        
        # Filter by proximity to a point
        near = self.request.query_params.get('near')
        distance = self.request.query_params.get('distance', 1000)  # meters
        if near and HAS_GIS_SUPPORT:
            try:
                lon, lat = map(float, near.split(','))
                point = Point(lon, lat, srid=4326)
                queryset = queryset.filter(
                    center__distance_lte=(point, Distance(m=int(distance)))
                )
            except (ValueError, TypeError):
                pass
        # Note: Proximity filtering without GIS requires more complex calculation
        
        # Only return verified radars for non-authenticated users
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(verified=True)
        
        return queryset.select_related('created_by', 'verified_by', 'category')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def detect(self, request, pk=None):
        """Record a radar detection event"""
        radar = self.get_object()
        device_id = request.data.get('device_id')
        speed = request.data.get('speed')
        location_data = request.data.get('location')
        
        if not device_id:
            return Response(
                {'error': 'device_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse location and create detection log
        if HAS_GIS_SUPPORT and location_data:
            try:
                location = Point(
                    location_data['longitude'], 
                    location_data['latitude'], 
                    srid=4326
                )
                DetectionLog.objects.create(
                    radar=radar,
                    device_id=device_id,
                    speed=speed,
                    location=location
                )
            except (KeyError, TypeError, ValueError):
                DetectionLog.objects.create(
                    radar=radar,
                    device_id=device_id,
                    speed=speed
                )
        elif not HAS_GIS_SUPPORT and location_data:
            try:
                DetectionLog.objects.create(
                    radar=radar,
                    device_id=device_id,
                    speed=speed,
                    location_lat=location_data['latitude'],
                    location_lon=location_data['longitude']
                )
            except (KeyError, TypeError, ValueError):
                DetectionLog.objects.create(
                    radar=radar,
                    device_id=device_id,
                    speed=speed
                )
        else:
            DetectionLog.objects.create(
                radar=radar,
                device_id=device_id,
                speed=speed
            )
        
        # Update radar analytics
        radar.increment_alert_count()
        
        return Response({'status': 'detection recorded'})
    
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Submit a report about this radar"""
        radar = self.get_object()
        serializer = RadarReportSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(radar=radar)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RadarReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing radar reports
    """
    queryset = RadarReport.objects.all()
    serializer_class = RadarReportSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['report_type', 'radar']
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return RadarReport.objects.none()  # Regular users can't list reports


class DetectionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for detection analytics (admin only)
    """
    queryset = DetectionLog.objects.all()
    serializer_class = DetectionLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['radar', 'detected_at']
    
    def get_queryset(self):
        if not self.request.user.is_staff:
            return DetectionLog.objects.none()
        
        queryset = super().get_queryset()
        
        # Filter by date range
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        
        if from_date:
            try:
                from datetime import datetime
                from_dt = datetime.fromisoformat(from_date)
                queryset = queryset.filter(detected_at__gte=from_dt)
            except ValueError:
                pass
        
        if to_date:
            try:
                from datetime import datetime
                to_dt = datetime.fromisoformat(to_date)
                queryset = queryset.filter(detected_at__lte=to_dt)
            except ValueError:
                pass
        
        return queryset.select_related('radar')


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def route_view(request):
    """
    Return a GeoJSON LineString between from and to coordinates.

    Query params:
      - from: "lon,lat"
      - to:   "lon,lat"

    Note: This placeholder returns a straight line. For production
    routing, integrate with OSRM/Valhalla/GraphHopper and return
    an actual road-following route.
    """
    coords_param = request.query_params.get('coords')
    profile = request.query_params.get('profile') or 'driving'

    coordinates = []
    if coords_param:
        # Expect "lon,lat;lon,lat;..."
        try:
            parts = [p.strip() for p in coords_param.split(';') if p.strip()]
            for part in parts:
                lon_str, lat_str = [v.strip() for v in part.split(',')]
                coordinates.append((float(lon_str), float(lat_str)))
        except Exception:
            return Response({'detail': 'Invalid coords format. Use "lon,lat;lon,lat;..."'}, status=400)
    else:
        src = request.query_params.get('from')
        dst = request.query_params.get('to')
        if not src or not dst:
            return Response({'detail': 'Provide either coords="lon,lat;..." or from/to as "lon,lat"'}, status=400)
        try:
            flon, flat = [float(x) for x in src.split(',')]
            tlon, tlat = [float(x) for x in dst.split(',')]
            coordinates = [(flon, flat), (tlon, tlat)]
        except Exception:
            return Response({'detail': 'Invalid coordinate format. Use "lon,lat".'}, status=400)

    # Try the remote OSRM first (steps=true, overview=false, geojson)
    try:
        base = getattr(settings, 'REMOTE_OSRM_BASE_URL', '')
        if base:
            feature = ExternalOSRMService.get_route(
                coordinates,
                profile=profile,
                base_url=base,
                steps=True,
                overview='false',
                geometries='geojson'
            )
            return Response(feature)
    except Exception:
        pass

    feature = RoutingService.get_route_coords(coordinates, profile=profile)
    return Response(feature)


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def radars_impacted_view(request):
    """
    Return route geometry and radars impacted within a buffer around the route.

    Query params:
      - from: "lon,lat" OR coords: "lon,lat;lon,lat;..."
      - to:   "lon,lat" (when not using coords)
      - buffer: impact tolerance in meters (default 5). Route is buffered
        by this amount (in meters) in a local planar approximation and
        intersected with each radar polygon.
      - profile: routing profile (default: driving)
    """
    coords_param = request.query_params.get('coords')
    profile = request.query_params.get('profile') or 'driving'
    buffer_m = request.query_params.get('buffer') or '5'
    try:
        buffer_m = float(buffer_m)
        if buffer_m <= 0:
            buffer_m = 50.0
    except Exception:
        buffer_m = 50.0

    coordinates = []
    if coords_param:
        try:
            parts = [p.strip() for p in coords_param.split(';') if p.strip()]
            for part in parts:
                lon_str, lat_str = [v.strip() for v in part.split(',')]
                coordinates.append((float(lon_str), float(lat_str)))
        except Exception:
            return Response({'detail': 'Invalid coords format. Use "lon,lat;lon,lat;..."'}, status=400)
    else:
        src = request.query_params.get('from')
        dst = request.query_params.get('to')
        if not src or not dst:
            return Response({'detail': 'Provide either coords="lon,lat;..." or from/to as "lon,lat"'}, status=400)
        try:
            flon, flat = [float(x) for x in src.split(',')]
            tlon, tlat = [float(x) for x in dst.split(',')]
            coordinates = [(flon, flat), (tlon, tlat)]
        except Exception:
            return Response({'detail': 'Invalid coordinate format. Use "lon,lat".'}, status=400)

    # Build route feature
    route_feature = None
    try:
        base = getattr(settings, 'REMOTE_OSRM_BASE_URL', '')
        if base:
            route_feature = ExternalOSRMService.get_route(
                coordinates,
                profile=profile,
                base_url=base,
                steps=True,
                overview='false',
                geometries='geojson'
            )
    except Exception:
        route_feature = None
    if route_feature is None:
        route_feature = RoutingService.get_route_coords(coordinates, profile=profile)

    radars = _compute_impacted_radars(request, route_feature, buffer_m)
    return Response({
        'route': route_feature,
        'buffer_m': buffer_m,
        'impacted_count': len(radars),
        'radars': radars,
    })


def _compute_impacted_radars(request, route_feature, buffer_m: float) -> list[dict]:
    """Return impacted radars if buffered route (meters) intersects radar polygon.

    Implementation details:
    - Projects lon/lat to a local equirectangular XY (meters) using mean latitude
      to approximate meters; buffers the route by `buffer_m` and tests polygon
      intersection in the same XY space.
    - Requires radar.sector_json (Polygon) for accurate direction-side filtering.
    """
    import math
    import json as _json
    try:
        from shapely.geometry import LineString, Polygon
    except Exception:
        return []

    coords = (route_feature or {}).get('geometry', {}).get('coordinates') or []
    if len(coords) < 2:
        return []

    # Compute projection anchor
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    mean_lat = (min_lat + max_lat) / 2.0
    R = 6371000.0
    cos0 = math.cos(math.radians(mean_lat)) or 1e-6

    def to_xy(lon: float, lat: float) -> tuple[float, float]:
        x = R * math.radians(lon) * cos0
        y = R * math.radians(lat)
        return (x, y)

    # Build route line in XY and buffer by buffer_m meters
    try:
        route_line_xy = LineString([to_xy(lon, lat) for lon, lat in coords])
        route_buf = route_line_xy.buffer(float(buffer_m))
    except Exception:
        return []

    # Coarse bbox prefilter in degrees (use ~meters -> degrees conversion)
    deg_lat = buffer_m / 111000.0
    deg_lon = buffer_m / (111000.0 * cos0)

    qs = Radar.objects.filter(active=True)
    if not request.user.is_authenticated:
        qs = qs.filter(verified=True)
    qs = qs.filter(
        center_lat__gte=min_lat - deg_lat,
        center_lat__lte=max_lat + deg_lat,
        center_lon__gte=min_lon - deg_lon,
        center_lon__lte=max_lon + deg_lon,
    )

    impacted: list[dict] = []
    for r in qs:
        sector = getattr(r, 'sector_json', None)
        if not sector:
            continue
        try:
            geom = _json.loads(sector) if isinstance(sector, str) else sector
            if not (isinstance(geom, dict) and geom.get('type') == 'Polygon'):
                continue
            rings = geom.get('coordinates') or []
            if not rings:
                continue
            shell = rings[0]
            poly_xy = Polygon([to_xy(lon, lat) for lon, lat in shell])
            if not poly_xy.is_valid or poly_xy.is_empty:
                continue
        except Exception:
            continue

        try:
            if route_buf.intersects(poly_xy):
                impacted.append({
                    'id': r.id,
                    'category_code': getattr(r.category, 'code', None),
                    'type': getattr(r.category, 'code', None),
                    'speed_limit': r.speed_limit,
                    'verified': r.verified,
                    'active': r.active,
                    'icon_url': getattr(r, 'icon_url', None),
                    'icon_color': getattr(r, 'resolved_icon_color', None),
                    'center': {
                        'latitude': getattr(r, 'center_lat', None),
                        'longitude': getattr(r, 'center_lon', None),
                    }
                })
        except Exception:
            continue

    return impacted


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def radars_nearby_view(request):
    """
    Return top-N nearest radars to a given point.

    Query params:
      - point: "lon,lat" (required)
      - limit: integer (default 10)
      - max_distance: meters (optional) — coarse filter and final threshold
    """
    point = request.query_params.get('point')
    limit = request.query_params.get('limit', '10')
    max_distance = request.query_params.get('max_distance')
    try:
        limit = max(1, min(100, int(limit)))
    except Exception:
        limit = 10
    if max_distance is not None:
        try:
            max_distance = float(max_distance)
            if max_distance <= 0:
                max_distance = None
        except Exception:
            max_distance = None
    if not point:
        return Response({'detail': 'point=lon,lat is required'}, status=400)
    try:
        plon, plat = [float(x) for x in point.split(',')]
    except Exception:
        return Response({'detail': 'Invalid point format. Use "lon,lat"'}, status=400)

    # Coarse bbox prefilter
    import math
    R = 6371000.0
    mean_lat = plat
    cos0 = math.cos(math.radians(mean_lat)) or 1e-6
    # default search window ~5km if no max_distance
    md = max_distance or 5000.0
    deg_lat = md / 111000.0
    deg_lon = md / (111000.0 * cos0)

    qs = Radar.objects.filter(active=True)
    if not request.user.is_authenticated:
        qs = qs.filter(verified=True)
    qs = qs.filter(
        center_lat__gte=plat - deg_lat,
        center_lat__lte=plat + deg_lat,
        center_lon__gte=plon - deg_lon,
        center_lon__lte=plon + deg_lon,
    )

    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    items = []
    for r in qs.select_related('created_by', 'verified_by', 'category'):
        lat = getattr(r, 'center_lat', None)
        lon = getattr(r, 'center_lon', None)
        if lat is None or lon is None:
            continue
        d = haversine(plon, plat, lon, lat)
        if max_distance is None or d <= max_distance:
            items.append({
                'id': r.id,
                'category_code': getattr(r.category, 'code', None),
                'type': getattr(r.category, 'code', None),
                'speed_limit': r.speed_limit,
                'verified': r.verified,
                'active': r.active,
                'icon_url': getattr(r, 'icon_url', None),
                'icon_color': getattr(r, 'resolved_icon_color', None),
                'center': {'latitude': lat, 'longitude': lon},
                'distance_m': round(d, 2),
            })

    items.sort(key=lambda x: x['distance_m'])
    return Response({'results': items[:limit]})


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def radars_updates_view(request):
    """
    Versioned radius query for mobile clients.

    Query params:
      - lat: latitude (required)
      - lon: longitude (required)
      - radius_km: search radius in kilometers (default 10, max 2000)
      - version: ISO8601 timestamp string or '0' (0 => full data)

    Response JSON:
      { version: ISO8601, count: N, radars: [ ... ] }
    """
    q = request.query_params
    lat_str = q.get('lat')
    lon_str = q.get('lon')
    has_point = bool(lat_str and lon_str)
    lat = lon = None
    radius_km = None
    if has_point:
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except Exception:
            return Response({'detail': 'Invalid lat/lon'}, status=400)
        radius_km_str = q.get('radius_km') or q.get('radius') or '10'
        try:
            radius_km = float(radius_km_str)
            if radius_km <= 0:
                radius_km = 10.0
            radius_km = min(radius_km, 2000.0)  # safety cap
        except Exception:
            radius_km = 10.0

    version_param = q.get('version') or '0'

    def parse_version(v: str):
        if not v or str(v).strip() in ('0', 'null', 'None'):
            return None
        s = str(v).strip()
        try:
            from datetime import datetime
            if s.endswith('Z'):
                s = s[:-1] + '+00:00'
            return datetime.fromisoformat(s)
        except Exception:
            return None

    since_dt = parse_version(version_param)

    # Base queryset (active + visibility)
    base_qs = Radar.objects.filter(active=True)
    if not request.user.is_authenticated:
        base_qs = base_qs.filter(verified=True)

    # If no coordinates provided, operate on the full dataset (active + visibility)
    if not has_point:
        full_qs = base_qs
        latest_dt = full_qs.aggregate(m=Max('updated_at'))['m']
        if since_dt is not None:
            # Return only items updated since the provided version
            full_qs = full_qs.filter(updated_at__gt=since_dt)
        data = RadarDeltaSerializer(full_qs.order_by('id'), many=True).data
        latest_version_str = version_param if latest_dt is None else latest_dt.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z')
        return Response({'version': latest_version_str, 'count': len(data), 'radars': data})

    # GIS-enhanced path with radius
    if HAS_GIS_SUPPORT:
        try:
            point = Point(lon, lat, srid=4326)
            zone_qs = base_qs.filter(center__distance_lte=(point, Distance(km=radius_km)))
        except Exception:
            zone_qs = base_qs.none()

        latest_dt = zone_qs.aggregate(m=Max('updated_at'))['m']
        changes_qs = zone_qs
        if since_dt is not None:
            changes_qs = changes_qs.filter(updated_at__gt=since_dt)
        data = RadarDeltaSerializer(changes_qs.order_by('id'), many=True).data

        # Prepare version string
        if latest_dt is None:
            latest_version_str = version_param if version_param else '0'
        else:
            latest_version_str = latest_dt.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z')

        return Response({
            'version': latest_version_str,
            'count': len(data),
            'radars': data,
        })

    # Non-GIS path: coarse bbox + haversine filter
    import math
    R = 6371000.0
    cos0 = math.cos(math.radians(lat)) or 1e-6
    deg_lat = (radius_km * 1000.0) / 111000.0
    deg_lon = (radius_km * 1000.0) / (111000.0 * cos0)

    candidates = base_qs.filter(
        center_lat__gte=lat - deg_lat,
        center_lat__lte=lat + deg_lat,
        center_lon__gte=lon - deg_lon,
        center_lon__lte=lon + deg_lon,
    )

    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    zone = []
    for r in candidates.select_related('created_by', 'verified_by'):
        rlat = getattr(r, 'center_lat', None)
        rlon = getattr(r, 'center_lon', None)
        if rlat is None or rlon is None:
            continue
        d = haversine(lon, lat, rlon, rlat)
        if d <= radius_km * 1000.0:
            zone.append(r)

    # Compute latest version in the zone
    latest_dt = None
    if zone:
        latest_dt = max((z.updated_at for z in zone if getattr(z, 'updated_at', None) is not None), default=None)

    # Apply version filter for changes
    if since_dt is not None:
        zone = [z for z in zone if (getattr(z, 'updated_at', None) and z.updated_at > since_dt)]

    data = RadarDeltaSerializer(zone, many=True).data
    if latest_dt is None:
        latest_version_str = version_param if version_param else '0'
    else:
        latest_version_str = latest_dt.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z')

    return Response({
        'version': latest_version_str,
        'count': len(data),
        'radars': data,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_request_view(request):
    """
    Development OTP request endpoint.

    Body JSON: { "phone": "+998901234567" }
    Response: { "status": "otp_sent", "dev_otp": "99999" } (dev only)
    """
    phone = str(request.data.get('phone', '')).strip()
    if not phone or len(phone) < 5:
        return Response({'detail': 'Valid phone is required'}, status=400)
    # In development we do not send SMS; return static OTP for convenience
    dev_otp = '99999'
    return Response({'status': 'otp_sent', 'dev_otp': dev_otp})


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_verify_view(request):
    """
    Verify phone + OTP and return an auth token.

    Body JSON: { "phone": "+998901234567", "otp": "99999" }
    """
    phone = str(request.data.get('phone', '')).strip()
    otp = str(request.data.get('otp', '')).strip()
    if not phone or len(phone) < 5:
        return Response({'detail': 'Valid phone is required'}, status=400)
    if otp != '99999':
        return Response({'detail': 'Invalid OTP (use 99999 in development)'}, status=400)

    # Use phone as username; create user if not exists
    username = phone
    user, created = User.objects.get_or_create(username=username, defaults={'is_active': True})
    if created:
        user.set_unusable_password()
        user.save()
    # DRF token (backward compatibility)
    token, _ = Token.objects.get_or_create(user=user)

    # Issue JWT access + refresh
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    # Compute expiries based on settings lifetimes in UTC
    now = dt_timezone.now()
    access_expires = now + settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME')
    refresh_expires = now + settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME')

    def iso(dt):
        try:
            return dt.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z')
        except Exception:
            return dt.isoformat()

    return Response({
        'token': token.key,  # legacy
        'access': str(access),
        'refresh': str(refresh),
        'access_expires_at': iso(access_expires),
        'refresh_expires_at': iso(refresh_expires),
        'user': {
            'id': user.id,
            'username': user.username,
            'is_staff': user.is_staff,
        }
    })
