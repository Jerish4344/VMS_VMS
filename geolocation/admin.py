from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
from django.contrib.admin import SimpleListFilter
import csv
from datetime import timedelta
import logging

from .models import AiroTrackDevice, VehicleLocation, LocationHistory
from .airotrack_service import AiroTrackAPI

# Configure logging
logger = logging.getLogger(__name__)

# ========== Custom LIST FILTERS ==========

class VehicleAssignmentFilter(SimpleListFilter):
    """
    Filter for distinguishing between devices that are assigned to a vehicle
    and those that are not.
    """
    title = "Vehicle assignment"
    parameter_name = "assignment"

    def lookups(self, request, model_admin):
        return (
            ("assigned", "Assigned"),
            ("unassigned", "Unassigned"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "assigned":
            return queryset.filter(vehicle__isnull=False)
        if value == "unassigned":
            return queryset.filter(vehicle__isnull=True)
        return queryset

# Custom admin actions
@admin.action(description="Sync selected devices with AiroTrack API")
def sync_with_api(modeladmin, request, queryset):
    """Sync selected devices with the AiroTrack API"""
    api_service = AiroTrackAPI()
    success_count = 0
    error_count = 0
    
    for device in queryset:
        try:
            # Get device info from API
            device_info = api_service.get_device_info(device.device_id)
            
            if not device_info:
                error_count += 1
                continue
                
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
            
            success_count += 1
                
        except Exception as e:
            logger.error(f"Error syncing device {device.device_id}: {str(e)}")
            error_count += 1
    
    modeladmin.message_user(
        request, 
        f"Synced {success_count} devices successfully. {error_count} devices failed.",
        messages.SUCCESS if error_count == 0 else messages.WARNING
    )

@admin.action(description="Mark selected devices as online")
def mark_as_online(modeladmin, request, queryset):
    """Mark selected devices as online"""
    queryset.update(status='online', last_update=timezone.now())
    modeladmin.message_user(request, f"Marked {queryset.count()} devices as online.", messages.SUCCESS)

@admin.action(description="Mark selected devices as offline")
def mark_as_offline(modeladmin, request, queryset):
    """Mark selected devices as offline"""
    queryset.update(status='offline', last_update=timezone.now())
    modeladmin.message_user(request, f"Marked {queryset.count()} devices as offline.", messages.SUCCESS)

@admin.action(description="Export selected history to CSV")
def export_history_to_csv(modeladmin, request, queryset):
    """Export selected location history to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="location_history.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Vehicle', 'Device ID', 'Date/Time', 'Latitude', 'Longitude', 
        'Speed (km/h)', 'Course', 'Altitude', 'Ignition', 'Address'
    ])
    
    for record in queryset.select_related('vehicle', 'device'):
        writer.writerow([
            record.vehicle.license_plate if record.vehicle else 'N/A',
            record.device.device_id if record.device else 'N/A',
            record.device_time.strftime('%Y-%m-%d %H:%M:%S'),
            float(record.latitude),
            float(record.longitude),
            float(record.speed) if record.speed else 0,
            float(record.course) if record.course else '',
            float(record.altitude) if record.altitude else '',
            'On' if record.ignition else 'Off',
            record.address or ''
        ])
    
    return response

@admin.action(description="Delete history older than 30 days")
def delete_old_history(modeladmin, request, queryset):
    """Delete location history older than 30 days"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    old_records = queryset.filter(device_time__lt=thirty_days_ago)
    count = old_records.count()
    old_records.delete()
    
    modeladmin.message_user(
        request, 
        f"Deleted {count} history records older than 30 days.",
        messages.SUCCESS
    )

@admin.action(description="Refresh location data")
def refresh_location_data(modeladmin, request, queryset):
    """Refresh location data for selected vehicles"""
    api_service = AiroTrackAPI()
    success_count = 0
    error_count = 0
    
    for location in queryset:
        try:
            if not location.device:
                error_count += 1
                continue
                
            # Get fresh position data
            positions = api_service.get_positions(device_ids=[location.device.device_id])
            
            if positions and len(positions) > 0:
                # Process the latest position
                position_data = api_service._parse_position_data(positions[0])
                
                if position_data:
                    # Update location
                    location.latitude = position_data['latitude']
                    location.longitude = position_data['longitude']
                    location.altitude = position_data['altitude']
                    location.speed = position_data['speed']
                    location.course = position_data['course']
                    location.device_time = position_data['device_time']
                    location.server_time = position_data['server_time']
                    location.fix_time = position_data['fix_time']
                    location.valid = position_data['valid']
                    location.address = position_data['address']
                    location.ignition = position_data['ignition']
                    location.battery_level = position_data.get('battery_level')
                    location.raw_data = position_data['raw_data']
                    location.save()
                    
                    # Create history entry
                    LocationHistory.objects.create(
                        vehicle=location.vehicle,
                        device=location.device,
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
                    
                    success_count += 1
                else:
                    error_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            logger.error(f"Error refreshing location for {location.vehicle}: {str(e)}")
            error_count += 1
    
    modeladmin.message_user(
        request, 
        f"Refreshed {success_count} locations successfully. {error_count} locations failed.",
        messages.SUCCESS if error_count == 0 else messages.WARNING
    )


class AiroTrackDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'name', 'formatted_status', 'vehicle_display', 'formatted_last_update')
    # Use custom filter for assignment status instead of invalid 'vehicle__isnull'
    list_filter = ('status', 'last_update', VehicleAssignmentFilter)
    search_fields = ('device_id', 'name', 'vehicle__license_plate')
    raw_id_fields = ('vehicle',)
    actions = [sync_with_api, mark_as_online, mark_as_offline]
    list_per_page = 50
    
    fieldsets = (
        ('Device Information', {
            'fields': ('device_id', 'name', 'status')
        }),
        ('Vehicle Assignment', {
            'fields': ('vehicle',)
        }),
        ('Settings', {
            'fields': ('update_interval', 'speed_limit', 'speed_alert', 'geofence_alert', 'ignition_alert'),
            'classes': ('collapse',),
        }),
        ('Status Information', {
            'fields': ('last_update',),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        """Optimize query with select_related"""
        return super().get_queryset(request).select_related('vehicle')
    
    def vehicle_display(self, obj):
        """Display vehicle with link if assigned"""
        if obj.vehicle:
            url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.id])
            return format_html('<a href="{}">{}</a>', url, obj.vehicle.license_plate)
        return format_html('<span class="text-muted">Not assigned</span>')
    vehicle_display.short_description = 'Vehicle'
    vehicle_display.admin_order_field = 'vehicle__license_plate'
    
    def formatted_status(self, obj):
        """Format status with color and icon"""
        status_colors = {
            'online': 'green',
            'offline': 'orange',
            'inactive': 'gray',
            'unknown': 'gray'
        }
        status_icons = {
            'online': '●',
            'offline': '○',
            'inactive': '◌',
            'unknown': '?'
        }
        color = status_colors.get(obj.status, 'gray')
        icon = status_icons.get(obj.status, '?')
        return format_html('<span style="color: {};">{} {}</span>', color, icon, obj.get_status_display())
    formatted_status.short_description = 'Status'
    formatted_status.admin_order_field = 'status'
    
    def formatted_last_update(self, obj):
        """Format last update time with relative time"""
        if not obj.last_update:
            return format_html('<span class="text-muted">Never</span>')
            
        time_diff = timezone.now() - obj.last_update
        minutes = int(time_diff.total_seconds() / 60)
        
        if minutes < 60:
            return format_html('<span style="color: green;">{} minutes ago</span>', minutes)
        elif minutes < 24 * 60:
            hours = minutes // 60
            return format_html('<span style="color: orange;">{} hours ago</span>', hours)
        else:
            days = minutes // (24 * 60)
            return format_html('<span style="color: red;">{} days ago</span>', days)
    formatted_last_update.short_description = 'Last Update'
    formatted_last_update.admin_order_field = 'last_update'


class VehicleLocationAdmin(admin.ModelAdmin):
    list_display = ('vehicle_display', 'device_display', 'coordinates_display', 'speed_display', 'formatted_device_time', 'status_display', 'map_link')
    list_filter = (
        'device_time',
        'ignition',
        ('speed', admin.EmptyFieldListFilter),
    )
    search_fields = ('vehicle__license_plate', 'address')
    readonly_fields = ('latitude', 'longitude', 'altitude', 'speed', 'course', 'device_time', 'server_time', 'fix_time', 'valid', 'address', 'raw_data')
    raw_id_fields = ('vehicle', 'device')
    actions = [refresh_location_data]
    list_per_page = 50
    
    fieldsets = (
        ('Vehicle & Device', {
            'fields': ('vehicle', 'device')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'altitude', 'address')
        }),
        ('Movement', {
            'fields': ('speed', 'course', 'ignition')
        }),
        ('Timing', {
            'fields': ('device_time', 'server_time', 'fix_time')
        }),
        ('Status', {
            'fields': ('valid', 'battery_level', 'signal_strength')
        }),
        ('Raw Data', {
            'fields': ('raw_data',),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        """Optimize query with select_related"""
        return super().get_queryset(request).select_related('vehicle', 'device')
    
    def vehicle_display(self, obj):
        """Display vehicle with link"""
        if obj.vehicle:
            url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.id])
            return format_html('<a href="{}">{}</a>', url, obj.vehicle.license_plate)
        return 'N/A'
    vehicle_display.short_description = 'Vehicle'
    vehicle_display.admin_order_field = 'vehicle__license_plate'
    
    def device_display(self, obj):
        """Display device with link"""
        if obj.device:
            url = reverse('admin:geolocation_airotrackdevice_change', args=[obj.device.id])
            return format_html('<a href="{}">{}</a>', url, obj.device.name or obj.device.device_id)
        return 'N/A'
    device_display.short_description = 'Device'
    device_display.admin_order_field = 'device__name'
    
    def coordinates_display(self, obj):
        """Display coordinates in a compact format"""
        if obj.latitude is None or obj.longitude is None:
            return 'N/A'
        lat = float(obj.latitude) if obj.latitude else 0
        lng = float(obj.longitude) if obj.longitude else 0
        return format_html('{}, {}', round(lat, 6), round(lng, 6))
    coordinates_display.short_description = 'Coordinates'
    
    def speed_display(self, obj):
        """Display speed with color coding"""
        if obj.speed is None:
            return format_html('<span class="text-muted">N/A</span>')
            
        try:
            speed = float(obj.speed)
            if speed == 0:
                return format_html('<span style="color: gray;">0 km/h</span>')
            elif speed < 20:
                return format_html('<span style="color: green;">{} km/h</span>', round(speed, 1))
            elif speed < 60:
                return format_html('<span style="color: orange;">{} km/h</span>', round(speed, 1))
            else:
                return format_html('<span style="color: red;">{} km/h</span>', round(speed, 1))
        except (ValueError, TypeError):
            return format_html('<span class="text-muted">Invalid</span>')
    speed_display.short_description = 'Speed'
    speed_display.admin_order_field = 'speed'
    
    def formatted_device_time(self, obj):
        """Format device time with relative time"""
        if not obj.device_time:
            return format_html('<span class="text-muted">Unknown</span>')
            
        time_diff = timezone.now() - obj.device_time
        minutes = int(time_diff.total_seconds() / 60)
        
        if minutes < 60:
            return format_html('<span style="color: green;">{} minutes ago</span>', minutes)
        elif minutes < 24 * 60:
            hours = minutes // 60
            return format_html('<span style="color: orange;">{} hours ago</span>', hours)
        else:
            days = minutes // (24 * 60)
            return format_html('<span style="color: red;">{} days ago</span>', days)
    formatted_device_time.short_description = 'Last Update'
    formatted_device_time.admin_order_field = 'device_time'
    
    def status_display(self, obj):
        """Display status based on speed and ignition"""
        if not obj.device_time or (timezone.now() - obj.device_time) > timedelta(minutes=60):
            return format_html('<span style="color: gray;">Unknown</span>')
            
        try:
            speed = float(obj.speed) if obj.speed is not None else 0
            
            if speed > 5:
                return format_html('<span style="color: green;">Active</span>')
            elif obj.ignition:
                return format_html('<span style="color: #17a2b8;">Idle</span>')
            else:
                return format_html('<span style="color: orange;">Parked</span>')
        except (ValueError, TypeError):
            return format_html('<span style="color: gray;">Unknown</span>')
    status_display.short_description = 'Status'
    
    def map_link(self, obj):
        """Display a link to view the location on Google Maps"""
        if obj.latitude and obj.longitude:
            try:
                lat = float(obj.latitude)
                lng = float(obj.longitude)
                url = f"https://www.google.com/maps?q={lat},{lng}"
                return format_html('<a href="{}" target="_blank" class="button">View on Map</a>', url)
            except (ValueError, TypeError):
                return 'Invalid coordinates'
        return 'N/A'
    map_link.short_description = 'Map'


class LocationHistoryAdmin(admin.ModelAdmin):
    list_display = ('vehicle_display', 'device_display', 'formatted_device_time', 'coordinates_display', 'speed_display', 'ignition_display')
    list_filter = (
        'device_time',
        'ignition',
        'device',
        ('speed', admin.EmptyFieldListFilter),
    )
    # NOTE:
    # ------------------------------------------------------------------
    # The `date_hierarchy` feature triggers a DB-level `DATE_TRUNC`
    # query which, on some MySQL/MariaDB installations, fails if the
    # server’s time-zone tables are missing.  This manifests as:
    #    “Database returned an invalid datetime value. Are time zone
    #     definitions for your database installed?”
    #
    # To keep the admin usable in environments where the TZ tables are
    # not present, we temporarily disable the hierarchy.  All other
    # functionality (filters, search, export, etc.) remains unaffected.
    #
    # If/when the DB is patched with proper time-zone info, simply
    # re-enable the next line.
    # date_hierarchy = 'device_time'
    search_fields = ('vehicle__license_plate', 'address')
    readonly_fields = ('vehicle', 'device', 'latitude', 'longitude', 'altitude', 'speed', 'course', 'device_time', 'valid', 'address', 'ignition')
    actions = [export_history_to_csv, delete_old_history]
    list_per_page = 100
    
    fieldsets = (
        ('Vehicle & Device', {
            'fields': ('vehicle', 'device')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'altitude', 'address')
        }),
        ('Movement', {
            'fields': ('speed', 'course', 'ignition')
        }),
        ('Timing', {
            'fields': ('device_time',)
        }),
        ('Status', {
            'fields': ('valid',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize query with select_related"""
        return super().get_queryset(request).select_related('vehicle', 'device')
    
    def vehicle_display(self, obj):
        """Display vehicle with link"""
        if obj.vehicle:
            url = reverse('admin:vehicles_vehicle_change', args=[obj.vehicle.id])
            return format_html('<a href="{}">{}</a>', url, obj.vehicle.license_plate)
        return 'N/A'
    vehicle_display.short_description = 'Vehicle'
    vehicle_display.admin_order_field = 'vehicle__license_plate'
    
    def device_display(self, obj):
        """Display device with link"""
        if obj.device:
            url = reverse('admin:geolocation_airotrackdevice_change', args=[obj.device.id])
            return format_html('<a href="{}">{}</a>', url, obj.device.name or obj.device.device_id)
        return 'N/A'
    device_display.short_description = 'Device'
    device_display.admin_order_field = 'device__name'
    
    def coordinates_display(self, obj):
        """Display coordinates in a compact format with map link"""
        if obj.latitude is None or obj.longitude is None:
            return 'N/A'
        
        try:
            lat = float(obj.latitude)
            lng = float(obj.longitude)
            url = f"https://www.google.com/maps?q={lat},{lng}"
            coords = f"{round(lat, 6)}, {round(lng, 6)}"
            return format_html('<a href="{}" target="_blank" title="View on map">{}</a>', url, coords)
        except (ValueError, TypeError):
            return 'Invalid coordinates'
    coordinates_display.short_description = 'Coordinates'
    
    def speed_display(self, obj):
        """Display speed with color coding"""
        if obj.speed is None:
            return format_html('<span class="text-muted">N/A</span>')
            
        try:
            speed = float(obj.speed)
            if speed == 0:
                return format_html('<span style="color: gray;">0 km/h</span>')
            elif speed < 20:
                return format_html('<span style="color: green;">{} km/h</span>', round(speed, 1))
            elif speed < 60:
                return format_html('<span style="color: orange;">{} km/h</span>', round(speed, 1))
            else:
                return format_html('<span style="color: red;">{} km/h</span>', round(speed, 1))
        except (ValueError, TypeError):
            return format_html('<span class="text-muted">Invalid</span>')
    speed_display.short_description = 'Speed'
    speed_display.admin_order_field = 'speed'
    
    def formatted_device_time(self, obj):
        """Format device time"""
        if not obj.device_time:
            return format_html('<span class="text-muted">Unknown</span>')
        return obj.device_time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_device_time.short_description = 'Time'
    formatted_device_time.admin_order_field = 'device_time'
    
    def ignition_display(self, obj):
        """Display ignition status with icon"""
        if obj.ignition:
            return format_html('<span style="color: green;">●</span>')
        else:
            return format_html('<span style="color: gray;">○</span>')
    ignition_display.short_description = 'Ignition'
    ignition_display.admin_order_field = 'ignition'
    
    def has_add_permission(self, request):
        """Disable adding new history records manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing history records"""
        return False


# Register models with custom admin classes
admin.site.register(AiroTrackDevice, AiroTrackDeviceAdmin)
admin.site.register(VehicleLocation, VehicleLocationAdmin)
admin.site.register(LocationHistory, LocationHistoryAdmin)
