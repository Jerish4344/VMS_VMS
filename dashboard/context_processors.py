from .models import Notification

def notifications_processor(request):
    """Add unread notifications count to all templates."""
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(
            user=request.user,
            read=False
        ).order_by('-timestamp')[:5]
        
        notifications_count = notifications.count()
        
        return {
            'notifications': notifications,
            'notifications_count': notifications_count,
        }
    return {
        'notifications': [],
        'notifications_count': 0,
    }