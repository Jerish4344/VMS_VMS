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

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def send_overnight_trip_alert_async(self):
    """Send alert for trips started yesterday that are still ongoing."""
    try:
        from trips.models import Trip
        from trips.zeptomail_utils import send_overnight_trip_alert_email
        from django.conf import settings
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.localtime()
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59, microsecond=999999)

        ongoing_trips = Trip.objects.filter(
            status='ongoing',
            start_time__gte=yesterday_start,
            start_time__lte=yesterday_end,
        ).select_related('driver', 'vehicle')

        if ongoing_trips.exists():
            recipients = getattr(settings, 'ZEPTO_ALERT_RECIPIENTS', [])
            if recipients:
                send_overnight_trip_alert_email(list(ongoing_trips), recipients)
                logger.info("Sent overnight trip alert for %d trip(s)", ongoing_trips.count())
        else:
            logger.info("No overnight ongoing trips found")
    except Exception as exc:
        logger.error("Failed to send overnight trip alert: %s", exc)
        raise self.retry(exc=exc)
