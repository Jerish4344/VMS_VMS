# accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to handle user creation events
    """
    if created:
        # Log new user creation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"New user created: {instance.username} ({instance.get_user_type_display()})")
