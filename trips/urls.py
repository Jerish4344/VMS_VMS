# Updated urls.py file

from django.urls import path, include
from . import views
from .views import (
    TripListView, TripDetailView, StartTripView, EndTripView, TripTrackingView,
    ManualTripCreateView, ManualTripListView,
)

urlpatterns = [
    # Existing URLs
    path('', TripListView.as_view(), name='trip_list'),
    path('<int:pk>/', TripDetailView.as_view(), name='trip_detail'),
    path('start/', StartTripView.as_view(), name='start_trip'),
    path('<int:pk>/end/', EndTripView.as_view(), name='end_trip'),
    path('<int:pk>/track/', TripTrackingView.as_view(), name='track_trip'),

    path('<int:pk>/edit/', views.trip_edit, name='trip_edit'),
    path('<int:pk>/update/', views.trip_update, name='trip_update'),
    path('<int:pk>/delete/', views.trip_delete, name='trip_delete'),
    
    # Export URLs
    path('export/', views.export_trips, name='export_trips'),  # New export URL for trip list

    
    # Manual Trip Entry URLs
    path('manual/', ManualTripListView.as_view(), name='manual_trip_list'),
    path('manual/create/', ManualTripCreateView.as_view(), name='manual_trip_create'),
    path('manual/export/', views.export_manual_trips, name='export_manual_trips'),
    
    # Commented out bulk upload and template views
    # path('manual/bulk-upload/', BulkTripUploadView.as_view(), name='bulk_trip_upload'),
    # path('manual/trip-sheet-template/', TripSheetTemplateView.as_view(), name='trip_sheet_template'),
    
    # API endpoints for AJAX requests
    # path('api/vehicle/<int:vehicle_id>/', get_vehicle_details_api, name='vehicle_details_api'),
    # path('api/driver/<int:driver_id>/', get_driver_details_api, name='driver_details_api'),
]