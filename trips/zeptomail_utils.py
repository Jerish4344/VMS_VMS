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
