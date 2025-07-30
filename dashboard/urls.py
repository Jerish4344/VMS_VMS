from django.urls import path
from .views import DashboardView, ongoing_trips_by_type_api

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('api/ongoing-trips-by-type/', ongoing_trips_by_type_api, name='ongoing_trips_by_type_api'),
]
