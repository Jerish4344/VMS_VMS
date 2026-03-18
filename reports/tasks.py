"""
Celery tasks for report generation and other background operations.

Usage:
    from reports.tasks import generate_report_task
    result = generate_report_task.delay(user_id, report_type, filters)
"""
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def send_email_task(self, subject, body, recipient_list, from_email=None, html_body=None):
    """Send email in background so it doesn't block the request."""
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        if html_body:
            email.content_subtype = 'html'
            email.body = html_body
        email.send()
        logger.info("Email sent to %s: %s", recipient_list, subject)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipient_list, exc)
        raise self.retry(exc=exc)
