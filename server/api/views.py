from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.conf import settings
from radars.models import Radar, RadarReport, DetectionLog
from .serializers import RadarSerializer, RadarReportSerializer, DetectionLogSerializer
from .filters import RadarFilter

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
        
        return queryset.select_related('created_by', 'verified_by')
    
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
