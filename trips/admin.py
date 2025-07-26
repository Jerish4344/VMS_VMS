from django.contrib import admin

# Import Trip from the main trips.models module
from .models import Trip

# Import ConsultantRate directly from consultant_models to avoid
# relying on re-export behaviour in trips.__init__, which can lead
# to circular-import issues during Django app loading.
from .consultant_models import ConsultantRate

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    """Admin configuration for Trip model."""
    
    list_display = ('id', 'vehicle', 'driver', 'get_route_summary', 'start_time', 'end_time', 'status', 'distance_traveled')
    list_filter = ('status', 'vehicle', 'driver', 'start_time')
    search_fields = ('vehicle__license_plate', 'driver__username', 'purpose', 'origin', 'destination')
    readonly_fields = ('distance_traveled', 'duration', 'get_route_summary')
    
    fieldsets = (
        ('Trip Details', {
            'fields': ('vehicle', 'driver', 'start_time', 'end_time', 'status')
        }),
        ('Route Information', {
            'fields': ('origin', 'destination', 'get_route_summary')
        }),
        ('Odometer Readings', {
            'fields': ('start_odometer', 'end_odometer', 'distance_traveled')
        }),
        ('Additional Information', {
            'fields': ('purpose', 'notes', 'duration'),
        }),
    )
    
    def get_route_summary(self, obj):
        """Display route summary in admin."""
        return obj.get_route_summary()
    get_route_summary.short_description = 'Route'
    
    def distance_traveled(self, obj):
        """Calculate the distance traveled."""
        if obj.end_odometer and obj.start_odometer:
            return f"{obj.end_odometer - obj.start_odometer} km"
        return "In progress"
    
    def duration(self, obj):
        """Calculate the trip duration."""
        if obj.end_time and obj.start_time:
            duration = obj.end_time - obj.start_time
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "In progress"


# ------------------------------------------------------------------
# ConsultantRate admin
# ------------------------------------------------------------------

@admin.register(ConsultantRate)
class ConsultantRateAdmin(admin.ModelAdmin):
    """Admin configuration for ConsultantRate model."""

    list_display = ('id', 'driver', 'vehicle', 'rate_per_km', 'status', 'updated_at')
    list_filter = ('status', 'driver', 'vehicle')
    search_fields = (
        'driver__first_name',
        'driver__last_name',
        'driver__username',
        'vehicle__license_plate',
        'vehicle__make',
        'vehicle__model',
    )
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Rate Details', {
            'fields': ('driver', 'vehicle', 'rate_per_km', 'status')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
