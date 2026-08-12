"""Store Visit token issuance and confirmation.

When a personal-vehicle-staff driver ends a trip whose purpose is 'Store
Visit', VMS issues a sequential token (see StoreVisitToken in models.py).
The driver types that token into the third-party Appointment System's Store
Visit record; that system then calls back through the API
(core.api_views.StoreVisitTokenConfirmView) to confirm it, which is what
makes the trip eligible for reimbursement.
"""

import logging

from django.urls import reverse

from .models import (
    STORE_VISIT_PURPOSE,
    STORE_VISIT_TOKEN_EFFECTIVE_DATE,
    StoreVisitToken,
    _trip_start_date,
)

logger = logging.getLogger(__name__)


def requires_store_visit_token(trip):
    """Return True if this trip should get a Store Visit token on close.

    Only applies to trips starting on/after STORE_VISIT_TOKEN_EFFECTIVE_DATE —
    see the matching check in Trip.counts_for_reimbursement / reimbursement_eligible_q.
    """
    if trip is None or trip.driver_id is None:
        return False
    if trip.purpose != STORE_VISIT_PURPOSE:
        return False
    if getattr(trip.driver, 'user_type', None) != 'personal_vehicle_staff':
        return False
    if not trip.start_time:
        return False
    return _trip_start_date(trip.start_time) >= STORE_VISIT_TOKEN_EFFECTIVE_DATE


def issue_token(trip):
    """Issue (or return the existing) Store Visit token for a just-closed
    trip. Safe to call repeatedly — idempotent via get_or_create.
    """
    if not requires_store_visit_token(trip):
        return None

    token, created = StoreVisitToken.objects.get_or_create(trip=trip)
    if created:
        _notify_driver_token_issued(trip, token)
    return token


def _safe_url(name, *args):
    try:
        return reverse(name, args=args)
    except Exception:
        return ''


def _create_notification(user, text, link='', level='info', icon='bell'):
    if user is None:
        return
    try:
        from dashboard.models import Notification
        Notification.objects.create(
            user=user, text=text, link=link, level=level, icon=icon,
        )
    except Exception as exc:
        logger.error('Failed to create notification: %s', exc)


def _notify_driver_token_issued(trip, token):
    text = (
        f"Store Visit token: {token.pk}. Enter this number in the Appointment "
        f"System's Store Visit record to confirm your visit — reimbursement for "
        f"this trip is on hold until it's confirmed."
    )
    _create_notification(
        trip.driver,
        text=text,
        link=_safe_url('trip_detail', trip.pk),
        level='info',
        icon='key',
    )


def notify_driver_token_confirmed(trip):
    text = (
        f"Your store visit was confirmed for the trip on "
        f"{trip.start_time.strftime('%d %b %Y')} — it's now eligible for reimbursement."
    )
    _create_notification(
        trip.driver,
        text=text,
        link=_safe_url('trip_detail', trip.pk),
        level='success',
        icon='check-circle',
    )
