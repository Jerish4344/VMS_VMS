from django.contrib.admin import AdminSite
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.contrib import messages
from django.db.models import Count, Avg, Max, Q
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from datetime import timedelta
import json
import logging

from .models import AiroTrackDevice, VehicleLocation, LocationHistory
from .airotrack_service import AiroTrackAPI
from vehicles.models import Vehicle

# Configure logging
logger = logging.getLogger(__name__)

csrf_protect_m = method_decorator(csrf_protect)
staff_member_required_m = method_decorator(staff_member_required)

class TrackingAdminSite(AdminSite):
    """
    Custom admin site for vehicle tracking management.
    
    This admin site provides specialized tracking dashboards, metrics,
    and management tools for the GPS tracking system.
    """
    site_header = 'VMS Tracking Administration'
    site_title = 'Vehicle Tracking Admin'
    index_title = 'GPS Tracking Management'
    
    def __init__(self, name='tracking_admin'):
        super().__init__(name)
        self._registry = {}
        self._actions = {}
        self._global_actions = {}
    
    def get_urls(self):
        """Add custom URLs for tracking management."""
        urls = super().get_urls()
        custom_urls = [
            path('tracking-dashboard/', self.admin_view(self.tracking_dashboard), name='tracking_admin_dashboard'),
            path('sync-all-devices/', self.admin_view(self.sync_all_devices), name='sync_all_devices'),
            path('sync-device/<int:device_id>/', self.admin_view(self.sync_device), name='sync_device_admin'),
            path('device-status/<int:device_id>/', self.admin_view(self.device_status), name='device_status_admin'),
            path('tracking-metrics/', self.admin_view(self.tracking_metrics), name='tracking_metrics'),
            path('tracking-map/', self.admin_view(self.tracking_map), name='tracking_map_admin'),
            path('vehicle-locations-json/', self.admin_view(self.vehicle_locations_json), name='vehicle_locations_json'),
        ]
        return custom_urls + urls
    
    @csrf_protect_m
    @staff_member_required_m
    def tracking_dashboard(self, request):
        """
        Custom dashboard for tracking management.
        
        Shows key metrics, device status, and recent activity.
        """
        # Get counts for dashboard stats
        total_devices = AiroTrackDevice.objects.count()
        online_devices = AiroTrackDevice.objects.filter(status='online').count()
        offline_devices = AiroTrackDevice.objects.filter(status='offline').count()
        inactive_devices = AiroTrackDevice.objects.filter(status='inactive').count()
        unknown_devices = AiroTrackDevice.objects.filter(status='unknown').count()
        
        # Get vehicle stats
        total_vehicles = Vehicle.objects.count()
        tracked_vehicles = Vehicle.objects.filter(airotrack_device__isnull=False).count()
        untracked_vehicles = total_vehicles - tracked_vehicles
        
        # Get location stats
        try:
            active_vehicles = VehicleLocation.objects.filter(
                Q(speed__gt=5),
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            idle_vehicles = VehicleLocation.objects.filter(
                Q(speed__lte=5) & Q(ignition=True),
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            parked_vehicles = VehicleLocation.objects.filter(
                Q(speed__lte=5) & (Q(ignition=False) | Q(ignition__isnull=True)),
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            unknown_status = tracked_vehicles - active_vehicles - idle_vehicles - parked_vehicles
            
            # Get average speed of active vehicles
            avg_speed = VehicleLocation.objects.filter(
                speed__gt=0,
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).aggregate(avg_speed=Avg('speed'))['avg_speed'] or 0
            
            # Get max speed
            max_speed = VehicleLocation.objects.filter(
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).aggregate(max_speed=Max('speed'))['max_speed'] or 0
            
        except Exception as e:
            logger.error(f"Error calculating location stats: {str(e)}")
            active_vehicles = idle_vehicles = parked_vehicles = unknown_status = 0
            avg_speed = max_speed = 0
        
        # Get recent history
        recent_history = LocationHistory.objects.select_related('vehicle', 'device').order_by('-device_time')[:10]
        
        # Get last sync time
        try:
            last_sync = AiroTrackDevice.objects.latest('last_update').last_update
        except (AiroTrackDevice.DoesNotExist, AttributeError):
            last_sync = None
        
        # Get devices with issues (offline for more than 24 hours)
        problem_devices = AiroTrackDevice.objects.filter(
            Q(status='offline') | Q(status='unknown'),
            last_update__lt=timezone.now() - timedelta(hours=24)
        ).select_related('vehicle')[:5]
        
        # Prepare chart data for active vehicles by hour
        hourly_data = []
        for hour in range(24):
            time_threshold = timezone.now() - timedelta(hours=23-hour)
            active_count = LocationHistory.objects.filter(
                device_time__gte=time_threshold,
                device_time__lt=time_threshold + timedelta(hours=1),
                speed__gt=5
            ).values('vehicle').distinct().count()
            
            hourly_data.append({
                'hour': (timezone.now() - timedelta(hours=23-hour)).strftime('%H:00'),
                'count': active_count
            })
        
        context = {
            'title': 'GPS Tracking Dashboard',
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'inactive_devices': inactive_devices,
            'unknown_devices': unknown_devices,
            'total_vehicles': total_vehicles,
            'tracked_vehicles': tracked_vehicles,
            'untracked_vehicles': untracked_vehicles,
            'active_vehicles': active_vehicles,
            'idle_vehicles': idle_vehicles,
            'parked_vehicles': parked_vehicles,
            'unknown_status': unknown_status,
            'avg_speed': round(float(avg_speed), 1) if avg_speed else 0,
            'max_speed': round(float(max_speed), 1) if max_speed else 0,
            'recent_history': recent_history,
            'last_sync': last_sync,
            'problem_devices': problem_devices,
            'hourly_data': json.dumps(hourly_data),
            'has_permission': True,
            'is_popup': False,
            'is_nav_sidebar_enabled': True,
            'has_sidebar': True,
            'available_apps': self.get_app_list(request),
            'opts': AiroTrackDevice._meta,
            'app_label': 'geolocation',
        }
        
        return TemplateResponse(request, 'admin/geolocation/tracking_dashboard.html', context)
    
    @csrf_protect_m
    @staff_member_required_m
    def sync_all_devices(self, request):
        """
        Sync all devices with AiroTrack API.
        
        Triggers a full synchronization and redirects back to the dashboard.
        """
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:tracking_admin_dashboard'))
        
        try:
            api_service = AiroTrackAPI()
            sync_result = api_service.sync_all_data()
            
            messages.success(
                request, 
                f"Sync completed: {sync_result['devices_created']} devices created, "
                f"{sync_result['devices_updated']} updated, "
                f"{sync_result['locations_updated']} locations updated."
            )
        except Exception as e:
            logger.error(f"Sync failed: {str(e)}")
            messages.error(request, f"Synchronization failed: {str(e)}")
        
        # Redirect back to referring page or dashboard
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:tracking_admin_dashboard')))
    
    @csrf_protect_m
    @staff_member_required_m
    def sync_device(self, request, device_id):
        """
        Sync a specific device with AiroTrack API.
        
        Args:
            device_id (int): The ID of the device to sync
            
        Returns:
            JsonResponse: Result of the sync operation
        """
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
        try:
            device = AiroTrackDevice.objects.get(pk=device_id)
            
            # Initialize API service
            api_service = AiroTrackAPI()
            
            # Get device info from API
            device_info = api_service.get_device_info(device.device_id)
            
            if not device_info:
                return JsonResponse({
                    'success': False, 
                    'error': "Could not retrieve device information from AiroTrack API"
                }, status=404)
            
            # Update device info
            device.status = 'online' if device_info.get('status') == 'online' else 'offline'
            device.last_update = timezone.now()
            device.save()
            
            # Get position data if device is assigned to a vehicle
            location_updated = False
            if device.vehicle:
                positions = api_service.get_positions(device_ids=[device.device_id])
                
                if positions and len(positions) > 0:
                    # Process the latest position
                    position_data = api_service._parse_position_data(positions[0])
                    
                    if position_data:
                        # Update or create current location
                        location, created = VehicleLocation.objects.update_or_create(
                            vehicle=device.vehicle,
                            device=device,
                            defaults={
                                'latitude': position_data['latitude'],
                                'longitude': position_data['longitude'],
                                'altitude': position_data['altitude'],
                                'speed': position_data['speed'],
                                'course': position_data['course'],
                                'device_time': position_data['device_time'],
                                'server_time': position_data['server_time'],
                                'fix_time': position_data['fix_time'],
                                'valid': position_data['valid'],
                                'address': position_data['address'],
                                'ignition': position_data['ignition'],
                                'battery_level': position_data.get('battery_level'),
                                'raw_data': position_data['raw_data']
                            }
                        )
                        
                        # Create history entry
                        LocationHistory.objects.create(
                            vehicle=device.vehicle,
                            device=device,
                            latitude=position_data['latitude'],
                            longitude=position_data['longitude'],
                            altitude=position_data['altitude'],
                            speed=position_data['speed'],
                            course=position_data['course'],
                            device_time=position_data['device_time'],
                            valid=position_data['valid'],
                            address=position_data['address'],
                            ignition=position_data['ignition']
                        )
                        
                        location_updated = True
            
            return JsonResponse({
                'success': True,
                'device': {
                    'id': device.id,
                    'name': device.name or device.device_id,
                    'status': device.status,
                    'last_update': device.last_update.isoformat()
                },
                'location_updated': location_updated
            })
            
        except AiroTrackDevice.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Device not found'}, status=404)
        except Exception as e:
            logger.error(f"Error syncing device: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    @csrf_protect_m
    @staff_member_required_m
    def device_status(self, request, device_id):
        """
        Get the current status of a device.
        
        Args:
            device_id (int): The ID of the device
            
        Returns:
            JsonResponse: Current status of the device
        """
        try:
            device = AiroTrackDevice.objects.get(pk=device_id)
            
            # Get current location if device is assigned to a vehicle
            current_location = None
            if device.vehicle:
                try:
                    location = VehicleLocation.objects.get(device=device)
                    current_location = {
                        'latitude': float(location.latitude),
                        'longitude': float(location.longitude),
                        'speed': float(location.speed) if location.speed else 0,
                        'course': float(location.course) if location.course else 0,
                        'time': location.device_time.isoformat(),
                        'time_relative': f"{(timezone.now() - location.device_time).total_seconds() // 60:.0f} minutes ago",
                        'address': location.address or "Unknown location",
                        'ignition': location.ignition
                    }
                except VehicleLocation.DoesNotExist:
                    pass
            
            # Determine status class for UI
            status_class = {
                'online': 'success',
                'offline': 'warning',
                'inactive': 'secondary',
                'unknown': 'secondary'
            }.get(device.status, 'secondary')
            
            # Construct response
            response_data = {
                'id': device.id,
                'device_id': device.device_id,
                'name': device.name,
                'status': device.status,
                'status_display': device.get_status_display(),
                'status_class': status_class,
                'last_update': device.last_update.isoformat() if device.last_update else None,
                'last_update_relative': f"{(timezone.now() - device.last_update).total_seconds() // 60:.0f} minutes ago" if device.last_update else "Never",
                'vehicle_id': device.vehicle.id if device.vehicle else None,
                'vehicle_plate': device.vehicle.license_plate if device.vehicle else None,
                'current_location': current_location
            }
            
            return JsonResponse(response_data)
            
        except AiroTrackDevice.DoesNotExist:
            return JsonResponse({'error': 'Device not found'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching device status: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @csrf_protect_m
    @staff_member_required_m
    def tracking_metrics(self, request):
        """
        Return metrics for tracking dashboard.
        
        Returns:
            JsonResponse: Current tracking metrics
        """
        try:
            # Get counts for dashboard stats
            total_devices = AiroTrackDevice.objects.count()
            online_devices = AiroTrackDevice.objects.filter(status='online').count()
            offline_devices = AiroTrackDevice.objects.filter(status='offline').count()
            
            # Get vehicle stats
            tracked_vehicles = Vehicle.objects.filter(airotrack_device__isnull=False).count()
            
            # Get location stats
            active_vehicles = VehicleLocation.objects.filter(
                Q(speed__gt=5) | Q(ignition=True),
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            parked_vehicles = VehicleLocation.objects.filter(
                Q(speed__lte=5) & (Q(ignition=False) | Q(ignition__isnull=True)),
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            # Get average speed of active vehicles
            avg_speed = VehicleLocation.objects.filter(
                speed__gt=0,
                device_time__gte=timezone.now() - timedelta(hours=1)
            ).aggregate(avg_speed=Avg('speed'))['avg_speed'] or 0
            
            # Get last sync time
            try:
                last_sync = AiroTrackDevice.objects.latest('last_update').last_update
                last_sync_relative = f"{(timezone.now() - last_sync).total_seconds() // 60:.0f} minutes ago"
            except (AiroTrackDevice.DoesNotExist, AttributeError):
                last_sync = None
                last_sync_relative = "Never"
            
            # Prepare response
            metrics = {
                'total_devices': total_devices,
                'online_devices': online_devices,
                'offline_devices': offline_devices,
                'tracked_vehicles': tracked_vehicles,
                'active_vehicles': active_vehicles,
                'parked_vehicles': parked_vehicles,
                'avg_speed': round(float(avg_speed), 1) if avg_speed else 0,
                'last_sync': last_sync.isoformat() if last_sync else None,
                'last_sync_relative': last_sync_relative,
                'timestamp': timezone.now().isoformat()
            }
            
            return JsonResponse(metrics)
            
        except Exception as e:
            logger.error(f"Error fetching tracking metrics: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @csrf_protect_m
    @staff_member_required_m
    def tracking_map(self, request):
        """
        Display a map of all tracked vehicles.
        
        Shows all vehicles on a map with their current status.
        """
        # Get all vehicles with tracking devices
        vehicles = Vehicle.objects.filter(airotrack_device__isnull=False)
        
        context = {
            'title': 'Vehicle Tracking Map',
            'vehicles': vehicles,
            'has_permission': True,
            'is_popup': False,
            'is_nav_sidebar_enabled': True,
            'has_sidebar': True,
            'available_apps': self.get_app_list(request),
            'opts': AiroTrackDevice._meta,
            'app_label': 'geolocation',
        }
        
        return TemplateResponse(request, 'admin/geolocation/tracking_map.html', context)
    
    @csrf_protect_m
    @staff_member_required_m
    def vehicle_locations_json(self, request):
        """
        Return current vehicle locations as GeoJSON.
        
        Returns:
            JsonResponse: GeoJSON of vehicle locations
        """
        try:
            # Get all current locations
            locations = VehicleLocation.objects.select_related('vehicle', 'device').all()
            
            # Convert to GeoJSON
            features = []
            for location in locations:
                # Skip if no valid coordinates
                if not location.latitude or not location.longitude:
                    continue
                    
                # Get vehicle status
                if (timezone.now() - location.device_time) > timedelta(minutes=60):
                    status = "unknown"
                elif float(location.speed) > 5:
                    status = "active"
                elif location.ignition:
                    status = "idle"
                else:
                    status = "inactive"
                
                # Create GeoJSON feature
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(location.longitude), float(location.latitude)]
                    },
                    "properties": {
                        "id": location.vehicle.id,
                        "license_plate": location.vehicle.license_plate,
                        "make": location.vehicle.make,
                        "model": location.vehicle.model,
                        "speed": float(location.speed) if location.speed else 0,
                        "course": float(location.course) if location.course else 0,
                        "time": location.device_time.isoformat(),
                        "status": status,
                        "ignition": location.ignition,
                        "address": location.address or ""
                    }
                }
                features.append(feature)
            
            # Create GeoJSON feature collection
            geojson = {
                "type": "FeatureCollection",
                "features": features,
                "timestamp": timezone.now().isoformat()
            }
            
            return JsonResponse(geojson)
            
        except Exception as e:
            logger.error(f"Error fetching vehicle locations: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def each_context(self, request):
        """Add extra context to each admin view."""
        context = super().each_context(request)
        context.update({
            'tracking_dashboard_url': reverse('admin:tracking_admin_dashboard'),
            'tracking_map_url': reverse('admin:tracking_map_admin'),
            'is_tracking_admin': True
        })
        return context

# Create an instance of the custom admin site
tracking_admin_site = TrackingAdminSite()

# Register the same models as the default admin site
from .admin import AiroTrackDeviceAdmin, VehicleLocationAdmin, LocationHistoryAdmin
from .models import AiroTrackDevice, VehicleLocation, LocationHistory

tracking_admin_site.register(AiroTrackDevice, AiroTrackDeviceAdmin)
tracking_admin_site.register(VehicleLocation, VehicleLocationAdmin)
tracking_admin_site.register(LocationHistory, LocationHistoryAdmin)

# Function to integrate with main admin
def integrate_with_main_admin(admin_site):
    """
    Add tracking links to the main admin site.
    
    This function adds custom links to the main admin site
    to access the tracking dashboard and other tracking features.
    """
    # Original get_urls method
    original_get_urls = admin_site.get_urls
    
    # Custom get_urls method
    def get_urls():
        urls = original_get_urls()
        tracking_urls = [
            path('tracking-dashboard/', admin_site.admin_view(tracking_admin_site.tracking_dashboard), 
                 name='main_tracking_dashboard'),
            path('tracking-map/', admin_site.admin_view(tracking_admin_site.tracking_map), 
                 name='main_tracking_map'),
        ]
        return tracking_urls + urls
    
    # Original each_context method
    original_each_context = admin_site.each_context
    
    # Custom each_context method
    def each_context(request):
        context = original_each_context(request)
        context.update({
            'has_tracking_integration': True,
            'tracking_dashboard_url': reverse('admin:main_tracking_dashboard'),
            'tracking_map_url': reverse('admin:main_tracking_map'),
        })
        return context
    
    # Apply the monkey patches
    admin_site.get_urls = get_urls
    admin_site.each_context = each_context
    
    return admin_site
