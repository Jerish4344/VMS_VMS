from django.urls import path
from .views import DashboardView, StaffDashboardView, ongoing_trips_by_type_api

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('staff/', StaffDashboardView.as_view(), name='staff_dashboard'),
    path('api/ongoing-trips-by-type/', ongoing_trips_by_type_api, name='ongoing_trips_by_type_api'),
]
