from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
import logging
import requests

logger = logging.getLogger(__name__)


def _send_zepto_email(subject, html_body, recipients):
    """Send email via ZeptoMail API to ZEPTO_ALERT_RECIPIENTS."""
    api_key = getattr(settings, 'ZEPTO_API_KEY', '')
    if not api_key or not recipients:
        return False
    data = {
        "from": {"address": "noreply@jeyarama.com", "name": "VMS System"},
        "to": [{"email_address": {"address": r}} for r in recipients],
        "subject": subject,
        "htmlbody": html_body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Zoho-enczapikey {api_key}",
    }
    resp = requests.post('https://api.zeptomail.in/v1.1/email', json=data, headers=headers, timeout=10)
    resp.raise_for_status()
    return True


class Command(BaseCommand):
    help = 'Send email reminders for pending approvals'
    
    def handle(self, *args, **options):
        # Get pending requests older than 24 hours
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        
        urgent_requests = CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending',
            hr_authenticated_at__lt=twenty_four_hours_ago
        )
        
        if urgent_requests.exists():
            recipients = getattr(settings, 'ZEPTO_ALERT_RECIPIENTS', [])
            
            if recipients:
                # Build HTML email body
                employee_rows = ""
                for employee in urgent_requests[:20]:
                    days_pending = (timezone.now() - employee.hr_authenticated_at).days
                    hr_role = employee.hr_designation or "Employee"
                    if employee.hr_department:
                        hr_role += f" ({employee.hr_department})"
                    employee_rows += f"""
                    <tr>
                      <td style='padding: 8px; border: 1px solid #ddd;'>{employee.get_full_name()}</td>
                      <td style='padding: 8px; border: 1px solid #ddd;'>{hr_role}</td>
                      <td style='padding: 8px; border: 1px solid #ddd; color: #d32f2f; font-weight: bold;'>{days_pending} days</td>
                    </tr>"""
                
                extra = ""
                if urgent_requests.count() > 20:
                    extra = f"<p style='color: #888;'>... and {urgent_requests.count() - 20} more</p>"
                
                subject = f"🔔 Urgent: {urgent_requests.count()} Employee Approval Requests Pending"
                html_body = f"""
                <div style='font-family: Arial, sans-serif; background: #f9f9f9; padding: 24px;'>
                  <div style='max-width: 600px; margin: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #eee; padding: 32px;'>
                    <h2 style='color: #d32f2f; margin-top: 0;'>🔔 Pending Approval Reminder</h2>
                    <p style='font-size: 15px; color: #333;'>
                      <b>{urgent_requests.count()}</b> employee approval request(s) have been pending for more than 24 hours.
                    </p>
                    <table style='width: 100%; border-collapse: collapse; margin: 16px 0;'>
                      <thead>
                        <tr style='background: #f5f5f5;'>
                          <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Employee</th>
                          <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Role</th>
                          <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Pending</th>
                        </tr>
                      </thead>
                      <tbody>{employee_rows}</tbody>
                    </table>
                    {extra}
                    <p style='color: #555;'>Please log in to review and approve these requests.</p>
                    <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;'>
                    <div style='text-align: center; color: #aaa; font-size: 13px;'>
                      VMS Automated Alert &mdash; <span style='color: #1976d2;'>jeyarama.com</span>
                    </div>
                  </div>
                </div>
                """
                
                try:
                    _send_zepto_email(subject, html_body, recipients)
                    self.stdout.write(
                        self.style.SUCCESS(f'Sent reminder to {len(recipients)} recipients')
                    )
                except Exception as e:
                    logger.error(f"Failed to send approval reminder email: {e}")
                    self.stdout.write(
                        self.style.ERROR(f'Failed to send emails: {e}')
                    )
        else:
            self.stdout.write(
                self.style.SUCCESS('No urgent approval requests found')
            )
