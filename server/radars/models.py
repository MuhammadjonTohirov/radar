from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

# Use GIS models if available, otherwise use regular models
if getattr(settings, 'HAS_GIS', False):
    from django.contrib.gis.db import models
else:
    from django.db import models


class Radar(models.Model):
    TYPE_CHOICES = [
        ("fixed_speed_camera", "Fixed Speed Camera"),
        ("mobile_tripod", "Mobile Speed Camera"),
        ("red_light", "Red Light Camera"),
        ("average_speed", "Average Speed Camera"),
        ("section_control", "Section Control"),
        ("bus_lane", "Bus Lane Camera"),
        ("other", "Other")
    ]
    

    # Core fields
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default="fixed_speed_camera")
    
    # Use GIS fields if available, otherwise use JSON/coordinate fields
    if getattr(settings, 'HAS_GIS', False):
        sector = models.PolygonField(geography=True, srid=4326, help_text="Detection area polygon")
        center = models.PointField(geography=True, srid=4326, help_text="Auto-calculated center point")
    else:
        sector_json = models.JSONField(help_text="Detection area polygon as GeoJSON")
        center_lat = models.FloatField(help_text="Center latitude")
        center_lon = models.FloatField(help_text="Center longitude")
    
    # Metadata
    speed_limit = models.IntegerField(null=True, blank=True, help_text="Speed limit in km/h")
    notes = models.TextField(blank=True, help_text="Additional notes about this radar")
    verified = models.BooleanField(default=False, help_text="Whether this radar has been verified")
    active = models.BooleanField(default=True, help_text="Whether this radar is currently active")
    
    # Audit fields
    created_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='created_radars',
        help_text="User who created this radar"
    )
    verified_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='verified_radars',
        help_text="User who verified this radar"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    alert_count = models.PositiveIntegerField(default=0, help_text="Number of times this radar has been detected")
    last_detected = models.DateTimeField(null=True, blank=True, help_text="Last time this radar was detected")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['verified']),
            models.Index(fields=['active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.id}"

    def save(self, *args, **kwargs):
        # Note: center_lat and center_lon should be set from the radar pin location,
        # not calculated from polygon center. The polygon represents detection area,
        # while center coordinates represent the actual radar device location.
        # These coordinates are set by the form when user places the radar pin on the map.
        super().save(*args, **kwargs)

    def mark_verified(self, user=None):
        """Mark radar as verified by a user"""
        self.verified = True
        self.verified_by = user
        self.verified_at = timezone.now()
        self.save(update_fields=['verified', 'verified_by', 'verified_at'])

    def increment_alert_count(self):
        """Increment the alert count and update last detected time"""
        self.alert_count += 1
        self.last_detected = timezone.now()
        self.save(update_fields=['alert_count', 'last_detected'])

    @property
    def coordinates_display(self):
        """Return a readable format of the center coordinates"""
        if getattr(settings, 'HAS_GIS', False):
            if hasattr(self, 'center') and self.center:
                return f"({self.center.y:.6f}, {self.center.x:.6f})"
        else:
            if (hasattr(self, 'center_lat') and hasattr(self, 'center_lon') and 
                self.center_lat is not None and self.center_lon is not None):
                return f"({self.center_lat:.6f}, {self.center_lon:.6f})"
        return "No coordinates"


class RadarReport(models.Model):
    """User reports for radar verification and updates"""
    REPORT_TYPE_CHOICES = [
        ('confirmed', 'Confirmed Active'),
        ('inactive', 'Not Active'),
        ('moved', 'Moved Location'),
        ('false_positive', 'False Detection'),
        ('new_radar', 'New Radar Spotted')
    ]

    radar = models.ForeignKey(
        Radar, 
        on_delete=models.CASCADE, 
        related_name='reports',
        null=True,
        blank=True,
        help_text="Radar being reported (null for new radar reports)"
    )
    reporter_device = models.CharField(max_length=100, help_text="Anonymous device identifier")
    
    # Use GIS field if available, otherwise use coordinate fields
    if getattr(settings, 'HAS_GIS', False):
        location = models.PointField(geography=True, srid=4326, help_text="Location where report was made")
    else:
        location_lat = models.FloatField(help_text="Report location latitude")
        location_lon = models.FloatField(help_text="Report location longitude")
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    notes = models.TextField(blank=True, help_text="Additional notes from reporter")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['radar', 'report_type']),
        ]

    def __str__(self):
        radar_info = f"Radar {self.radar.id}" if self.radar else "New Radar"
        return f"{radar_info} - {self.get_report_type_display()}"


class DetectionLog(models.Model):
    """Anonymous analytics for radar detections"""
    radar = models.ForeignKey(Radar, on_delete=models.CASCADE, related_name='detections')
    device_id = models.CharField(max_length=100, help_text="Anonymous device identifier")
    detected_at = models.DateTimeField(auto_now_add=True)
    speed = models.FloatField(null=True, blank=True, help_text="Vehicle speed in km/h if available")
    
    # Use GIS field if available, otherwise use coordinate fields
    if getattr(settings, 'HAS_GIS', False):
        location = models.PointField(geography=True, srid=4326, help_text="Location where detection occurred")
    else:
        location_lat = models.FloatField(null=True, blank=True, help_text="Detection location latitude")
        location_lon = models.FloatField(null=True, blank=True, help_text="Detection location longitude")
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['radar', 'detected_at']),
            models.Index(fields=['detected_at']),
            models.Index(fields=['device_id', 'detected_at']),
        ]

    def __str__(self):
        return f"Detection of Radar {self.radar.id} at {self.detected_at}"
