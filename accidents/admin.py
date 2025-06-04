from django.contrib import admin
from .models import Accident, AccidentImage

class AccidentImageInline(admin.TabularInline):
    """Inline admin for AccidentImage model."""
    model = AccidentImage  # Use the model directly, not the related manager
    extra = 3

@admin.register(AccidentImage)
class AccidentImageAdmin(admin.ModelAdmin):
    """Admin configuration for AccidentImage model."""
    list_display = ('id', 'caption', 'image')
    search_fields = ('caption',)

@admin.register(Accident)
class AccidentAdmin(admin.ModelAdmin):
    """Admin configuration for Accident model."""
    list_display = ('id', 'vehicle', 'driver', 'date_time', 'status', 'third_party_involved', 'injuries')
    list_filter = ('status', 'third_party_involved', 'injuries')
    search_fields = ('vehicle__license_plate', 'driver__username', 'location', 'police_report_number')
    inlines = [AccidentImageInline]
    fieldsets = (
        ('Accident Information', {
            'fields': ('vehicle', 'driver', 'date_time', 'location', 'latitude', 'longitude')
        }),
        ('Accident Details', {
            'fields': ('description', 'damage_description', 'third_party_involved', 'police_report_number')
        }),
        ('Injuries', {
            'fields': ('injuries', 'injuries_description')
        }),
        ('Financial Information', {
            'fields': ('estimated_cost', 'actual_cost', 'insurance_claim_number')
        }),
        ('Status', {
            'fields': ('status', 'resolution_date')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )