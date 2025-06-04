from django.contrib import admin
from .models import Maintenance, MaintenanceType, MaintenanceProvider

@admin.register(MaintenanceType)
class MaintenanceTypeAdmin(admin.ModelAdmin):
    """Admin configuration for MaintenanceType model."""
    
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(MaintenanceProvider)
class MaintenanceProviderAdmin(admin.ModelAdmin):
    """Admin configuration for MaintenanceProvider model."""
    
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone', 'email')

@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    """Admin configuration for Maintenance model."""
    
    list_display = ('id', 'vehicle', 'maintenance_type', 'date_reported', 'status', 'scheduled_date', 'completion_date')
    list_filter = ('status', 'maintenance_type', 'vehicle')
    search_fields = ('vehicle__license_plate', 'description', 'maintenance_type__name')
    fieldsets = (
        ('Maintenance Details', {
            'fields': ('vehicle', 'maintenance_type', 'provider', 'reported_by')
        }),
        ('Status Information', {
            'fields': ('date_reported', 'status', 'scheduled_date', 'completion_date')
        }),
        ('Technical Details', {
            'fields': ('description', 'odometer_reading', 'cost', 'invoice_image')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )