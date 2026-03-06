from django.core.cache import cache
from .models import Notification
import logging

logger = logging.getLogger(__name__)

def notifications_processor(request):
    """Add unread notifications count to all templates.
    Uses cache to avoid hitting the DB on every single request.
    Gracefully handles cache failures (Redis down).
    """
    if request.user.is_authenticated:
        cache_key = f'user_notifications_{request.user.pk}'
        
        # Try cache first, but don't crash if Redis is down
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass  # Cache backend down — fall through to DB query
        
        # Single query: fetch top 5 unread, count from the same queryset
        notifications = list(
            Notification.objects.filter(
                user=request.user,
                read=False
            ).order_by('-timestamp')[:5]
        )
        
        # Use a lightweight count query for total unread
        notifications_count = Notification.objects.filter(
            user=request.user,
            read=False
        ).count()
        
        result = {
            'notifications': notifications,
            'notifications_count': notifications_count,
        }
        
        # Cache for 30 seconds to reduce DB hits
        try:
            cache.set(cache_key, result, 30)
        except Exception:
            pass  # Cache backend down — still return the result
        return result
    return {
        'notifications': [],
        'notifications_count': 0,
    }
