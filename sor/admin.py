from django.contrib import admin
from .models import SOR

@admin.register(SOR)
class SORAdmin(admin.ModelAdmin):
    list_display = ('id', 'goods_value', 'from_location', 'to_location', 'vehicle', 'driver', 'status', 'created_at')
    list_filter = ('status', 'vehicle', 'driver')
    search_fields = ('from_location', 'to_location', 'vehicle__license_plate', 'driver__username')
