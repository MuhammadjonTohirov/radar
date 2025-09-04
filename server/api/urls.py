from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

router = DefaultRouter()
router.register(r'radars', views.RadarViewSet)
router.register(r'reports', views.RadarReportViewSet)
router.register(r'detections', views.DetectionLogViewSet)

urlpatterns = [
    # OpenAPI schema and docs
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # Place specific endpoints BEFORE router include to avoid being captured
    # by the ViewSet detail route (e.g., 'radars/<pk>/').
    path('radars/impacted/', views.radars_impacted_view, name='radars-impacted'),
    path('radars/nearby/', views.radars_nearby_view, name='radars-nearby'),
    # Mobile: versioned radius updates
    path('mobile/radars/updates/', views.radars_updates_view, name='mobile-radars-updates'),
    path('route/', views.route_view, name='route'),
    # Auth endpoints (Djoser)
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    # JWT refresh/verify for mobile sessions
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
    path('auth/jwt/verify/', TokenVerifyView.as_view(), name='jwt-verify'),
    # Simple phone OTP auth (dev)
    path('auth/otp/request/', views.otp_request_view, name='otp-request'),
    path('auth/otp/verify/', views.otp_verify_view, name='otp-verify'),
    path('', include(router.urls)),
]
