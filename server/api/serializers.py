from rest_framework import serializers
from django.conf import settings
from radars.models import Radar, RadarReport, DetectionLog, RadarCategory

# Import GIS serializer only if available
if getattr(settings, 'HAS_GIS', False):
    try:
        from rest_framework_gis.serializers import GeoFeatureModelSerializer
        BaseRadarSerializer = GeoFeatureModelSerializer
        HAS_GIS_SERIALIZER = True
    except ImportError:
        BaseRadarSerializer = serializers.ModelSerializer
        HAS_GIS_SERIALIZER = False
else:
    BaseRadarSerializer = serializers.ModelSerializer
    HAS_GIS_SERIALIZER = False


class RadarSerializer(BaseRadarSerializer):
    """
    Radar serializer with optional GeoJSON support
    """
    coordinates_display = serializers.ReadOnlyField()
    category_id = serializers.PrimaryKeyRelatedField(source='category', read_only=True)
    category_code = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    icon_color = serializers.SerializerMethodField()
    category_groups = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True)
    
    class Meta:
        model = Radar
        fields = [
            'id', 'speed_limit', 'notes', 
            'verified', 'active', 'alert_count', 'last_detected',
            'created_at', 'updated_at', 'verified_at',
            'coordinates_display', 'created_by_username', 'verified_by_username',
            'category_id', 'category_code', 'category_name', 'category_groups', 'icon_url', 'icon_color'
        ]
        read_only_fields = [
            'alert_count', 'last_detected', 'created_at', 'updated_at', 
            'verified_at', 'coordinates_display', 'created_by_username',
            'verified_by_username', 'category_id', 'category_code', 'category_name', 'category_groups', 'icon_url', 'icon_color'
        ]
        
        # Add geo_field only for GIS serializer
        if HAS_GIS_SERIALIZER:
            geo_field = 'center'
    
    def to_representation(self, instance):
        """Add sector polygon to the representation"""
        representation = super().to_representation(instance)
        
        # Add sector polygon as additional property
        if HAS_GIS_SERIALIZER and hasattr(instance, 'sector') and instance.sector:
            representation['properties']['sector'] = {
                'type': 'Polygon',
                'coordinates': list(instance.sector.coords)
            }
        elif not HAS_GIS_SERIALIZER and hasattr(instance, 'sector_json') and instance.sector_json:
            representation['sector'] = instance.sector_json
            representation['center'] = {
                'latitude': getattr(instance, 'center_lat', None),
                'longitude': getattr(instance, 'center_lon', None)
            }
        
        return representation

    def get_category_code(self, obj):
        try:
            return obj.category.code if obj.category else None
        except Exception:
            return None

    def get_category_name(self, obj):
        try:
            return obj.category.name if obj.category else None
        except Exception:
            return None

    def get_icon_url(self, obj):
        return getattr(obj, 'icon_url', None)

    def get_icon_color(self, obj):
        return getattr(obj, 'resolved_icon_color', None)

    def get_category_groups(self, obj):
        try:
            return list(obj.category.groups or []) if obj.category else []
        except Exception:
            return []


class RadarListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing radars without geometry
    """
    coordinates_display = serializers.ReadOnlyField()
    category_code = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    icon_color = serializers.SerializerMethodField()
    category_groups = serializers.SerializerMethodField()
    
    class Meta:
        model = Radar
        fields = [
            'id', 'speed_limit', 'verified', 
            'active', 'alert_count', 'coordinates_display', 'created_at',
            'category_code', 'category_groups', 'icon_url', 'icon_color'
        ]

    def get_category_code(self, obj):
        try:
            return obj.category.code if obj.category else None
        except Exception:
            return None

    def get_icon_url(self, obj):
        return getattr(obj, 'icon_url', None)

    def get_icon_color(self, obj):
        return getattr(obj, 'resolved_icon_color', None)

    def get_category_groups(self, obj):
        try:
            return list(obj.category.groups or []) if obj.category else []
        except Exception:
            return []


class RadarDeltaSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for mobile delta sync within a radius.
    Always emits a stable shape regardless of GIS availability:
      - center: { latitude, longitude }
      - sector: GeoJSON Polygon (if available), else null
    """
    center = serializers.SerializerMethodField()
    sector = serializers.SerializerMethodField()
    category_code = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    icon_color = serializers.SerializerMethodField()
    category_groups = serializers.SerializerMethodField()

    class Meta:
        model = Radar
        fields = [
            'id', 'speed_limit', 'verified', 'active',
            'created_at', 'updated_at', 'center', 'sector',
            'category_code', 'category_groups', 'icon_url', 'icon_color'
        ]

    def get_center(self, obj):
        if getattr(settings, 'HAS_GIS', False) and hasattr(obj, 'center') and obj.center:
            try:
                return {
                    'latitude': obj.center.y,
                    'longitude': obj.center.x,
                }
            except Exception:
                return None
        # Non-GIS
        lat = getattr(obj, 'center_lat', None)
        lon = getattr(obj, 'center_lon', None)
        if lat is None or lon is None:
            return None
        return {'latitude': lat, 'longitude': lon}

    def get_sector(self, obj):
        if getattr(settings, 'HAS_GIS', False) and hasattr(obj, 'sector') and obj.sector:
            try:
                # Emit GeoJSON polygon
                return {
                    'type': 'Polygon',
                    'coordinates': list(obj.sector.coords)
                }
            except Exception:
                return None
        # Non-GIS
        return getattr(obj, 'sector_json', None)

    def get_category_code(self, obj):
        try:
            return obj.category.code if obj.category else None
        except Exception:
            return None

    def get_icon_url(self, obj):
        return getattr(obj, 'icon_url', None)

    def get_icon_color(self, obj):
        return getattr(obj, 'resolved_icon_color', None)

    def get_category_groups(self, obj):
        try:
            return list(obj.category.groups or []) if obj.category else []
        except Exception:
            return []


class RadarReportSerializer(serializers.ModelSerializer):
    """
    Serializer for radar reports
    """
    radar_info = RadarListSerializer(source='radar', read_only=True)
    
    class Meta:
        model = RadarReport
        fields = [
            'id', 'radar', 'radar_info', 'reporter_device', 'location',
            'report_type', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def validate_reporter_device(self, value):
        """Ensure reporter device ID is provided"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Valid device ID is required")
        return value.strip()


class DetectionLogSerializer(serializers.ModelSerializer):
    """
    Serializer for detection logs (analytics)
    """
    radar_info = RadarListSerializer(source='radar', read_only=True)
    
    class Meta:
        model = DetectionLog
        fields = [
            'id', 'radar', 'radar_info', 'device_id', 'detected_at',
            'speed', 'location'
        ]
        read_only_fields = ['detected_at']


class RadarCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating radars with polygon validation
    """
    
    class Meta:
        model = Radar
        fields = [
            'category', 'sector', 'speed_limit', 'notes'
        ]
    
    def validate_sector(self, value):
        """Validate polygon geometry"""
        if not value:
            raise serializers.ValidationError("Sector polygon is required")
        
        if not value.valid:
            raise serializers.ValidationError("Invalid polygon geometry")
        
        # Check minimum area (prevent tiny polygons)
        if value.area < 0.000001:  # Very small area check
            raise serializers.ValidationError("Polygon area is too small")
        
        return value
    
    def validate_speed_limit(self, value):
        """Validate speed limit range"""
        if value is not None:
            if value < 10 or value > 200:
                raise serializers.ValidationError(
                    "Speed limit must be between 10 and 200 km/h"
                )
        return value


class RadarStatsSerializer(serializers.Serializer):
    """
    Serializer for radar statistics
    """
    total_radars = serializers.IntegerField()
    verified_radars = serializers.IntegerField()
    active_radars = serializers.IntegerField()
    total_detections = serializers.IntegerField()
    radars_by_type = serializers.DictField()
    recent_detections = serializers.IntegerField()
    top_radars = RadarListSerializer(many=True)
