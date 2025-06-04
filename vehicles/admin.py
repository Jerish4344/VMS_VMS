from django.contrib import admin
from .models import VehicleType, Vehicle

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
        'year', 'status', 'fuel_or_electric', 'capacity_display'
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
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for conditional fields
        if 'vehicle_type' in form.base_fields:
            form.base_fields['vehicle_type'].help_text = (
                "Select vehicle type. This determines which additional fields are required."
            )
        
        return form