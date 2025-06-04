# reports/templatetags/report_filters.py
from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def filter_status(status_breakdown, status_code):
    """
    Filter status breakdown by status code and return the count
    """
    for item in status_breakdown:
        if item['status'] == status_code:
            return item['count']
    return 0

@register.filter
def add_days(date, days):
    """Add days to a date"""
    if date:
        return date + timedelta(days=int(days))
    return date

@register.filter
def status_color(status):
    """Return Bootstrap color class for status"""
    status_colors = {
        'available': 'success',
        'in_use': 'primary',
        'maintenance': 'warning',
        'retired': 'secondary',
        'scheduled': 'warning',
        'in_progress': 'primary',
        'completed': 'success',
        'cancelled': 'secondary',
    }
    return status_colors.get(status, 'secondary')