"""Personal Trip approval flow.

Effective 01-May-2026, every personal-vehicle staff trip whose driver has a
``reports_to`` user enters the approval flow. Until the trip is approved by
that manager (or any escalation), it does not count for reimbursement.
"""

from datetime import date, datetime
import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Approval flow only triggers for trips that started on or after this date.
APPROVAL_FLOW_EFFECTIVE_DATE = date(2026, 5, 1)


def _is_personal_staff(user):
    return getattr(user, 'user_type', None) == 'personal_vehicle_staff'


def trip_requires_approval(trip):
    """Return True if this trip should enter the approval flow."""
    if trip is None or trip.driver_id is None:
        return False
    driver = trip.driver
    if not _is_personal_staff(driver):
        return False
    if not getattr(driver, 'reports_to_id', None):
        return False
    if not trip.start_time:
        return False
    start = trip.start_time
    if isinstance(start, datetime):
        start = timezone.localtime(start).date() if timezone.is_aware(start) else start.date()
    return start >= APPROVAL_FLOW_EFFECTIVE_DATE


def submit_for_approval(trip):
    """Move a freshly-completed trip into the pending state and notify the
    manager. Safe to call repeatedly — only acts when status is 'not_required'.
    """
    if not trip_requires_approval(trip):
        return False
    if trip.approval_status != 'not_required':
        return False

    manager = trip.driver.reports_to
    trip.approval_status = 'pending'
    trip.approval_manager = manager
    trip.approval_submitted_at = trip.end_time or timezone.now()
    trip.save(update_fields=[
        'approval_status', 'approval_manager', 'approval_submitted_at', 'updated_at'
    ])

    _notify_manager_pending(trip, manager)
    return True


def approve_trip(trip, manager_user, remarks=''):
    """Manager approves the trip. Returns True on state change."""
    if trip.approval_status != 'pending':
        return False
    trip.approval_status = 'approved'
    trip.approval_action_at = timezone.now()
    trip.approval_action_by = manager_user
    trip.approval_remarks = remarks or ''
    trip.save(update_fields=[
        'approval_status', 'approval_action_at', 'approval_action_by',
        'approval_remarks', 'updated_at'
    ])
    _notify_driver_decision(trip, approved=True)
    return True


def reject_trip(trip, manager_user, remarks=''):
    """Manager rejects the trip."""
    if trip.approval_status != 'pending':
        return False
    trip.approval_status = 'rejected'
    trip.approval_action_at = timezone.now()
    trip.approval_action_by = manager_user
    trip.approval_remarks = remarks or ''
    trip.save(update_fields=[
        'approval_status', 'approval_action_at', 'approval_action_by',
        'approval_remarks', 'updated_at'
    ])
    _notify_driver_decision(trip, approved=False)
    return True


# ---------------------------------------------------------------------------
# Notifications (in-app + ZeptoMail)
# ---------------------------------------------------------------------------

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


def _notify_manager_pending(trip, manager):
    if manager is None:
        return
    driver_name = trip.driver.get_full_name()
    distance = trip.distance_traveled() or 0
    text = f"Trip approval needed: {driver_name} • {distance} km on {trip.start_time.strftime('%d %b %Y')}"
    _create_notification(
        manager,
        text=text,
        link=_safe_url('pending_trip_approvals'),
        level='warning',
        icon='hourglass-half',
    )
    _send_manager_email(trip, manager)


def _notify_driver_decision(trip, approved):
    driver = trip.driver
    if approved:
        text = f"Your trip on {trip.start_time.strftime('%d %b %Y')} was approved."
        level = 'success'
        icon = 'check-circle'
    else:
        text = f"Your trip on {trip.start_time.strftime('%d %b %Y')} was rejected."
        level = 'danger'
        icon = 'times-circle'
    _create_notification(
        driver,
        text=text,
        link=_safe_url('trip_detail', trip.pk),
        level=level,
        icon=icon,
    )
    _send_driver_email(trip, approved)


def _send_manager_email(trip, manager):
    email = getattr(manager, 'email', None)
    if not email:
        return
    try:
        from trips.zeptomail_utils import send_approval_request_email
        send_approval_request_email(trip, manager, [email])
    except Exception as exc:
        logger.error('Failed to send manager approval email: %s', exc)


def _send_driver_email(trip, approved):
    email = getattr(trip.driver, 'email', None)
    if not email:
        return
    try:
        from trips.zeptomail_utils import send_approval_decision_email
        send_approval_decision_email(trip, approved, [email])
    except Exception as exc:
        logger.error('Failed to send driver decision email: %s', exc)
