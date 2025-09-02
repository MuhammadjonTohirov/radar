from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'radars', views.RadarViewSet)
router.register(r'reports', views.RadarReportViewSet)
router.register(r'detections', views.DetectionLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('route/', views.route_view, name='route'),
]
