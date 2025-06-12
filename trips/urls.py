# Updated urls.py file

from django.urls import path, include
from . import views
from .views import (
    TripListView, TripDetailView, StartTripView, EndTripView, TripTrackingView,
    ManualTripCreateView, ManualTripListView,
)

urlpatterns = [
    # Export URLs (should come before dynamic URLs)
    path('export/', views.export_trips, name='export_trips'),
    path('manual/export/', views.export_manual_trips, name='export_manual_trips'),
    
    # Manual Trip Entry URLs (should come before dynamic URLs)
    path('manual/', ManualTripListView.as_view(), name='manual_trip_list'),
    path('manual/create/', ManualTripCreateView.as_view(), name='manual_trip_create'),
    
    # Trip management URLs
    path('', TripListView.as_view(), name='trip_list'),
    path('start/', StartTripView.as_view(), name='start_trip'),
    
    # Dynamic URLs with primary keys (should come after static URLs)
    path('<int:pk>/', TripDetailView.as_view(), name='trip_detail'),
    path('<int:pk>/end/', EndTripView.as_view(), name='end_trip'),
    path('<int:pk>/track/', TripTrackingView.as_view(), name='track_trip'),
    path('<int:pk>/edit/', views.trip_edit, name='trip_edit'),
    path('<int:pk>/update/', views.trip_update, name='trip_update'),
    path('<int:pk>/delete/', views.trip_delete, name='trip_delete'),
    
    # Commented out bulk upload and template views
    # path('manual/bulk-upload/', BulkTripUploadView.as_view(), name='bulk_trip_upload'),
    # path('manual/trip-sheet-template/', TripSheetTemplateView.as_view(), name='trip_sheet_template'),
    
    # API endpoints for AJAX requests
    # path('api/vehicle/<int:vehicle_id>/', get_vehicle_details_api, name='vehicle_details_api'),
    # path('api/driver/<int:driver_id>/', get_driver_details_api, name='driver_details_api'),
]