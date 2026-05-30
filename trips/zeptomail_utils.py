import requests
from django.conf import settings

def send_trip_alert_email(trip, recipients):
    """
    Send an alert email using ZeptoMail API if trip distance is suspiciously high.
    """
    # Calculate distance
    distance = trip.distance_traveled() if hasattr(trip, 'distance_traveled') else 0
    if distance <= 120:
        return  # No alert needed

    # ZeptoMail API config
    ZEPTO_API_URL = 'https://api.zeptomail.in/v1.1/email'
    ZEPTO_API_KEY = getattr(settings, 'ZEPTO_API_KEY', None)
    ZEPTO_TEMPLATE_KEY = getattr(settings, 'ZEPTO_TEMPLATE_KEY', None)

    if not ZEPTO_API_KEY:
        return

    subject = f"🚨 ALERT: Suspicious Trip Distance ({distance} km)"
    body = f"""
    <div style='font-family: Arial, sans-serif; background: #f9f9f9; padding: 24px;'>
      <div style='max-width: 500px; margin: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #eee; padding: 32px;'>
        <h2 style='color: #d32f2f; margin-top: 0;'>🚨 Suspicious Trip Alert</h2>
        <p style='font-size: 16px; color: #333;'>
          <b>Driver:</b> <span style='color: #1976d2;'>{trip.driver}</span><br>
          <b>Vehicle:</b> <span style='color: #1976d2;'>{trip.vehicle}</span><br>
          <b>Distance:</b> <span style='color: #d32f2f; font-weight: bold;'>{distance} km</span><br>
          <b>Start:</b> {trip.origin}<br>
          <b>Destination:</b> {trip.destination or 'N/A'}<br>
          <b>Start Odometer:</b> {trip.start_odometer}<br>
          <b>End Odometer:</b> {trip.end_odometer}<br>
        </p>
        <p style='color: #555; font-size: 15px;'>
          Please review this trip for possible incorrect entry or misuse.<br>
          <span style='font-size: 13px; color: #888;'>Time: {trip.end_time or 'N/A'}</span>
        </p>
        <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;'>
        <div style='text-align: center; color: #aaa; font-size: 13px;'>
          VMS Automated Alert &mdash; <span style='color: #1976d2;'>jeyarama.com</span>
        </div>
      </div>
    </div>
    """

    data = {
        "from": {"address": "noreply@jeyarama.com", "name": "VMS System"},
        "to": [{"email_address": {"address": r}} for r in recipients],
        "subject": subject,
        "htmlbody": body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Zoho-enczapikey {ZEPTO_API_KEY}"
    }
    try:
        response = requests.post(ZEPTO_API_URL, json=data, headers=headers, timeout=10)
        print(f"ZeptoMail API response: {response.status_code} {response.text}")
        response.raise_for_status()
    except Exception as e:
        print(f"ZeptoMail error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"ZeptoMail response: {e.response.text}")

def send_overnight_trip_alert_email(trips, recipients):
    """
    Send an alert email for trips that started yesterday and are still ongoing.
    """
    if not trips or not recipients:
        return

    ZEPTO_API_URL = 'https://api.zeptomail.in/v1.1/email'
    ZEPTO_API_KEY = getattr(settings, 'ZEPTO_API_KEY', None)

    if not ZEPTO_API_KEY:
        return

    # Build trip rows
    trip_rows = ""
    for trip in trips:
        delta = trip.get_duration_timedelta()
        hours = int(delta.total_seconds() // 3600) if delta else 'N/A'
        trip_rows += f"""
        <tr>
          <td style='padding: 8px; border: 1px solid #ddd;'>{trip.driver.get_full_name()}</td>
          <td style='padding: 8px; border: 1px solid #ddd;'>{trip.vehicle}</td>
          <td style='padding: 8px; border: 1px solid #ddd;'>{trip.origin}</td>
          <td style='padding: 8px; border: 1px solid #ddd;'>{trip.destination or 'N/A'}</td>
          <td style='padding: 8px; border: 1px solid #ddd;'>{trip.start_time.strftime('%d-%b-%Y %I:%M %p')}</td>
          <td style='padding: 8px; border: 1px solid #ddd; color: #d32f2f; font-weight: bold;'>{hours} hrs</td>
        </tr>"""

    subject = f"⚠️ ALERT: {len(trips)} Trip(s) Not Closed From Previous Day"
    body = f"""
    <div style='font-family: Arial, sans-serif; background: #f9f9f9; padding: 24px;'>
      <div style='max-width: 700px; margin: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #eee; padding: 32px;'>
        <h2 style='color: #e65100; margin-top: 0;'>⚠️ Overnight Ongoing Trips</h2>
        <p style='font-size: 15px; color: #333;'>
          The following <b>{len(trips)}</b> trip(s) were started yesterday but have <b>not been closed</b>.
          Please review and take necessary action.
        </p>
        <table style='width: 100%; border-collapse: collapse; margin: 16px 0;'>
          <thead>
            <tr style='background: #f5f5f5;'>
              <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Driver</th>
              <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Vehicle</th>
              <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Origin</th>
              <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Destination</th>
              <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Started</th>
              <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Duration</th>
            </tr>
          </thead>
          <tbody>{trip_rows}</tbody>
        </table>
        <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;'>
        <div style='text-align: center; color: #aaa; font-size: 13px;'>
          VMS Automated Alert &mdash; <span style='color: #1976d2;'>jeyarama.com</span>
        </div>
      </div>
    </div>
    """

    data = {
        "from": {"address": "noreply@jeyarama.com", "name": "VMS System"},
        "to": [{"email_address": {"address": r}} for r in recipients],
        "subject": subject,
        "htmlbody": body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Zoho-enczapikey {ZEPTO_API_KEY}"
    }
    try:
        response = requests.post(ZEPTO_API_URL, json=data, headers=headers, timeout=10)
        print(f"ZeptoMail overnight alert response: {response.status_code} {response.text}")
        response.raise_for_status()
    except Exception as e:
        print(f"ZeptoMail overnight alert error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"ZeptoMail response: {e.response.text}")


# ---------------------------------------------------------------------------
# Personal Trip approval flow emails
# ---------------------------------------------------------------------------

def _zepto_send(subject, body, recipients):
    """Internal helper to fire a ZeptoMail email."""
    if not recipients:
        return
    ZEPTO_API_URL = 'https://api.zeptomail.in/v1.1/email'
    ZEPTO_API_KEY = getattr(settings, 'ZEPTO_API_KEY', None)
    if not ZEPTO_API_KEY:
        return
    data = {
        "from": {"address": "noreply@jeyarama.com", "name": "VMS System"},
        "to": [{"email_address": {"address": r}} for r in recipients],
        "subject": subject,
        "htmlbody": body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Zoho-enczapikey {ZEPTO_API_KEY}",
    }
    try:
        response = requests.post(ZEPTO_API_URL, json=data, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"ZeptoMail approval email error: {e}")


def send_approval_request_email(trip, manager, recipients):
    """Notify a manager that a personal trip is awaiting their approval."""
    distance = trip.distance_traveled() if hasattr(trip, 'distance_traveled') else 0
    rate = getattr(trip.vehicle, 'reimbursement_rate_per_km', None) or 0
    try:
        amount = float(rate) * distance
    except Exception:
        amount = 0
    base_url = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    approval_link = f"{base_url}/trips/approvals/" if base_url else "/trips/approvals/"

    subject = f"Trip approval needed: {trip.driver.get_full_name()} ({distance} km)"
    body = f"""
    <div style='font-family: Arial, sans-serif; background:#f4f6f9; padding:24px;'>
      <div style='max-width:560px; margin:auto; background:#fff; border-radius:8px; padding:28px; box-shadow:0 2px 6px #e5e9ef;'>
        <h2 style='color:#1976d2; margin-top:0;'>Personal Trip Awaiting Approval</h2>
        <p style='color:#333; font-size:15px;'>Hi {manager.get_full_name() or manager.username},</p>
        <p style='color:#333; font-size:15px;'>
          <b>{trip.driver.get_full_name()}</b> has submitted a personal-vehicle trip for your approval.
        </p>
        <table style='width:100%; border-collapse:collapse; margin:14px 0; font-size:14px;'>
          <tr><td style='padding:6px 8px; color:#666;'>Date</td><td style='padding:6px 8px;'>{trip.start_time.strftime('%d %b %Y')}</td></tr>
          <tr><td style='padding:6px 8px; color:#666;'>Vehicle</td><td style='padding:6px 8px;'>{trip.vehicle}</td></tr>
          <tr><td style='padding:6px 8px; color:#666;'>From</td><td style='padding:6px 8px;'>{trip.origin}</td></tr>
          <tr><td style='padding:6px 8px; color:#666;'>To</td><td style='padding:6px 8px;'>{trip.destination or 'N/A'}</td></tr>
          <tr><td style='padding:6px 8px; color:#666;'>Distance</td><td style='padding:6px 8px;'><b>{distance} km</b></td></tr>
          <tr><td style='padding:6px 8px; color:#666;'>Reimbursement</td><td style='padding:6px 8px; color:#2e7d32;'><b>₹{amount:.2f}</b></td></tr>
          <tr><td style='padding:6px 8px; color:#666;'>Purpose</td><td style='padding:6px 8px;'>{trip.purpose}</td></tr>
        </table>
        <div style='text-align:center; margin-top:20px;'>
          <a href='{approval_link}' style='background:#1976d2; color:#fff; padding:10px 22px; text-decoration:none; border-radius:6px; font-weight:600;'>Review &amp; Approve</a>
        </div>
        <p style='color:#888; font-size:12px; margin-top:24px; text-align:center;'>VMS &mdash; jeyarama.com</p>
      </div>
    </div>
    """
    _zepto_send(subject, body, recipients)


def send_approval_decision_email(trip, approved, recipients):
    """Notify a driver of the manager's approval decision."""
    distance = trip.distance_traveled() if hasattr(trip, 'distance_traveled') else 0
    decision = 'Approved' if approved else 'Rejected'
    color = '#2e7d32' if approved else '#c62828'
    icon = '✅' if approved else '❌'
    remarks = trip.approval_remarks or ('No remarks.' if approved else 'No reason provided.')
    actioned_by = trip.approval_action_by.get_full_name() if trip.approval_action_by_id else 'Manager'

    subject = f"{icon} Trip {decision}: {trip.start_time.strftime('%d %b %Y')} ({distance} km)"
    body = f"""
    <div style='font-family: Arial, sans-serif; background:#f4f6f9; padding:24px;'>
      <div style='max-width:520px; margin:auto; background:#fff; border-radius:8px; padding:28px; box-shadow:0 2px 6px #e5e9ef;'>
        <h2 style='color:{color}; margin-top:0;'>{icon} Trip {decision}</h2>
        <p style='color:#333; font-size:15px;'>Hi {trip.driver.get_full_name()},</p>
        <p style='color:#333; font-size:15px;'>
          Your personal trip on <b>{trip.start_time.strftime('%d %b %Y')}</b> ({distance} km) has been
          <b style='color:{color};'>{decision.lower()}</b> by {actioned_by}.
        </p>
        <div style='background:#f7f9fc; border-left:4px solid {color}; padding:12px 14px; margin:14px 0; font-size:14px; color:#444;'>
          <b>Remarks:</b><br>{remarks}
        </div>
        <p style='color:#888; font-size:12px; margin-top:24px; text-align:center;'>VMS &mdash; jeyarama.com</p>
      </div>
    </div>
    """
    _zepto_send(subject, body, recipients)

