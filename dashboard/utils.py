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
    """Add notification for all users with a specific role."""
    from django.contrib.auth import get_user_model
    from .models import Notification
    
    User = get_user_model()
    users = User.objects.filter(user_type=user_type)
    
    notifications = []
    for user in users:
        notification = Notification.objects.create(
            user=user,
            text=text,
            link=link,
            icon=icon,
            level=level
        )
        notifications.append(notification)
    
    return notifications

def mark_notification_read(notification_id):
    """Mark a notification as read."""
    from .models import Notification
    
    try:
        notification = Notification.objects.get(id=notification_id)
        notification.read = True
        notification.save()
        return True
    except Notification.DoesNotExist:
        return False

def mark_all_notifications_read(user):
    """Mark all notifications for a user as read."""
    from .models import Notification
    
    Notification.objects.filter(user=user, read=False).update(read=True)