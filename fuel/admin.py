from django.contrib import admin
from .models import FuelTransaction, FuelStation

@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    """Admin configuration for FuelStation model."""
    
    list_display = ('name', 'address')
    search_fields = ('name', 'address')

@admin.register(FuelTransaction)
class FuelTransactionAdmin(admin.ModelAdmin):
    """Admin configuration for FuelTransaction model."""
    
    list_display = ('id', 'vehicle', 'driver', 'date', 'fuel_type', 'quantity', 'total_cost', 'odometer_reading')
    list_filter = ('fuel_type', 'vehicle', 'driver', 'date')
    search_fields = ('vehicle__license_plate', 'driver__username', 'fuel_station__name')
    readonly_fields = ('total_cost',)
    fieldsets = (
        ('Transaction Details', {
            'fields': ('vehicle', 'driver', 'fuel_station', 'date')
        }),
        ('Fuel Information', {
            'fields': ('fuel_type', 'quantity', 'cost_per_liter', 'total_cost')
        }),
        ('Vehicle Data', {
            'fields': ('odometer_reading',)
        }),
        ('Documentation', {
            'fields': ('receipt_image', 'notes'),
            'classes': ('collapse',),
        }),
    )