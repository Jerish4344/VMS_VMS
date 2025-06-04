from django.urls import path
from .views import (
    MaintenanceListView, MaintenanceDetailView, MaintenanceCreateView, 
    MaintenanceUpdateView, MaintenanceDeleteView,
    MaintenanceTypeListView, MaintenanceTypeCreateView, MaintenanceTypeUpdateView, MaintenanceTypeDeleteView,
    MaintenanceProviderListView, MaintenanceProviderCreateView, MaintenanceProviderUpdateView, MaintenanceProviderDeleteView
)

urlpatterns = [
    # Maintenance Records
    path('', MaintenanceListView.as_view(), name='maintenance_list'),
    path('<int:pk>/', MaintenanceDetailView.as_view(), name='maintenance_detail'),
    path('add/', MaintenanceCreateView.as_view(), name='maintenance_create'),
    path('<int:pk>/edit/', MaintenanceUpdateView.as_view(), name='maintenance_update'),
    path('<int:pk>/delete/', MaintenanceDeleteView.as_view(), name='maintenance_delete'),
    
    # Maintenance Types
    path('types/', MaintenanceTypeListView.as_view(), name='maintenance_type_list'),
    path('types/add/', MaintenanceTypeCreateView.as_view(), name='maintenance_type_create'),
    path('types/<int:pk>/edit/', MaintenanceTypeUpdateView.as_view(), name='maintenance_type_update'),
    path('types/<int:pk>/delete/', MaintenanceTypeDeleteView.as_view(), name='maintenance_type_delete'),
    
    # Maintenance Providers
    path('providers/', MaintenanceProviderListView.as_view(), name='maintenance_provider_list'),
    path('providers/add/', MaintenanceProviderCreateView.as_view(), name='maintenance_provider_create'),
    path('providers/<int:pk>/edit/', MaintenanceProviderUpdateView.as_view(), name='maintenance_provider_update'),
    path('providers/<int:pk>/delete/', MaintenanceProviderDeleteView.as_view(), name='maintenance_provider_delete'),
]