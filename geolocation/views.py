from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.core.paginator import Paginator
from django.conf import settings
from datetime import datetime, timedelta
import json
import logging
import csv

from .models import AiroTrackDevice, VehicleLocation, LocationHistory
from vehicles.models import Vehicle
from .airotrack_service import AiroTrackAPI
from .forms import AiroTrackDeviceForm, VehicleAssignmentForm, DateRangeForm, AiroTrackSettingsForm

# Configure logging
logger = logging.getLogger(__name__)

# ===== Helper Functions =====

def has_tracking_permission(user):
    """Check if user has permission to view tracking data"""
    return user.is_authenticated and (
        user.is_staff or 
        user.is_superuser or 
        getattr(user, 'user_type', '') in ['admin', 'vehicle_manager', 'manager', 'driver']
    )

def has_admin_permission(user):
    """Check if user has admin permission for tracking system"""
    return user.is_authenticated and (
        user.is_staff or 
        user.is_superuser or 
        getattr(user, 'user_type', '') in ['admin', 'vehicle_manager', 'manager']
    )

def get_vehicle_status(vehicle):
    """Get the current status of a vehicle based on its location data"""
    try:
        location = VehicleLocation.objects.get(vehicle=vehicle)
        
        # Check if location is stale (older than 60 minutes instead of 10)
        is_stale = (timezone.now() - location.device_time) > timedelta(minutes=60)
        
        if is_stale:
            status = "unknown"
            status_display = "Unknown"
            status_class = "text-secondary"
        else:
            # Get speed as float, defaulting to 0 if None or invalid
            try:
                speed = float(location.speed) if location.speed is not None else 0
            except (ValueError, TypeError):
                speed = 0
            
            if speed > 5:
                # Active if speed > 5 km/h (moving)
                status = "active"
                status_display = "Active"
                status_class = "text-success"
            elif location.ignition:
                # Idle if speed <= 5 km/h but ignition is on
                status = "idle"
                status_display = "Idle"
                status_class = "text-info"
            else:
                # Parked if speed <= 5 km/h AND ignition is off/None
                status = "inactive"
                status_display = "Parked"
                status_class = "text-warning"
    except VehicleLocation.DoesNotExist:
        status = "no_data"
        status_display = "No Data"
        status_class = "text-danger"
    
    return {
        "status": status,
        "display": status_display,
        "class": status_class
    }

# ===== Main Views =====

@login_required
def tracking_dashboard(request):
    """
    Main dashboard for vehicle tracking.
    
    Shows all vehicles with their current status and location on a map.
    """
    if not has_tracking_permission(request.user):
        messages.error(request, "You don't have permission to access the tracking system.")
        return redirect('dashboard')
    
    # Get all vehicles with tracking devices
    vehicles_with_devices = Vehicle.objects.filter(airotrack_device__isnull=False)
    
    # Get status for each vehicle
    vehicles_data = []
    for vehicle in vehicles_with_devices:
        status = get_vehicle_status(vehicle)
        
        try:
            location = VehicleLocation.objects.get(vehicle=vehicle)
            location_data = {
                "latitude": float(location.latitude),
                "longitude": float(location.longitude),
                "speed": float(location.speed) if location.speed else 0,
                "last_update": location.device_time,
                "address": location.address or "Unknown location"
            }
        except VehicleLocation.DoesNotExist:
            location_data = None
        
        vehicles_data.append({
            "vehicle": vehicle,
            "status": status,
            "location": location_data
        })
    
    # Get counts for dashboard stats
    total_vehicles = vehicles_with_devices.count()
    active_vehicles = sum(1 for v in vehicles_data if v["status"]["status"] == "active")
    idle_vehicles = sum(1 for v in vehicles_data if v["status"]["status"] == "idle")
    inactive_vehicles = sum(1 for v in vehicles_data if v["status"]["status"] == "inactive")
    unknown_vehicles = sum(1 for v in vehicles_data if v["status"]["status"] in ["unknown", "no_data"])
    
    # Get last sync time
    try:
        last_sync = AiroTrackDevice.objects.latest('last_update').last_update
    except (AiroTrackDevice.DoesNotExist, AttributeError):
        last_sync = None
    
    context = {
        'vehicles_data': vehicles_data,
        'total_vehicles': total_vehicles,
        'active_vehicles': active_vehicles,
        'idle_vehicles': idle_vehicles,
        'inactive_vehicles': inactive_vehicles,
        'unknown_vehicles': unknown_vehicles,
        'last_sync': last_sync,
        'page_title': 'Vehicle Tracking Dashboard',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/tracking_dashboard.html', context)

@login_required
def vehicle_tracking_detail(request, vehicle_id):
    """
    Detailed tracking view for a specific vehicle.
    
    Shows current location, status, and recent history.
    """
    if not has_tracking_permission(request.user):
        messages.error(request, "You don't have permission to access the tracking system.")
        return redirect('dashboard')
    
    # Get vehicle and check if it exists
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    
    # Check if vehicle has a tracking device
    try:
        device = AiroTrackDevice.objects.get(vehicle=vehicle)
    except AiroTrackDevice.DoesNotExist:
        messages.warning(request, f"Vehicle {vehicle.license_plate} does not have a tracking device installed.")
        return redirect('tracking_dashboard')
    
    # Get current location and status
    status = get_vehicle_status(vehicle)
    
    try:
        location = VehicleLocation.objects.get(vehicle=vehicle)
        
        # Format for display
        location_data = {
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
            "speed": float(location.speed) if location.speed else 0,
            "course": float(location.course) if location.course else 0,
            "altitude": float(location.altitude) if location.altitude else 0,
            "last_update": location.device_time,
            "address": location.address or "Unknown location",
            "ignition": location.ignition,
            "battery_level": float(location.battery_level) if location.battery_level else None,
            "signal_strength": location.signal_strength
        }
    except VehicleLocation.DoesNotExist:
        location_data = None
    
    # Get recent history (last 24 hours)
    end_time = timezone.now()
    start_time = end_time - timedelta(hours=24)
    
    # First, get max speed from a separate query before slicing
    max_speed_obj = LocationHistory.objects.filter(
        vehicle=vehicle,
        device_time__gte=start_time,
        device_time__lte=end_time
    ).order_by('-speed').first()
    
    max_speed = float(max_speed_obj.speed) if max_speed_obj and max_speed_obj.speed else 0
    
    # Now get history with limit for display
    history = LocationHistory.objects.filter(
        vehicle=vehicle,
        device_time__gte=start_time,
        device_time__lte=end_time
    ).order_by('-device_time')[:100]  # Limit to 100 points for performance
    
    # Calculate remaining stats from the limited history queryset
    if history.exists():
        # Convert to list to work with the sliced queryset
        history_list = list(history)
        avg_speed = sum(float(h.speed or 0) for h in history_list) / len(history_list)
        distance = 0  # Would need to calculate based on coordinates
        
        # Get first and last positions from the list
        first_position = history_list[-1] if history_list else None
        last_position = history_list[0] if history_list else None
    else:
        avg_speed = distance = 0
        first_position = last_position = None
    
    context = {
        'vehicle': vehicle,
        'device': device,
        'status': status,
        'location': location_data,
        'history': history,
        'max_speed': max_speed,
        'avg_speed': avg_speed,
        'distance': distance,
        'first_position': first_position,
        'last_position': last_position,
        'start_time': start_time,
        'end_time': end_time,
        'page_title': f'Tracking: {vehicle.license_plate}',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/vehicle_tracking_detail.html', context)

@login_required
def vehicle_tracking_history(request, vehicle_id):
    """
    Historical tracking data for a specific vehicle.
    
    Shows routes and stops over a selected time period.
    """
    if not has_tracking_permission(request.user):
        messages.error(request, "You don't have permission to access the tracking system.")
        return redirect('dashboard')
    
    # Get vehicle and check if it exists
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    
    # Check if vehicle has a tracking device
    try:
        device = AiroTrackDevice.objects.get(vehicle=vehicle)
    except AiroTrackDevice.DoesNotExist:
        messages.warning(request, f"Vehicle {vehicle.license_plate} does not have a tracking device installed.")
        return redirect('tracking_dashboard')
    
    # Get date range from request parameters or use defaults
    end_date = request.GET.get('end_date')
    start_date = request.GET.get('start_date')
    
    if end_date:
        try:
            end_time = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            end_time = timezone.make_aware(end_time)
        except ValueError:
            end_time = timezone.now()
    else:
        end_time = timezone.now()
    
    if start_date:
        try:
            start_time = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            start_time = timezone.make_aware(start_time)
        except ValueError:
            start_time = end_time - timedelta(days=1)
    else:
        start_time = end_time - timedelta(days=1)
    
    # Get history data for the selected period
    history = LocationHistory.objects.filter(
        vehicle=vehicle,
        device_time__gte=start_time,
        device_time__lte=end_time
    ).order_by('device_time')
    
    # If no data in database, try to fetch from API
    if history.count() < 10:
        try:
            api_service = AiroTrackAPI()
            api_service.get_vehicle_history(vehicle, start_time, end_time)
            
            # Refresh query after API fetch
            history = LocationHistory.objects.filter(
                vehicle=vehicle,
                device_time__gte=start_time,
                device_time__lte=end_time
            ).order_by('device_time')
        except Exception as e:
            logger.error(f"Error fetching history from API: {str(e)}")
            messages.warning(request, "Could not fetch additional history data from AiroTrack API.")
    
    # Calculate stats
    if history.exists():
        max_speed = history.order_by('-speed').first().speed
        avg_speed = sum(h.speed or 0 for h in history) / history.count() if history.count() > 0 else 0
        
        # Identify stops (periods of no movement)
        stops = []
        current_stop = None
        
        for point in history:
            if point.speed is None or float(point.speed) < 2:  # Less than 2 km/h considered stopped
                if current_stop is None:
                    current_stop = {
                        'start_time': point.device_time,
                        'end_time': point.device_time,
                        'latitude': point.latitude,
                        'longitude': point.longitude,
                        'address': point.address or "Unknown location"
                    }
                else:
                    current_stop['end_time'] = point.device_time
            else:
                if current_stop is not None:
                    # Only count stops longer than 5 minutes
                    duration = current_stop['end_time'] - current_stop['start_time']
                    if duration.total_seconds() > 300:
                        current_stop['duration'] = duration
                        stops.append(current_stop)
                    current_stop = None
        
        # Add the last stop if there is one
        if current_stop is not None:
            duration = current_stop['end_time'] - current_stop['start_time']
            if duration.total_seconds() > 300:
                current_stop['duration'] = duration
                stops.append(current_stop)
    else:
        max_speed = avg_speed = 0
        stops = []
    
    context = {
        'vehicle': vehicle,
        'device': device,
        'history': history,
        'history_count': history.count(),
        'max_speed': max_speed,
        'avg_speed': avg_speed,
        'stops': stops,
        'start_time': start_time,
        'end_time': end_time,
        'start_date': start_time.strftime('%Y-%m-%d'),
        'end_date': end_time.strftime('%Y-%m-%d'),
        'page_title': f'History: {vehicle.license_plate}',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/vehicle_tracking_history.html', context)

@login_required
def map_view(request):
    """
    Interactive map view for tracking vehicles.
    
    Shows all vehicles on a map with real-time updates.
    """
    if not has_tracking_permission(request.user):
        messages.error(request, "You don't have permission to access the tracking system.")
        return redirect('dashboard')
    
    # Get all vehicles with tracking devices
    vehicles = Vehicle.objects.filter(airotrack_device__isnull=False)
    
    context = {
        'vehicles': vehicles,
        'page_title': 'Live Tracking Map',
        'is_tracking_page': True,
        'map_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    }
    
    return render(request, 'geolocation/map_view.html', context)

@login_required
def all_vehicles_map(request):
    """
    Full-screen map view for all vehicles.
    
    Shows all vehicles on a map with minimal UI.
    """
    if not has_tracking_permission(request.user):
        messages.error(request, "You don't have permission to access the tracking system.")
        return redirect('dashboard')
    
    # Get all vehicles with tracking devices
    vehicles = Vehicle.objects.filter(airotrack_device__isnull=False)
    
    context = {
        'vehicles': vehicles,
        'page_title': 'Full Map View',
        'is_tracking_page': True,
        'is_fullscreen': True,
        'map_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    }
    
    return render(request, 'geolocation/fullscreen_map.html', context)

# ===== Device Management =====

@login_required
def device_list(request):
    """
    List all AiroTrack devices.
    
    Shows all devices with their status and assigned vehicles.
    """
    if not has_admin_permission(request.user):
        messages.error(request, "You don't have permission to manage tracking devices.")
        return redirect('dashboard')
    
    # Get all devices
    devices = AiroTrackDevice.objects.all().order_by('name')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        devices = devices.filter(status=status_filter)
    
    # Filter by vehicle assignment
    assigned_filter = request.GET.get('assigned')
    if assigned_filter:
        if assigned_filter == 'yes':
            devices = devices.filter(vehicle__isnull=False)
        elif assigned_filter == 'no':
            devices = devices.filter(vehicle__isnull=True)
    
    # Paginate results
    paginator = Paginator(devices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Count by status
    status_counts = {
        'total': devices.count(),
        'online': devices.filter(status='online').count(),
        'offline': devices.filter(status='offline').count(),
        'inactive': devices.filter(status='inactive').count(),
        'unknown': devices.filter(status='unknown').count(),
        'assigned': devices.filter(vehicle__isnull=False).count(),
        'unassigned': devices.filter(vehicle__isnull=True).count()
    }
    
    context = {
        'devices': page_obj,
        'status_counts': status_counts,
        'status_filter': status_filter,
        'assigned_filter': assigned_filter,
        'page_title': 'AiroTrack Devices',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/device_list.html', context)

@login_required
def device_add(request):
    """
    Add a new AiroTrack device.
    """
    if not has_admin_permission(request.user):
        messages.error(request, "You don't have permission to manage tracking devices.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AiroTrackDeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.status = 'unknown'
            device.last_update = timezone.now()
            device.save()
            
            messages.success(request, f"Device {device.name} added successfully.")
            return redirect('device_list')
    else:
        form = AiroTrackDeviceForm()
    
    context = {
        'form': form,
        'page_title': 'Add AiroTrack Device',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/device_form.html', context)

@login_required
def device_detail(request, device_id):
    """
    View details of a specific AiroTrack device.
    """
    if not has_admin_permission(request.user):
        messages.error(request, "You don't have permission to manage tracking devices.")
        return redirect('dashboard')
    
    device = get_object_or_404(AiroTrackDevice, pk=device_id)
    
    # Get current location if assigned to a vehicle
    current_location = None
    if device.vehicle:
        try:
            # Use .first() to avoid MultipleObjectsReturned if duplicates exist
            current_location = VehicleLocation.objects.filter(device=device).first()
        except VehicleLocation.DoesNotExist:
            pass
    
    # Get unassigned vehicles for quick assignment
    # Show ALL vehicles that do not already have a tracking device,
    # regardless of their current `gps_fitted` flag.  This gives users the
    # flexibility to attach a tracker to any vehicle and subsequently mark it
    # as GPS-enabled once a device is assigned.
    unassigned_vehicles = Vehicle.objects.filter(
        airotrack_device__isnull=True
    ).order_by('license_plate')
    
    # Get location history
    location_history = LocationHistory.objects.filter(device=device).order_by('-device_time')
    
    # Paginate location history
    paginator = Paginator(location_history, 20)
    page_number = request.GET.get('page')
    location_history = paginator.get_page(page_number)
    
    # Prepare history data for chart
    history_data = []
    for location in LocationHistory.objects.filter(
        device=device,
        device_time__gte=timezone.now() - timedelta(days=1)
    ).order_by('device_time')[:48]:  # Limit to 48 points (~ every 30 min for 24h)
        history_data.append({
            'time': location.device_time,
            'speed': float(location.speed) if location.speed else 0
        })
    
    # Create status timeline
    status_timeline = []
    # This would typically come from a status history table or be calculated from location history
    # For now, we'll create some sample data
    if device.last_update:
        status_timeline.append({
            'time': device.last_update,
            'status': device.status,
            'description': f"Device reported status: {device.get_status_display()}"
        })
    
    context = {
        'device': device,
        'current_location': current_location,
        'unassigned_vehicles': unassigned_vehicles,
        'location_history': location_history,
        'history_data': history_data,
        'status_timeline': status_timeline,
        'page_title': f'Device: {device.name or device.device_id}',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/device_detail.html', context)

@login_required
def device_edit(request, device_id):
    """
    Edit an existing AiroTrack device.
    """
    if not has_admin_permission(request.user):
        messages.error(request, "You don't have permission to manage tracking devices.")
        return redirect('dashboard')
    
    device = get_object_or_404(AiroTrackDevice, pk=device_id)
    
    if request.method == 'POST':
        # Check if this is an unassign request
        if 'unassign' in request.POST:
            device.vehicle = None
            device.save()
            messages.success(request, f"Device {device.name or device.device_id} unassigned successfully.")
            return redirect('device_detail', device_id=device.id)
        
        # Check if this is a vehicle assignment request
        if 'vehicle' in request.POST and request.POST['vehicle']:
            try:
                vehicle = Vehicle.objects.get(pk=request.POST['vehicle'])
                device.vehicle = vehicle
                device.save()
                messages.success(request, f"Device assigned to {vehicle.license_plate} successfully.")
                return redirect('device_detail', device_id=device.id)
            except Vehicle.DoesNotExist:
                messages.error(request, "Selected vehicle does not exist.")
        
        # Regular form submission
        form = AiroTrackDeviceForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            messages.success(request, f"Device {device.name or device.device_id} updated successfully.")
            return redirect('device_detail', device_id=device.id)
    else:
        form = AiroTrackDeviceForm(instance=device)
    
    context = {
        'form': form,
        'device': device,
        'page_title': f'Edit Device: {device.name or device.device_id}',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/device_form.html', context)

# ===== Admin Functions =====

@login_required
@require_POST
def sync_airotrack(request):
    """
    Manually trigger synchronization with AiroTrack API.
    """
    if not has_admin_permission(request.user):
        messages.error(request, "You don't have permission to manage tracking system.")
        return redirect('dashboard')
    
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
    
    # Redirect back to referring page
    return redirect(request.META.get('HTTP_REFERER', 'tracking_dashboard'))

@login_required
def airotrack_settings(request):
    """
    Settings page for AiroTrack integration.
    """
    if not has_admin_permission(request.user):
        messages.error(request, "You don't have permission to manage tracking system.")
        return redirect('dashboard')
    
    # Get stats for the dashboard
    device_count = AiroTrackDevice.objects.count()
    vehicle_count = Vehicle.objects.filter(airotrack_device__isnull=False).count()
    location_count = VehicleLocation.objects.count()
    history_count = LocationHistory.objects.count()
    
    # Get last sync time
    try:
        last_sync = AiroTrackDevice.objects.latest('last_update').last_update
    except (AiroTrackDevice.DoesNotExist, AttributeError):
        last_sync = None
    
    context = {
        'device_count': device_count,
        'vehicle_count': vehicle_count,
        'location_count': location_count,
        'history_count': history_count,
        'last_sync': last_sync,
        'api_username': AiroTrackAPI.USERNAME,
        'api_base_url': AiroTrackAPI.BASE_URL,
        'page_title': 'AiroTrack Settings',
        'is_tracking_page': True
    }
    
    return render(request, 'geolocation/airotrack_settings.html', context)

# ===== AJAX Endpoints =====

@login_required
@require_GET
def ajax_vehicle_locations(request):
    """
    AJAX endpoint to get current locations of all vehicles.
    
    Returns GeoJSON format for map display.
    """
    if not has_tracking_permission(request.user):
        return HttpResponseForbidden("Permission denied")
    
    # Get all current locations
    locations = VehicleLocation.objects.select_related('vehicle', 'device').all()
    
    # Convert to GeoJSON
    features = []
    for location in locations:
        # Skip if no valid coordinates
        if not location.latitude or not location.longitude:
            continue
            
        # Get vehicle status - Updated with new logic including idle status
        if (timezone.now() - location.device_time) > timedelta(minutes=60):
            status = "unknown"
        else:
            # Get speed as float, defaulting to 0 if None or invalid
            try:
                speed = float(location.speed) if location.speed is not None else 0
            except (ValueError, TypeError):
                speed = 0
            
            if speed > 5:
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

@login_required
@require_GET
def ajax_vehicle_detail(request, vehicle_id):
    """
    AJAX endpoint to get details of a specific vehicle.
    
    Returns JSON with vehicle details and current location.
    """
    if not has_tracking_permission(request.user):
        return HttpResponseForbidden("Permission denied")
    
    try:
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        
        # Get device info
        try:
            device = AiroTrackDevice.objects.get(vehicle=vehicle)
            device_info = {
                "id": device.id,
                "name": device.name or device.device_id,
                "status": device.status,
                "last_update": device.last_update.isoformat() if device.last_update else None
            }
        except AiroTrackDevice.DoesNotExist:
            device_info = None
        
        # Get location info
        try:
            location = VehicleLocation.objects.get(vehicle=vehicle)
            
            # Check if location is stale - Updated with new logic
            is_stale = (timezone.now() - location.device_time) > timedelta(minutes=60)
            
            if is_stale:
                status = "unknown"
                status_display = "Unknown"
            elif float(location.speed) > 5 or location.ignition:
                status = "active"
                status_display = "Active"
            else:
                status = "inactive"
                status_display = "Parked"
            
            location_info = {
                "latitude": float(location.latitude),
                "longitude": float(location.longitude),
                "speed": float(location.speed) if location.speed else 0,
                "course": float(location.course) if location.course else 0,
                "time": location.device_time.isoformat(),
                "address": location.address or "Unknown location",
                "ignition": location.ignition,
                "status": status,
                "status_display": status_display,
                "is_stale": is_stale
            }
        except VehicleLocation.DoesNotExist:
            location_info = None
            status = "no_data"
            status_display = "No Data"
        
        # Construct response
        response_data = {
            "vehicle": {
                "id": vehicle.id,
                "license_plate": vehicle.license_plate,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year
            },
            "device": device_info,
            "location": location_info,
            "status": status,
            "status_display": status_display
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in ajax_vehicle_detail: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required
@require_POST
def device_settings(request, device_id):
    """
    Handle device settings updates via AJAX/POST.
    
    Accepts JSON with setting name and value to update.
    """
    if not has_admin_permission(request.user):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    try:
        device = get_object_or_404(AiroTrackDevice, pk=device_id)
        
        # Check if this is a JSON request
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            setting = data.get('setting')
            value = data.get('value')
            
            # Update the specified setting
            if setting == 'name':
                device.name = value
            elif setting == 'update_interval':
                device.update_interval = int(value)
            elif setting == 'speed_alert':
                device.speed_alert = bool(value)
            elif setting == 'speed_limit':
                device.speed_limit = float(value)
            elif setting == 'geofence_alert':
                device.geofence_alert = bool(value)
            elif setting == 'ignition_alert':
                device.ignition_alert = bool(value)
            else:
                return JsonResponse({"success": False, "error": f"Unknown setting: {setting}"}, status=400)
            
            device.save()
            return JsonResponse({"success": True})
        
        # Handle form submission
        form = AiroTrackDeviceForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            messages.success(request, f"Device settings updated successfully.")
            return redirect('device_detail', device_id=device.id)
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
            
    except Exception as e:
        logger.error(f"Error updating device settings: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_GET
def device_status(request, device_id):
    """
    Return device status as JSON for AJAX updates.
    """
    if not has_tracking_permission(request.user):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    try:
        device = get_object_or_404(AiroTrackDevice, pk=device_id)
        
        # Get current location if device is assigned to a vehicle
        current_location = None
        if device.vehicle:
            try:
                location = VehicleLocation.objects.get(device=device)
                current_location = {
                    "latitude": float(location.latitude),
                    "longitude": float(location.longitude),
                    "speed": float(location.speed) if location.speed else 0,
                    "course": float(location.course) if location.course else 0,
                    "time": location.device_time.isoformat(),
                    "time_relative": f"{(timezone.now() - location.device_time).total_seconds() // 60:.0f} minutes ago",
                    "address": location.address or "Unknown location",
                    "ignition": location.ignition
                }
            except VehicleLocation.DoesNotExist:
                pass
        
        # Construct response
        response_data = {
            "id": device.id,
            "device_id": device.device_id,
            "name": device.name,
            "status": device.status,
            "status_display": device.get_status_display(),
            "last_update": device.last_update.isoformat() if device.last_update else None,
            "last_update_relative": f"{(timezone.now() - device.last_update).total_seconds() // 60:.0f} minutes ago" if device.last_update else "Never",
            "vehicle_id": device.vehicle.id if device.vehicle else None,
            "vehicle_plate": device.vehicle.license_plate if device.vehicle else None,
            "current_location": current_location
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error fetching device status: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_GET
def device_history_data(request, device_id):
    """
    Return chart data for device history.
    
    Accepts 'period' parameter: day, week, month
    """
    if not has_tracking_permission(request.user):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    try:
        device = get_object_or_404(AiroTrackDevice, pk=device_id)
        
        # Determine time period
        period = request.GET.get('period', 'day')
        end_time = timezone.now()
        
        if period == 'day':
            start_time = end_time - timedelta(days=1)
            interval = 30  # 30 minutes
        elif period == 'week':
            start_time = end_time - timedelta(days=7)
            interval = 180  # 3 hours
        elif period == 'month':
            start_time = end_time - timedelta(days=30)
            interval = 720  # 12 hours
        else:
            return JsonResponse({"success": False, "error": f"Invalid period: {period}"}, status=400)
        
        # Get history data
        history = LocationHistory.objects.filter(
            device=device,
            device_time__gte=start_time,
            device_time__lte=end_time
        ).order_by('device_time')
        
        # Sample data at regular intervals to avoid overwhelming the chart
        sampled_data = []
        if history.exists():
            total_minutes = (end_time - start_time).total_seconds() / 60
            sample_count = min(100, total_minutes / interval)  # Limit to 100 data points
            
            # Simple sampling - take evenly spaced points
            step = max(1, history.count() // sample_count)
            sampled_data = list(history)[::step]
        
        # Format for chart
        labels = [h.device_time.strftime('%H:%M' if period == 'day' else '%m-%d %H:%M') for h in sampled_data]
        speeds = [float(h.speed) if h.speed else 0 for h in sampled_data]
        
        return JsonResponse({
            "success": True,
            "labels": labels,
            "speeds": speeds,
            "period": period,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching device history data: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_POST
def sync_device(request, device_id):
    """
    Sync individual device data with AiroTrack API.
    """
    if not has_admin_permission(request.user):
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    try:
        device = get_object_or_404(AiroTrackDevice, pk=device_id)
        
        # Initialize API service
        api_service = AiroTrackAPI()
        
        # Get device info from API
        device_info = api_service.get_device_info(device.device_id)
        
        if not device_info:
            return JsonResponse({
                "success": False, 
                "error": "Could not retrieve device information from AiroTrack API"
            }, status=404)
        
        # Update device info
        device.status = 'online' if device_info.get('status') == 'online' else 'offline'
        device.last_update = timezone.now()
        device.save()
        
        # Get position data if device is assigned to a vehicle
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
        
        # Handle AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "message": f"Device {device.name or device.device_id} synchronized successfully."
            })
        
        # Handle regular form submission
        messages.success(request, f"Device {device.name or device.device_id} synchronized successfully.")
        return redirect('device_detail', device_id=device.id)
        
    except Exception as e:
        logger.error(f"Error syncing device: {str(e)}")
        
        # Handle AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "error": str(e)}, status=500)
        
        # Handle regular form submission
        messages.error(request, f"Error syncing device: {str(e)}")
        return redirect('device_detail', device_id=device_id)

@login_required
@require_POST
def device_delete(request, device_id):
    """
    Delete a device (admin only).
    """
    if not request.user.is_authenticated or getattr(request.user, 'user_type', '') != 'admin':
        messages.error(request, "Only administrators can delete devices.")
        return redirect('device_list')
    
    try:
        device = get_object_or_404(AiroTrackDevice, pk=device_id)
        device_name = device.name or device.device_id
        
        # Delete the device
        device.delete()
        
        messages.success(request, f"Device {device_name} deleted successfully.")
        return redirect('device_list')
        
    except Exception as e:
        logger.error(f"Error deleting device: {str(e)}")
        messages.error(request, f"Error deleting device: {str(e)}")
        return redirect('device_detail', device_id=device_id)

@login_required
def device_export(request, device_id):
    """
    Export device history as CSV.
    """
    if not has_tracking_permission(request.user):
        messages.error(request, "You don't have permission to access tracking data.")
        return redirect('dashboard')
    
    try:
        device = get_object_or_404(AiroTrackDevice, pk=device_id)
        
        # Get time range from query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if start_date:
            try:
                start_time = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
                start_time = timezone.make_aware(start_time)
            except ValueError:
                start_time = timezone.now() - timedelta(days=7)
        else:
            start_time = timezone.now() - timedelta(days=7)
        
        if end_date:
            try:
                end_time = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                end_time = timezone.make_aware(end_time)
            except ValueError:
                end_time = timezone.now()
        else:
            end_time = timezone.now()
        
        # Get history data
        history = LocationHistory.objects.filter(
            device=device,
            device_time__gte=start_time,
            device_time__lte=end_time
        ).order_by('device_time')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="device_{device.device_id}_history_{start_time.strftime("%Y%m%d")}-{end_time.strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date/Time', 'Latitude', 'Longitude', 'Speed (km/h)', 'Altitude', 
            'Course', 'Ignition', 'Address', 'Valid'
        ])
        
        for record in history:
            writer.writerow([
                record.device_time.strftime('%Y-%m-%d %H:%M:%S'),
                float(record.latitude),
                float(record.longitude),
                float(record.speed) if record.speed else 0,
                float(record.altitude) if record.altitude else '',
                float(record.course) if record.course else '',
                'On' if record.ignition else 'Off',
                record.address or '',
                'Yes' if record.valid else 'No'
            ])
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting device history: {str(e)}")
        messages.error(request, f"Error exporting device history: {str(e)}")
        return redirect('device_detail', device_id=device_id)
