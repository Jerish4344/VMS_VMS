"""Celery tasks for the core app — generic utilities."""
from celery import shared_task
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def run_management_command(self, command_name, *args):
    """Run a Django management command as a Celery task.

    Used by Celery Beat to schedule periodic commands like
    send_document_expiry_notifications, send_maintenance_reminders, etc.

    Guards against running the same scheduled command twice in one day —
    either from Celery retrying after a partial success, or Celery Beat
    double-firing — since several of these commands send real emails and
    would otherwise duplicate them to real people.
    """
    arg_key = ':'.join(str(a) for a in args)
    lock_key = f"mgmt_cmd_lock:{command_name}:{arg_key}:{timezone.localdate()}"

    # cache.add() only sets the key if it doesn't already exist — atomic,
    # so this is safe even if two workers race on the same scheduled task.
    if not cache.add(lock_key, True, timeout=60 * 60):
        logger.warning("Skipping duplicate run of %s %s — already ran today", command_name, ' '.join(args))
        return

    try:
        logger.info("Running management command: %s %s", command_name, ' '.join(args))
        call_command(command_name, *args)
        logger.info("Completed management command: %s", command_name)
    except Exception as exc:
        logger.error("Management command %s failed: %s", command_name, exc)
        # Release the lock so the retry can actually run instead of silently
        # no-oping against its own lock.
        cache.delete(lock_key)
        raise self.retry(exc=exc)
