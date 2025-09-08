from django.urls import path
# Import FirmReportView from new file
from .views import (
    VehicleReportView, DriverReportView, MaintenanceReportView, FuelReportView, 
    DailyUsageCostView
)
from .firm_report_view import FirmReportView
# Consultant report view resides in a separate module to keep code modular
from .consultant_views import ConsultantReportView

urlpatterns = [
    path('vehicles/', VehicleReportView.as_view(), name='vehicle_report'),
    path('drivers/', DriverReportView.as_view(), name='driver_report'),
    path('maintenance/', MaintenanceReportView.as_view(), name='maintenance_report'),
    path('fuel/', FuelReportView.as_view(), name='fuel_report'),
    path('consultant/', ConsultantReportView.as_view(), name='consultant_report'),
    path('daily-usage-cost/', DailyUsageCostView.as_view(), name='daily_usage_cost'),
    path('firm/', FirmReportView.as_view(), name='firm_report'),
]
