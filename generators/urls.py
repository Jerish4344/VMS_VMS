"""
URL patterns for the Generator module.

This module defines all URL routes for the Generator functionality:
1. Dashboard view
2. Store management
3. Generator management
4. Usage tracking
5. Fuel entries
6. Maintenance logs
7. API endpoints for AJAX operations
"""

from django.urls import path
from . import views

app_name = 'generators'

urlpatterns = [
    # Dashboard
    path('', views.GeneratorDashboardView.as_view(), name='dashboard'),
    
    # Store Management
    path('stores/', views.StoreListView.as_view(), name='store_list'),
    path('stores/<int:pk>/', views.StoreDetailView.as_view(), name='store_detail'),
    path('stores/create/', views.StoreCreateView.as_view(), name='store_create'),
    path('stores/<int:pk>/update/', views.StoreUpdateView.as_view(), name='store_update'),
    path('stores/<int:pk>/delete/', views.StoreDeleteView.as_view(), name='store_delete'),
    
    # Generator Management
    path('generators/', views.GeneratorListView.as_view(), name='generator_list'),
    path('generators/<int:pk>/', views.GeneratorDetailView.as_view(), name='generator_detail'),
    path('generators/create/', views.GeneratorCreateView.as_view(), name='generator_create'),
    path('generators/<int:pk>/update/', views.GeneratorUpdateView.as_view(), name='generator_update'),
    path('generators/<int:pk>/delete/', views.GeneratorDeleteView.as_view(), name='generator_delete'),
    
    # Usage Tracking
    path('usage/', views.UsageTrackingListView.as_view(), name='usage_tracking_list'),
    path('usage/create/', views.UsageTrackingCreateView.as_view(), name='usage_tracking_create'),
    path('usage/<int:pk>/update/', views.UsageTrackingUpdateView.as_view(), name='usage_tracking_update'),
    path('usage/<int:pk>/delete/', views.UsageTrackingDeleteView.as_view(), name='usage_tracking_delete'),
    
    # Fuel Entries
    path('fuel/', views.FuelEntryListView.as_view(), name='fuel_entry_list'),
    path('fuel/create/', views.FuelEntryCreateView.as_view(), name='fuel_entry_create'),
    path('fuel/<int:pk>/update/', views.FuelEntryUpdateView.as_view(), name='fuel_entry_update'),
    path('fuel/<int:pk>/delete/', views.FuelEntryDeleteView.as_view(), name='fuel_entry_delete'),
    
    # Maintenance Logs
    path('maintenance/', views.MaintenanceLogListView.as_view(), name='maintenance_log_list'),
    path('maintenance/create/', views.MaintenanceLogCreateView.as_view(), name='maintenance_log_create'),
    path('maintenance/<int:pk>/update/', views.MaintenanceLogUpdateView.as_view(), name='maintenance_log_update'),
    path('maintenance/<int:pk>/delete/', views.MaintenanceLogDeleteView.as_view(), name='maintenance_log_delete'),
    
    # API Endpoints for AJAX
    path('api/generators-by-store/<int:store_id>/', views.generators_by_store, name='generators_by_store'),
    path('api/generator-details/<int:generator_id>/', views.generator_details, name='generator_details'),
]
