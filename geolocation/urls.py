from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import api

# API Router for RESTful endpoints
router = DefaultRouter()
router.register(r'devices', api.AiroTrackDeviceViewSet)
router.register(r'locations', api.VehicleLocationViewSet)
router.register(r'history', api.LocationHistoryViewSet)

urlpatterns = [
    # Main tracking dashboard
    path('tracking/', views.tracking_dashboard, name='tracking_dashboard'),
    
    # Vehicle-specific tracking
    path('tracking/vehicle/<int:vehicle_id>/', views.vehicle_tracking_detail, name='vehicle_tracking_detail'),
    path('tracking/vehicle/<int:vehicle_id>/history/', views.vehicle_tracking_history, name='vehicle_tracking_history'),
    
    # Map views
    path('map/', views.map_view, name='map_view'),
    path('map/all/', views.all_vehicles_map, name='all_vehicles_map'),
    
    # Device management
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_add, name='device_add'),
    path('devices/<int:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<int:device_id>/edit/', views.device_edit, name='device_edit'),
    # Extra device management endpoints referenced in templates
    path('devices/<int:device_id>/settings/', views.device_settings, name='device_settings'),
    path('devices/<int:device_id>/status/', views.device_status, name='device_status'),
    path('devices/<int:device_id>/history/data/', views.device_history_data, name='device_history_data'),
    path('devices/<int:device_id>/sync/', views.sync_device, name='sync_device'),
    path('devices/<int:device_id>/delete/', views.device_delete, name='device_delete'),
    path('devices/<int:device_id>/export/', views.device_export, name='device_export'),
    
    # Admin functions
    path('admin/sync/', views.sync_airotrack, name='sync_airotrack'),
    path('admin/settings/', views.airotrack_settings, name='airotrack_settings'),
    
    # API endpoints
    path('api/', include(router.urls)),
    path('api/sync/', api.sync_data, name='api_sync_data'),
    path('api/vehicle/<int:vehicle_id>/current/', api.vehicle_current_location, name='api_vehicle_current_location'),
    path('api/vehicles/current/', api.all_vehicles_current_location, name='api_all_vehicles_current_location'),
    
    # AJAX endpoints for real-time updates
    path('ajax/locations/', views.ajax_vehicle_locations, name='ajax_vehicle_locations'),
    path('ajax/vehicle/<int:vehicle_id>/', views.ajax_vehicle_detail, name='ajax_vehicle_detail'),
]
