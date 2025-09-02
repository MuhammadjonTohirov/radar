import django_filters
from radars.models import Radar, RadarReport, DetectionLog


class RadarFilter(django_filters.FilterSet):
    """
    Filter set for Radar model with geographic and metadata filtering
    """
    # Type filtering
    type = django_filters.MultipleChoiceFilter(
        choices=Radar.TYPE_CHOICES,
        help_text="Filter by radar type(s)"
    )
    
    # Status filtering
    verified = django_filters.BooleanFilter(
        help_text="Filter by verification status"
    )
    active = django_filters.BooleanFilter(
        help_text="Filter by active status"
    )
    
    # Speed limit filtering
    speed_limit_min = django_filters.NumberFilter(
        field_name='speed_limit',
        lookup_expr='gte',
        help_text="Minimum speed limit"
    )
    speed_limit_max = django_filters.NumberFilter(
        field_name='speed_limit',
        lookup_expr='lte',
        help_text="Maximum speed limit"
    )
    
    
    # Date filtering
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text="Created after this date"
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text="Created before this date"
    )
    
    # Alert count filtering
    min_alerts = django_filters.NumberFilter(
        field_name='alert_count',
        lookup_expr='gte',
        help_text="Minimum alert count"
    )
    
    # Recent activity
    recently_detected = django_filters.BooleanFilter(
        method='filter_recently_detected',
        help_text="Radars detected in the last 30 days"
    )
    
    class Meta:
        model = Radar
        fields = [
            'type', 'verified', 'active',
            'speed_limit_min', 'speed_limit_max',
            'created_after', 'created_before',
            'min_alerts', 'recently_detected'
        ]
    
    def filter_recently_detected(self, queryset, name, value):
        """Filter radars that have been detected recently"""
        if value:
            from django.utils import timezone
            from datetime import timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(last_detected__gte=thirty_days_ago)
        return queryset


class RadarReportFilter(django_filters.FilterSet):
    """
    Filter set for RadarReport model
    """
    report_type = django_filters.MultipleChoiceFilter(
        choices=RadarReport.REPORT_TYPE_CHOICES,
        help_text="Filter by report type(s)"
    )
    
    radar_type = django_filters.ChoiceFilter(
        field_name='radar__type',
        choices=Radar.TYPE_CHOICES,
        help_text="Filter by radar type"
    )
    
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    
    class Meta:
        model = RadarReport
        fields = ['report_type', 'radar_type', 'created_after', 'created_before']


class DetectionLogFilter(django_filters.FilterSet):
    """
    Filter set for DetectionLog model
    """
    radar_type = django_filters.ChoiceFilter(
        field_name='radar__type',
        choices=Radar.TYPE_CHOICES,
        help_text="Filter by radar type"
    )
    
    speed_min = django_filters.NumberFilter(
        field_name='speed',
        lookup_expr='gte',
        help_text="Minimum speed"
    )
    speed_max = django_filters.NumberFilter(
        field_name='speed',
        lookup_expr='lte',
        help_text="Maximum speed"
    )
    
    detected_after = django_filters.DateTimeFilter(
        field_name='detected_at',
        lookup_expr='gte'
    )
    detected_before = django_filters.DateTimeFilter(
        field_name='detected_at',
        lookup_expr='lte'
    )
    
    # Date shortcuts
    today = django_filters.BooleanFilter(
        method='filter_today',
        help_text="Detections from today"
    )
    this_week = django_filters.BooleanFilter(
        method='filter_this_week',
        help_text="Detections from this week"
    )
    this_month = django_filters.BooleanFilter(
        method='filter_this_month',
        help_text="Detections from this month"
    )
    
    class Meta:
        model = DetectionLog
        fields = [
            'radar_type', 'speed_min', 'speed_max',
            'detected_after', 'detected_before',
            'today', 'this_week', 'this_month'
        ]
    
    def filter_today(self, queryset, name, value):
        if value:
            from django.utils import timezone
            today = timezone.now().date()
            return queryset.filter(detected_at__date=today)
        return queryset
    
    def filter_this_week(self, queryset, name, value):
        if value:
            from django.utils import timezone
            from datetime import timedelta
            week_ago = timezone.now() - timedelta(days=7)
            return queryset.filter(detected_at__gte=week_ago)
        return queryset
    
    def filter_this_month(self, queryset, name, value):
        if value:
            from django.utils import timezone
            from datetime import timedelta
            month_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(detected_at__gte=month_ago)
        return queryset