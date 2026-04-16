from django.contrib import admin
from .models import SOR

@admin.register(SOR)
class SORAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_type', 'goods_value', 'from_location', 'to_location', 'vehicle', 'driver', 'outsourced_vehicle_text', 'outsourced_driver_text', 'status', 'created_at')
    list_filter = ('status', 'source_type')
    search_fields = ('from_location', 'to_location', 'vehicle__license_plate', 'driver__username', 'outsourced_vehicle_text', 'outsourced_driver_text', 'vendor_name')
    autocomplete_fields = ('vehicle', 'driver', 'created_by', 'trip')
    readonly_fields = ('created_at', 'updated_at', 'distance_km')
