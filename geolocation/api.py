from rest_framework import viewsets, permissions, status, throttling
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from datetime import datetime, timedelta
import logging

from .models import AiroTrackDevice, VehicleLocation, LocationHistory
from vehicles.models import Vehicle
from .airotrack_service import AiroTrackAPI

# Configure logging
logger = logging.getLogger(__name__)

# ===== Serializers =====

class AiroTrackDeviceSerializer(serializers.ModelSerializer):
    """Serializer for AiroTrack devices"""
    vehicle_info = serializers.SerializerMethodField()
    
    class Meta:
        model = AiroTrackDevice
        fields = ['id', 'device_id', 'name', 'vehicle', 'status', 'last_update', 'vehicle_info']
        read_only_fields = ['status', 'last_update']
    
    def get_vehicle_info(self, obj):
        """Get basic vehicle information if associated"""
        if obj.vehicle:
            return {
                'id': obj.vehicle.id,
                'make': obj.vehicle.make,
                'model': obj.vehicle.model,
                'license_plate': obj.vehicle.license_plate
            }
        return None

class VehicleLocationSerializer(serializers.ModelSerializer):
    """Serializer for current vehicle locations"""
    vehicle_info = serializers.SerializerMethodField()
    device_info = serializers.SerializerMethodField()
    
    class Meta:
        model = VehicleLocation
        fields = [
            'id', 'vehicle', 'device', 'vehicle_info', 'device_info',
            'latitude', 'longitude', 'altitude', 'speed', 'course',
            'device_time', 'server_time', 'fix_time',
            'valid', 'address', 'battery_level', 'signal_strength', 'ignition'
        ]
        read_only_fields = ['server_time']
    
    def get_vehicle_info(self, obj):
        """Get basic vehicle information"""
        return {
            'id': obj.vehicle.id,
            'make': obj.vehicle.make,
            'model': obj.vehicle.model,
            'license_plate': obj.vehicle.license_plate,
            'year': obj.vehicle.year
        }
    
    def get_device_info(self, obj):
        """Get basic device information"""
        return {
            'id': obj.device.id,
            'device_id': obj.device.device_id,
            'name': obj.device.name,
            'status': obj.device.status
        }

class LocationHistorySerializer(serializers.ModelSerializer):
    """Serializer for location history records"""
    
    class Meta:
        model = LocationHistory
        fields = [
            'id', 'vehicle', 'device', 'latitude', 'longitude', 
            'altitude', 'speed', 'course', 'device_time', 'server_time',
            'valid', 'address', 'ignition'
        ]
        read_only_fields = ['server_time']

class VehicleLocationGeoJsonSerializer(serializers.ModelSerializer):
    """Serializer for GeoJSON format of vehicle locations"""
    geojson = serializers.SerializerMethodField()
    
    class Meta:
        model = VehicleLocation
        fields = ['geojson']
    
    def get_geojson(self, obj):
        """Convert location to GeoJSON format"""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(obj.longitude), float(obj.latitude)]
            },
            "properties": {
                "id": obj.id,
                "vehicle_id": obj.vehicle.id,
                "license_plate": obj.vehicle.license_plate,
                "make": obj.vehicle.make,
                "model": obj.vehicle.model,
                "speed": float(obj.speed) if obj.speed else 0,
                "course": float(obj.course) if obj.course else 0,
                "time": obj.device_time.isoformat(),
                "ignition": obj.ignition,
                "valid": obj.valid,
                "status": "active" if float(obj.speed) > 5 else ("idle" if obj.ignition else "inactive")
            }
        }

# ===== Permissions =====

class IsAdminOrVehicleManager(permissions.BasePermission):
    """
    Custom permission to only allow admins and vehicle managers to access.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or 
            request.user.is_superuser or 
            getattr(request.user, 'user_type', '') in ['admin', 'vehicle_manager', 'manager']
        )

class IsVehicleOwnerOrStaff(permissions.BasePermission):
    """
    Custom permission to only allow vehicle owners or staff to access vehicle data.
    """
    def has_object_permission(self, request, view, obj):
        # Staff can access any vehicle
        if request.user.is_staff or request.user.is_superuser:
            return True
            
        # For vehicle objects
        if isinstance(obj, Vehicle):
            vehicle = obj
        # For device objects
        elif isinstance(obj, AiroTrackDevice):
            vehicle = obj.vehicle
        # For location objects
        elif isinstance(obj, VehicleLocation) or isinstance(obj, LocationHistory):
            vehicle = obj.vehicle
        else:
            return False
            
        # Check if user is associated with this vehicle
        # This would need to be customized based on your user-vehicle relationship
        # For example, if drivers are associated with vehicles
        if hasattr(request.user, 'user_type') and request.user.user_type == 'driver':
            # Check if this user is assigned to this vehicle
            # This is a placeholder - implement based on your model relationships
            return False  # Replace with actual check
            
        return False

# ===== Rate Limiting =====

class BurstRateThrottle(throttling.UserRateThrottle):
    """Rate limiting for burst API calls"""
    rate = '60/minute'  # Allow 60 requests per minute

class SustainedRateThrottle(throttling.UserRateThrottle):
    """Rate limiting for sustained API calls"""
    rate = '1000/day'  # Allow 1000 requests per day

# ===== ViewSets =====

class AiroTrackDeviceViewSet(viewsets.ModelViewSet):
    """ViewSet for AiroTrack devices"""
    queryset = AiroTrackDevice.objects.all()
    serializer_class = AiroTrackDeviceSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrVehicleManager]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]
    
    def get_queryset(self):
        """Filter devices based on query parameters"""
        queryset = AiroTrackDevice.objects.all()
        
        # Filter by status
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
            
        # Filter by vehicle
        vehicle_id = self.request.query_params.get('vehicle', None)
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
            
        # Filter by online status
        online = self.request.query_params.get('online', None)
        if online:
            if online.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(status='online')
            elif online.lower() in ['false', '0', 'no']:
                queryset = queryset.exclude(status='online')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def assign_vehicle(self, request, pk=None):
        """Assign a vehicle to this device"""
        device = self.get_object()
        vehicle_id = request.data.get('vehicle_id')
        
        if not vehicle_id:
            return Response(
                {"error": "Vehicle ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
            
            # Check if vehicle already has a device
            if hasattr(vehicle, 'airotrack_device'):
                return Response(
                    {"error": "Vehicle already has an assigned device"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            device.vehicle = vehicle
            device.save()
            
            return Response(
                {"success": f"Device assigned to vehicle {vehicle.license_plate}"},
                status=status.HTTP_200_OK
            )
            
        except Vehicle.DoesNotExist:
            return Response(
                {"error": "Vehicle not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error assigning vehicle to device: {str(e)}")
            return Response(
                {"error": "Failed to assign vehicle"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VehicleLocationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for current vehicle locations (read-only)"""
    queryset = VehicleLocation.objects.all()
    serializer_class = VehicleLocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle]
    
    def get_queryset(self):
        """Filter locations based on query parameters"""
        queryset = VehicleLocation.objects.all()
        
        # Filter by vehicle
        vehicle_id = self.request.query_params.get('vehicle', None)
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
            
        # Filter by status (ignition)
        status = self.request.query_params.get('status', None)
        if status:
            if status.lower() in ['on', 'active', 'true', '1']:
                queryset = queryset.filter(ignition=True)
            elif status.lower() in ['off', 'inactive', 'false', '0']:
                queryset = queryset.filter(ignition=False)
        
        # Filter by time range
        time_from = self.request.query_params.get('from', None)
        if time_from:
            try:
                from_time = datetime.fromisoformat(time_from.replace('Z', '+00:00'))
                queryset = queryset.filter(device_time__gte=from_time)
            except ValueError:
                pass
        
        time_to = self.request.query_params.get('to', None)
        if time_to:
            try:
                to_time = datetime.fromisoformat(time_to.replace('Z', '+00:00'))
                queryset = queryset.filter(device_time__lte=to_time)
            except ValueError:
                pass
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def geojson(self, request):
        """Return locations in GeoJSON format for map display"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = VehicleLocationGeoJsonSerializer(queryset, many=True)
        
        # Construct GeoJSON feature collection
        geojson = {
            "type": "FeatureCollection",
            "features": [item['geojson'] for item in serializer.data]
        }
        
        return Response(geojson)

class LocationHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for location history (read-only)"""
    queryset = LocationHistory.objects.all()
    serializer_class = LocationHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]
    
    def get_queryset(self):
        """Filter history based on query parameters"""
        queryset = LocationHistory.objects.all()
        
        # Filter by vehicle
        vehicle_id = self.request.query_params.get('vehicle', None)
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
            
        # Filter by device
        device_id = self.request.query_params.get('device', None)
        if device_id:
            queryset = queryset.filter(device_id=device_id)
            
        # Filter by time range
        time_from = self.request.query_params.get('from', None)
        if time_from:
            try:
                from_time = datetime.fromisoformat(time_from.replace('Z', '+00:00'))
                queryset = queryset.filter(device_time__gte=from_time)
            except ValueError:
                pass
        
        time_to = self.request.query_params.get('to', None)
        if time_to:
            try:
                to_time = datetime.fromisoformat(time_to.replace('Z', '+00:00'))
                queryset = queryset.filter(device_time__lte=to_time)
            except ValueError:
                pass
        
        # Limit number of results to prevent performance issues
        limit = self.request.query_params.get('limit', 1000)
        try:
            limit = int(limit)
            if limit > 5000:  # Cap at 5000 records
                limit = 5000
        except ValueError:
            limit = 1000
            
        return queryset.order_by('-device_time')[:limit]
    
    @action(detail=False, methods=['get'])
    def geojson(self, request):
        """Return location history in GeoJSON format for map display"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Construct GeoJSON feature collection manually for efficiency
        features = []
        
        for location in queryset:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(location.longitude), float(location.latitude)]
                },
                "properties": {
                    "id": location.id,
                    "vehicle_id": location.vehicle.id,
                    "license_plate": location.vehicle.license_plate,
                    "speed": float(location.speed) if location.speed else 0,
                    "time": location.device_time.isoformat(),
                    "ignition": location.ignition
                }
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return Response(geojson)
    
    @action(detail=False, methods=['get'])
    def route(self, request):
        """Return location history as a route LineString for map display"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get vehicle ID from query params
        vehicle_id = request.query_params.get('vehicle', None)
        if not vehicle_id:
            return Response(
                {"error": "Vehicle ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get coordinates for the route
        coordinates = []
        for location in queryset.order_by('device_time'):
            coordinates.append([float(location.longitude), float(location.latitude)])
        
        if not coordinates:
            return Response(
                {"error": "No location data found for this vehicle"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Construct GeoJSON LineString
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            },
            "properties": {
                "vehicle_id": int(vehicle_id),
                "points": len(coordinates),
                "start_time": queryset.last().device_time.isoformat() if queryset.exists() else None,
                "end_time": queryset.first().device_time.isoformat() if queryset.exists() else None
            }
        }
        
        return Response(geojson)

# ===== API Endpoints =====

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsAdminOrVehicleManager])
@throttle_classes([BurstRateThrottle])
def sync_data(request):
    """
    Manually trigger synchronization with AiroTrack API.
    
    This endpoint is used to fetch the latest data from AiroTrack
    and update the local database.
    """
    try:
        api_service = AiroTrackAPI()
        sync_result = api_service.sync_all_data()
        
        return Response({
            "success": True,
            "message": "Synchronization completed successfully",
            "details": sync_result
        })
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        return Response({
            "success": False,
            "message": "Synchronization failed",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BurstRateThrottle])
def vehicle_current_location(request, vehicle_id):
    """
    Get the current location of a specific vehicle.
    
    This endpoint returns the most recent location data for a vehicle,
    including status information.
    """
    try:
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        
        # Check if user has permission to view this vehicle
        if not (request.user.is_staff or request.user.is_superuser):
            # Add your custom permission logic here
            pass
        
        try:
            location = VehicleLocation.objects.get(vehicle=vehicle)
            serializer = VehicleLocationSerializer(location)
            
            # Check if location is stale (older than 10 minutes)
            is_stale = (timezone.now() - location.server_time) > timedelta(minutes=10)
            
            response_data = serializer.data
            response_data['is_stale'] = is_stale
            
            return Response(response_data)
            
        except VehicleLocation.DoesNotExist:
            return Response({
                "error": "No location data available for this vehicle",
                "vehicle_id": vehicle_id
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error retrieving vehicle location: {str(e)}")
        return Response({
            "error": "Failed to retrieve vehicle location",
            "details": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BurstRateThrottle])
def all_vehicles_current_location(request):
    """
    Get the current location of all vehicles.
    
    This endpoint returns the most recent location data for all vehicles,
    formatted for map display.
    """
    try:
        # Get format parameter (default to 'json')
        format_type = request.query_params.get('format', 'json').lower()
        
        # Get all vehicle locations
        locations = VehicleLocation.objects.all()
        
        if format_type == 'geojson':
            # Return as GeoJSON for map display
            serializer = VehicleLocationGeoJsonSerializer(locations, many=True)
            geojson = {
                "type": "FeatureCollection",
                "features": [item['geojson'] for item in serializer.data],
                "timestamp": timezone.now().isoformat()
            }
            return Response(geojson)
        else:
            # Return as regular JSON
            serializer = VehicleLocationSerializer(locations, many=True)
            return Response(serializer.data)
            
    except Exception as e:
        logger.error(f"Error retrieving all vehicle locations: {str(e)}")
        return Response({
            "error": "Failed to retrieve vehicle locations",
            "details": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
