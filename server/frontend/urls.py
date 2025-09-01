from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    path('', views.radar_list, name='radar_list'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('radars/', views.radar_list, name='radar_list'),
    path('radars/add/', views.radar_add, name='radar_add'),
    path('radars/<int:radar_id>/edit/', views.radar_edit, name='radar_edit'),
    path('radars/<int:radar_id>/delete/', views.radar_delete, name='radar_delete'),
]