from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import LocationLog
from trips.models import Trip
from .serializers import LocationLogSerializer
from django.shortcuts import get_object_or_404

class IsDriverOfTrip(permissions.BasePermission):
    """
    Custom permission to only allow drivers of the trip to submit location updates.
    """
    def has_permission(self, request, view):
        trip_id = request.data.get('trip')
        if not trip_id:
            return False
        
        try:
            trip = Trip.objects.get(pk=trip_id)
            return request.user == trip.driver
        except Trip.DoesNotExist:
            return False

class LocationLogViewSet(viewsets.ModelViewSet):
    queryset = LocationLog.objects.all()
    serializer_class = LocationLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = LocationLog.objects.all()
        trip_id = self.request.query_params.get('trip', None)
        
        if trip_id is not None:
            queryset = queryset.filter(trip_id=trip_id)
            
        return queryset
    
    def perform_create(self, serializer):
        trip_id = self.request.data.get('trip')
        trip = get_object_or_404(Trip, pk=trip_id)
        
        # Only allow the driver to submit location updates
        if self.request.user != trip.driver:
            self.permission_denied(self.request)
            
        serializer.save()

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsDriverOfTrip])
def update_location(request):
    """
    API endpoint for drivers to update their current location during a trip.
    """
    serializer = LocationLogSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

# geolocation/serializers.py
from rest_framework import serializers
from .models import LocationLog

class LocationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationLog
        fields = ['id', 'trip', 'latitude', 'longitude', 'altitude', 'speed', 'timestamp']
        read_only_fields = ['timestamp']