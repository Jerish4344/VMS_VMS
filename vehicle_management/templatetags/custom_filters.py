from django import template
from django.utils import timezone
import datetime

register = template.Library()

@register.filter
def status_color(status):
    """Return a CSS color class based on status."""
    colors = {
        'available': 'success',
        'in_use': 'primary',
        'maintenance': 'warning',
        'retired': 'secondary',
        'ongoing': 'info',
        'completed': 'success',
        'cancelled': 'danger',
        'scheduled': 'warning',
        'in_progress': 'primary',
        'reported': 'warning',
        'under_investigation': 'info',
        'repair_scheduled': 'primary',
        'repair_in_progress': 'primary',
        'resolved': 'success',
    }
    return colors.get(status, 'secondary')

@register.filter
def days_until(date):
    """Return number of days until a given date."""
    if not date:
        return None
    
    today = timezone.now().date()
    delta = date - today
    
    return delta.days

@register.filter
def days_since(date):
    """Return number of days since a given date."""
    if not date:
        return None
    
    today = timezone.now().date()
    delta = today - date
    
    return delta.days

@register.filter
def format_duration(duration):
    """Format a duration (timedelta) into a readable string."""
    if not duration:
        return "N/A"
    
    total_seconds = duration.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

@register.filter
def format_distance(meters):
    """Format a distance in meters to km with 1 decimal place."""
    if not meters:
        return "0 km"
    
    km = meters / 1000
    return f"{km:.1f} km"

@register.filter
def currency(amount):
    """Format a number as currency."""
    if amount is None:
        return "$0.00"
    
    return f"${amount:,.2f}"

@register.filter
def file_extension(filename):
    """Return the file extension from a filename."""
    if not filename:
        return ""
    
    return filename.split('.')[-1].lower()

@register.filter
def notification_icon(icon_name):
    """Return appropriate Font Awesome icon class."""
    icon_map = {
        'bell': 'fa-bell',
        'info': 'fa-info-circle',
        'warning': 'fa-exclamation-triangle',
        'danger': 'fa-exclamation-circle',
        'success': 'fa-check-circle',
        'car': 'fa-car',
        'document': 'fa-file-alt',
        'maintenance': 'fa-tools',
        'fuel': 'fa-gas-pump',
        'accident': 'fa-car-crash',
        'trip': 'fa-route',
        'user': 'fa-user',
        'calendar': 'fa-calendar-alt',
        'money': 'fa-money-bill-wave',
        'clock': 'fa-clock',
        'location': 'fa-map-marker-alt',
    }
    
    return icon_map.get(icon_name, 'fa-bell')

@register.filter
def vehicle_status_icon(status):
    """Return an appropriate icon for vehicle status."""
    icons = {
        'available': 'fa-check-circle',
        'in_use': 'fa-car-side',
        'maintenance': 'fa-tools',
        'retired': 'fa-archive',
    }
    
    return icons.get(status, 'fa-question-circle')