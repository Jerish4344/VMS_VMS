# accounts/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from .models import CustomUser, AuditLog

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@receiver(post_save, sender=CustomUser)
def audit_user_save(sender, instance, created, **kwargs):
    if created:
        logger.info("New user created: %s (%s)", instance.username, instance.get_user_type_display())
        AuditLog.objects.create(
            user=None,
            action='user_created',
            target_model='CustomUser',
            target_id=instance.pk,
            details=f"Username: {instance.username}, Type: {instance.get_user_type_display()}",
        )


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        user=user,
        action='login',
        ip_address=_get_client_ip(request),
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    if user:
        AuditLog.objects.create(
            user=user,
            action='logout',
            ip_address=_get_client_ip(request),
        )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    AuditLog.objects.create(
        action='login_failed',
        details=f"Username attempted: {credentials.get('username', '?')}",
        ip_address=_get_client_ip(request) if request else None,
    )
