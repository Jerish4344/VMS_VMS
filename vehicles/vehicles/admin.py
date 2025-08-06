# Update your existing vehicles/admin.py

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib import messages
from django.urls import path, reverse
from django.utils.html import format_html
from .models import VehicleType, Vehicle
from trips.models import Trip

@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'vehicle_count', 'description']
    list_filter = ['category']
    search_fields = ['name', 'description']
    ordering = ['category', 'name']
    
    def vehicle_count(self, obj):
        return obj.vehicle_count()
    vehicle_count.short_description = 'Vehicle Count'

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = [
        'license_plate', 'make', 'model', 'vehicle_type', 
        'year', 'status', 'fuel_or_electric', 'capacity_display',
        'rate_per_km', 'current_odometer', 'odometer_actions'  # Added rate_per_km
    ]
    list_filter = [
        'status', 'vehicle_type', 'vehicle_type__category', 
        'year', 'fuel_type', 'company_owned'
    ]
    search_fields = [
        'license_plate', 'make', 'model', 'vin', 
        'owner_name', 'assigned_driver'
    ]
    ordering = ['license_plate']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'vehicle_type', 'make', 'model', 'year', 
                'license_plate', 'vin', 'color'
            )
        }),
        ('Capacity', {
            'fields': ('seating_capacity', 'load_capacity_kg'),
            'description': 'Load capacity is required for commercial vehicles'
        }),
        ('Fuel/Energy Information', {
            'fields': (
                'fuel_type', 'fuel_capacity', 'average_mileage',
                'battery_capacity_kwh', 'charging_type', 
                'range_per_charge', 'charging_time_hours'
            ),
            'description': 'Fill fuel fields for conventional vehicles, battery fields for electric vehicles'
        }),
        ('Status & Usage', {
            'fields': (
                'status', 'current_odometer', 'acquisition_date',
                'purpose_of_vehicle', 'company_owned', 'usage_type', 'used_by'
            )
        }),
        ('Pricing', {
            'fields': ('rate_per_km',),
            'description': 'Set the rate per kilometer for this vehicle'
        }),
        ('Documents & Registration', {
            'fields': (
                'owner_name', 'rc_valid_till', 'insurance_expiry_date',
                'fitness_expiry', 'permit_expiry', 'pollution_cert_expiry'
            )
        }),
        ('GPS & Driver', {
            'fields': (
                'gps_fitted', 'gps_name', 
                'driver_contact', 'assigned_driver'
            )
        }),
        ('Additional', {
            'fields': ('image', 'notes'),
            'classes': ('collapse',)
        })
    )
    
    def fuel_or_electric(self, obj):
        if obj.is_electric():
            return f"Electric ({obj.battery_capacity_kwh} kWh)" if obj.battery_capacity_kwh else "Electric"
        else:
            return f"{obj.fuel_type} ({obj.fuel_capacity}L)" if obj.fuel_capacity else obj.fuel_type
    fuel_or_electric.short_description = 'Fuel/Energy'
    
    def capacity_display(self, obj):
        parts = [f"{obj.seating_capacity} seats"]
        if obj.is_commercial() and obj.load_capacity_kg:
            parts.append(f"{obj.load_capacity_kg} kg")
        return " | ".join(parts)
    capacity_display.short_description = 'Capacity'
    
    def odometer_actions(self, obj):
        """Add quick action buttons for odometer management."""
        return format_html(
            '<a class="button" href="{}">Update</a>&nbsp;'
            '<span style="color: #666;">({} km)</span>',
            reverse('admin:update_vehicle_odometer', args=[obj.pk]),
            obj.current_odometer or 'Not set'
        )
    odometer_actions.short_description = 'Odometer'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for conditional fields
        if 'vehicle_type' in form.base_fields:
            form.base_fields['vehicle_type'].help_text = (
                "Select vehicle type. This determines which additional fields are required."
            )
        
        # Add help text for current_odometer
        if 'current_odometer' in form.base_fields:
            form.base_fields['current_odometer'].help_text = (
                "Current odometer reading. This will be automatically updated when trips are completed. "
                "You can also use the 'Update Odometer' action for manual adjustments."
            )
        
        return form
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:vehicle_id>/update-odometer/',
                self.admin_site.admin_view(self.update_odometer_view),
                name='update_vehicle_odometer',
            ),
        ]
        return custom_urls + urls
    
    def update_odometer_view(self, request, vehicle_id):
        """Custom view to update vehicle odometer."""
        vehicle = self.get_object(request, vehicle_id)
        if vehicle is None:
            messages.error(request, 'Vehicle not found.')
            return HttpResponseRedirect(reverse('admin:vehicles_vehicle_changelist'))
        
        # Get latest trips for reference
        latest_trips = Trip.objects.filter(
            vehicle=vehicle,
            status='completed',
            end_odometer__isnull=False
        ).order_by('-end_time')[:5]
        
        # Get highest odometer reading
        highest_trip = Trip.objects.filter(
            vehicle=vehicle,
            status='completed',
            end_odometer__isnull=False
        ).order_by('-end_odometer').first()
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'set_manual':
                try:
                    new_odometer = int(request.POST.get('manual_odometer', 0))
                    if new_odometer >= 0:
                        old_odometer = vehicle.current_odometer
                        vehicle.current_odometer = new_odometer
                        vehicle.save()
                        
                        messages.success(
                            request,
                            f'Vehicle {vehicle.license_plate} odometer updated from {old_odometer} to {new_odometer} km'
                        )
                    else:
                        messages.error(request, 'Odometer reading cannot be negative.')
                except (ValueError, TypeError):
                    messages.error(request, 'Please enter a valid odometer reading.')
            
            elif action == 'set_latest':
                if latest_trips:
                    latest_trip = latest_trips[0]
                    old_odometer = vehicle.current_odometer
                    vehicle.current_odometer = latest_trip.end_odometer
                    vehicle.save()
                    
                    messages.success(
                        request,
                        f'Vehicle {vehicle.license_plate} odometer updated to latest trip reading: {latest_trip.end_odometer} km'
                    )
                else:
                    messages.error(request, 'No completed trips found for this vehicle.')
            
            elif action == 'set_highest':
                if highest_trip:
                    old_odometer = vehicle.current_odometer
                    vehicle.current_odometer = highest_trip.end_odometer
                    vehicle.save()
                    
                    messages.success(
                        request,
                        f'Vehicle {vehicle.license_plate} odometer updated to highest reading: {highest_trip.end_odometer} km'
                    )
                else:
                    messages.error(request, 'No completed trips found for this vehicle.')
            
            return HttpResponseRedirect(reverse('admin:vehicles_vehicle_changelist'))
        
        context = {
            'vehicle': vehicle,
            'latest_trips': latest_trips,
            'highest_trip': highest_trip,
            'title': f'Update Odometer - {vehicle.license_plate}',
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request, vehicle),
            'has_change_permission': self.has_change_permission(request, vehicle),
        }
        
        return render(request, 'admin/vehicles/update_odometer.html', context)