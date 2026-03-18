"""Celery tasks for the core app — generic utilities."""
from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def run_management_command(self, command_name, *args):
    """Run a Django management command as a Celery task.

    Used by Celery Beat to schedule periodic commands like
    send_document_expiry_notifications, send_maintenance_reminders, etc.
    """
    try:
        logger.info("Running management command: %s %s", command_name, ' '.join(args))
        call_command(command_name, *args)
        logger.info("Completed management command: %s", command_name)
    except Exception as exc:
        logger.error("Management command %s failed: %s", command_name, exc)
        raise self.retry(exc=exc)
