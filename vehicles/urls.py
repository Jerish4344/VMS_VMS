# Add this to your vehicles/urls.py

from django.urls import path
from .views import (
    VehicleListView, VehicleDetailView, VehicleCreateView, VehicleUpdateView, VehicleDeleteView,
    VehicleTypeListView, VehicleTypeCreateView, VehicleTypeUpdateView, ImportVehiclesView,
    vehicle_details_api  # Add this import
)

urlpatterns = [
    path('', VehicleListView.as_view(), name='vehicle_list'),
    path('<int:pk>/', VehicleDetailView.as_view(), name='vehicle_detail'),
    path('add/', VehicleCreateView.as_view(), name='vehicle_create'),
    path('<int:pk>/edit/', VehicleUpdateView.as_view(), name='vehicle_update'),
    path('<int:pk>/delete/', VehicleDeleteView.as_view(), name='vehicle_delete'),
    path('types/', VehicleTypeListView.as_view(), name='vehicle_type_list'),
    path('types/add/', VehicleTypeCreateView.as_view(), name='vehicle_type_create'),
    path('types/<int:pk>/edit/', VehicleTypeUpdateView.as_view(), name='vehicle_type_update'),
    path('import/', ImportVehiclesView.as_view(), name='vehicle_import'),
    # Add this new API endpoint
    path('api/<int:vehicle_id>/details/', vehicle_details_api, name='vehicle_details_api'),
]