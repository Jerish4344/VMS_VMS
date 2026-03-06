from django.utils import timezone
from django.db.models import Q
import json

def get_notification_count(user):
    """Get unread notification count for a user."""
    from .models import Notification
    
    return Notification.objects.filter(
        user=user,
        read=False
    ).count()

def add_notification(user, text, link="", icon="bell", level="info"):
    """Add a notification for a user."""
    from .models import Notification
    
    notification = Notification.objects.create(
        user=user,
        text=text,
        link=link,
        icon=icon,
        level=level
    )
    
    return notification

def add_notification_for_role(user_type, text, link="", icon="bell", level="info"):
    """Add notification for all users with a specific role.
    Uses bulk_create for efficiency instead of individual creates.
    """
    from django.contrib.auth import get_user_model
    from .models import Notification
    
    User = get_user_model()
    users = User.objects.filter(user_type=user_type)
    
    notifications = [
        Notification(
            user=user,
            text=text,
            link=link,
            icon=icon,
            level=level
        )
        for user in users
    ]
    
    created = Notification.objects.bulk_create(notifications)
    
    # Invalidate notification cache for affected users
    try:
        from django.core.cache import cache
        for user in users:
            cache.delete(f'user_notifications_{user.pk}')
    except Exception:
        pass  # Cache backend down — safe to ignore
    
    return created

def mark_notification_read(notification_id):
    """Mark a notification as read using a single UPDATE query."""
    from .models import Notification
    
    updated = Notification.objects.filter(id=notification_id, read=False).update(read=True)
    
    if updated:
        # Invalidate cache for the notification's user
        try:
            from django.core.cache import cache
            notif = Notification.objects.values_list('user_id', flat=True).get(id=notification_id)
            cache.delete(f'user_notifications_{notif}')
        except Notification.DoesNotExist:
            pass
        except Exception:
            pass  # Cache backend down
        return True
    return False

def mark_all_notifications_read(user):
    """Mark all notifications for a user as read."""
    from .models import Notification
    
    Notification.objects.filter(user=user, read=False).update(read=True)
