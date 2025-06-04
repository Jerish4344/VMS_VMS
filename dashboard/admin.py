from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for Notification model."""
    
    list_display = ('id', 'user', 'text', 'timestamp', 'read', 'level')
    list_filter = ('read', 'level', 'timestamp')
    search_fields = ('user__username', 'text')
    readonly_fields = ('timestamp',)
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'text', 'link', 'icon', 'level')
        }),
        ('Status', {
            'fields': ('read', 'timestamp')
        }),
    )