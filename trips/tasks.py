"""Celery tasks for the trips app."""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def send_trip_alert_email_async(self, trip_id):
    """Send ZeptoMail suspicious-distance alert in background."""
    try:
        from trips.models import Trip
        from trips.zeptomail_utils import send_trip_alert_email
        from django.conf import settings

        trip = Trip.objects.select_related('driver', 'vehicle').get(pk=trip_id)
        recipients = getattr(settings, 'ZEPTO_ALERT_RECIPIENTS', [])
        if recipients:
            send_trip_alert_email(trip, recipients)
            logger.info("Sent trip alert email for trip %s", trip_id)
    except Exception as exc:
        logger.error("Failed to send trip alert for trip %s: %s", trip_id, exc)
        raise self.retry(exc=exc)
