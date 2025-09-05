from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from .models import Radar, RadarReport, DetectionLog, RadarCategory

# Use GIS admin if available, otherwise use regular admin
if getattr(settings, 'HAS_GIS', False):
    try:
        from django.contrib.gis.admin import OSMGeoAdmin
        BaseRadarAdmin = OSMGeoAdmin
    except ImportError:
        BaseRadarAdmin = admin.ModelAdmin
else:
    BaseRadarAdmin = admin.ModelAdmin


@admin.register(Radar)
class RadarAdmin(BaseRadarAdmin):
    list_display = [
        'id', 'category', 'coordinates_display', 'speed_limit',
        'verified', 'active', 'alert_count', 'created_at'
    ]
    list_filter = [
        'category', 'verified', 'active', 'created_at', 'speed_limit'
    ]
    search_fields = ['notes', 'id']
    def get_readonly_fields(self, request, obj=None):
        readonly = ['created_at', 'updated_at', 'alert_count', 'last_detected', 'coordinates_display']
        if getattr(settings, 'HAS_GIS', False):
            readonly.append('center')
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        if getattr(settings, 'HAS_GIS', False):
            radar_fields = ['category', 'sector', 'center', 'coordinates_display']
        else:
            radar_fields = ['category', 'sector_json', 'center_lat', 'center_lon', 'coordinates_display']
        
        return [
            ('Radar Information', {
                'fields': radar_fields
            }),
            ('Traffic Details', {
                'fields': ['speed_limit', 'notes']
            }),
            ('Presentation', {
                'fields': ['icon', 'icon_color']
            }),
            ('Status', {
                'fields': ['verified', 'active']
            }),
            ('Analytics', {
                'fields': ['alert_count', 'last_detected'],
                'classes': ['collapse']
            }),
            ('Audit Trail', {
                'fields': [
                    'created_by', 'verified_by', 'created_at', 
                    'updated_at', 'verified_at'
                ],
                'classes': ['collapse']
            })
        ]
    
    # Map settings for OSMGeoAdmin
    default_zoom = 12
    map_width = 800
    map_height = 500
    
    actions = ['mark_as_verified', 'mark_as_active', 'mark_as_inactive']
    
    def mark_as_verified(self, request, queryset):
        updated = 0
        for radar in queryset:
            if not radar.verified:
                radar.mark_verified(request.user)
                updated += 1
        self.message_user(request, f'{updated} radars marked as verified.')
    mark_as_verified.short_description = "Mark selected radars as verified"
    
    def mark_as_active(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} radars marked as active.')
    mark_as_active.short_description = "Mark selected radars as active"
    
    def mark_as_inactive(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} radars marked as inactive.')
    mark_as_inactive.short_description = "Mark selected radars as inactive"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new radar
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RadarCategory)
class RadarCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code', 'color', 'order', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        (None, {'fields': ['name', 'code', 'groups', 'order', 'is_active']}),
        ('Presentation', {'fields': ['color', 'icon']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(RadarReport)
class RadarReportAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'radar_link', 'report_type', 'reporter_device',
        'created_at'
    ]
    list_filter = ['report_type', 'created_at']
    search_fields = ['reporter_device', 'notes', 'radar__id']
    def get_readonly_fields(self, request, obj=None):
        readonly = ['created_at', 'reporter_device']
        if getattr(settings, 'HAS_GIS', False):
            readonly.append('location')
        else:
            readonly.extend(['location_lat', 'location_lon'])
        return readonly
    
    def radar_link(self, obj):
        if obj.radar:
            url = f"/admin/radars/radar/{obj.radar.id}/change/"
            return format_html('<a href="{}">{}</a>', url, str(obj.radar))
        return "New Radar"
    radar_link.short_description = "Radar"
    radar_link.admin_order_field = "radar"


@admin.register(DetectionLog)
class DetectionLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'radar_link', 'device_id', 'speed', 'detected_at'
    ]
    list_filter = ['detected_at', 'radar__category']
    search_fields = ['device_id', 'radar__id']
    def get_readonly_fields(self, request, obj=None):
        readonly = ['detected_at', 'device_id', 'radar']
        if getattr(settings, 'HAS_GIS', False):
            readonly.append('location')
        else:
            readonly.extend(['location_lat', 'location_lon'])
        return readonly
    date_hierarchy = 'detected_at'
    
    def radar_link(self, obj):
        url = f"/admin/radars/radar/{obj.radar.id}/change/"
        return format_html('<a href="{}">{}</a>', url, str(obj.radar))
    radar_link.short_description = "Radar"
    radar_link.admin_order_field = "radar"
    
    def has_add_permission(self, request):
        return False  # Don't allow manual creation of detection logs
    
    def has_change_permission(self, request, obj=None):
        return False  # Don't allow editing detection logs
