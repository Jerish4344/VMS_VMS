from django.contrib import admin
from .models import FuelTransaction, FuelStation

@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    """Admin configuration for FuelStation model."""
    
    list_display = ('name', 'address', 'station_type')
    search_fields = ('name', 'address')
    list_filter = ('station_type',)

@admin.register(FuelTransaction)
class FuelTransactionAdmin(admin.ModelAdmin):
    """Admin configuration for FuelTransaction model."""
    
    list_display = (
        'id', 'vehicle', 'driver', 'date', 'fuel_type', 'quantity', 'total_cost', 
        'company_invoice_number', 'station_invoice_number', 'odometer_reading'
    )
    list_filter = ('fuel_type', 'vehicle', 'driver', 'date', 'fuel_station')
    search_fields = (
        'vehicle__license_plate', 'driver__username', 'fuel_station__name',
        'company_invoice_number', 'station_invoice_number'
    )
    readonly_fields = ('total_cost',)
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('vehicle', 'driver', 'fuel_station', 'date')
        }),
        ('Fuel Information', {
            'fields': ('fuel_type', 'quantity', 'cost_per_liter', 'total_cost')
        }),
        ('Electric Vehicle Information', {
            'fields': ('energy_consumed', 'cost_per_kwh', 'charging_duration_minutes'),
            'classes': ('collapse',),
        }),
        ('Finance & Invoice Information', {
            'fields': ('company_invoice_number', 'station_invoice_number'),
            'description': 'Invoice numbers for finance team tracking and reconciliation',
        }),
        ('Vehicle Data', {
            'fields': ('odometer_reading',)
        }),
        ('Documentation', {
            'fields': ('receipt_image', 'notes'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('vehicle', 'driver', 'fuel_station')
    
    def save_model(self, request, obj, form, change):
        """Custom save to ensure proper data handling."""
        # Auto-format invoice numbers
        if obj.company_invoice_number:
            obj.company_invoice_number = obj.company_invoice_number.upper().strip()
        if obj.station_invoice_number:
            obj.station_invoice_number = obj.station_invoice_number.upper().strip()
        
        super().save_model(request, obj, form, change)
