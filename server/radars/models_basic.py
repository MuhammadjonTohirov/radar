from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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
    
    DIRECTION_CHOICES = [
        ("both", "Both Directions"),
        ("north", "Northbound"),
        ("south", "Southbound"),
        ("east", "Eastbound"),
        ("west", "Westbound")
    ]

    # Core fields
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default="fixed_speed_camera")
    # Store polygon as JSON string for non-GIS setup
    sector_json = models.JSONField(help_text="Detection area polygon as GeoJSON")
    # Store center coordinates
    center_lat = models.FloatField(help_text="Center latitude")
    center_lon = models.FloatField(help_text="Center longitude")
    
    # Metadata
    speed_limit = models.IntegerField(null=True, blank=True, help_text="Speed limit in km/h")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, blank=True, default="both")
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
            models.Index(fields=['center_lat', 'center_lon']),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.id}"

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
        return f"({self.center_lat:.6f}, {self.center_lon:.6f})"