from django.urls import path
from .views import (
    VehicleReportView, DriverReportView, MaintenanceReportView, FuelReportView
)

urlpatterns = [
    path('vehicles/', VehicleReportView.as_view(), name='vehicle_report'),
    path('drivers/', DriverReportView.as_view(), name='driver_report'),
    path('maintenance/', MaintenanceReportView.as_view(), name='maintenance_report'),
    path('fuel/', FuelReportView.as_view(), name='fuel_report'),
]