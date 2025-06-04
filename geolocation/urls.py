from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import LocationLogViewSet, update_location

router = DefaultRouter()
router.register(r'location-logs', LocationLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('location/update/', update_location, name='location_update'),
]