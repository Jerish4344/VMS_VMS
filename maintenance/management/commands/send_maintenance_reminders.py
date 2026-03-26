from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from maintenance.models import Maintenance
from accounts.models import CustomUser
import datetime
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
    help = 'Send reminders for scheduled maintenance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of days in advance to send maintenance reminders'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without sending actual emails'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        today = timezone.now().date()
        reminder_date = today + datetime.timedelta(days=days)
        
        # Get maintenance records scheduled for the reminder date
        upcoming_maintenance = Maintenance.objects.filter(
            status='scheduled',
            scheduled_date=reminder_date
        ).select_related('vehicle', 'maintenance_type', 'provider', 'reported_by')
        
        self.stdout.write(f"Found {upcoming_maintenance.count()} maintenance records scheduled for {reminder_date}")
        
        if upcoming_maintenance.count() == 0:
            return
        
        recipients = getattr(settings, 'ZEPTO_ALERT_RECIPIENTS', [])
        self.stdout.write(f"Sending to {len(recipients)} ZEPTO_ALERT_RECIPIENTS")
        
        # Build HTML email body
        maint_rows = ""
        for maintenance in upcoming_maintenance:
            provider = maintenance.provider.name if maintenance.provider else 'N/A'
            maint_rows += f"""
            <tr>
              <td style='padding: 8px; border: 1px solid #ddd;'>{maintenance.vehicle.license_plate}</td>
              <td style='padding: 8px; border: 1px solid #ddd;'>{maintenance.maintenance_type.name}</td>
              <td style='padding: 8px; border: 1px solid #ddd;'>{maintenance.scheduled_date}</td>
              <td style='padding: 8px; border: 1px solid #ddd;'>{provider}</td>
            </tr>"""
        
        subject = f"🔧 Maintenance Reminder: {upcoming_maintenance.count()} task(s) scheduled for {reminder_date}"
        html_body = f"""
        <div style='font-family: Arial, sans-serif; background: #f9f9f9; padding: 24px;'>
          <div style='max-width: 600px; margin: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #eee; padding: 32px;'>
            <h2 style='color: #1565c0; margin-top: 0;'>🔧 Maintenance Reminder</h2>
            <p style='font-size: 15px; color: #333;'>
              <b>{upcoming_maintenance.count()}</b> maintenance task(s) scheduled for <b>{reminder_date}</b>.
            </p>
            <table style='width: 100%; border-collapse: collapse; margin: 16px 0;'>
              <thead>
                <tr style='background: #f5f5f5;'>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Vehicle</th>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Type</th>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Date</th>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Provider</th>
                </tr>
              </thead>
              <tbody>{maint_rows}</tbody>
            </table>
            <p style='color: #555;'>Please review these scheduled maintenance tasks.</p>
            <hr style='border: none; border-top: 1px solid #eee; margin: 24px 0;'>
            <div style='text-align: center; color: #aaa; font-size: 13px;'>
              VMS Automated Alert &mdash; <span style='color: #1976d2;'>jeyarama.com</span>
            </div>
          </div>
        </div>
        """
        
        if not dry_run:
            try:
                _send_zepto_email(subject, html_body, recipients)
                self.stdout.write(self.style.SUCCESS(f"Sent reminder email to {len(recipients)} recipients"))
            except Exception as e:
                logger.error(f"Failed to send maintenance reminder email: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Failed to send email: {str(e)}"))
        else:
            self.stdout.write(f"[DRY RUN] Would send to {recipients}")
        
        # Also create in-app notifications for admin/manager users
        if not dry_run:
            from dashboard.models import Notification
            managers = CustomUser.objects.filter(
                user_type__in=['admin', 'manager', 'vehicle_manager']
            )
            
            for maintenance in upcoming_maintenance:
                notification_text = f"Maintenance scheduled: {maintenance.maintenance_type.name} for {maintenance.vehicle.license_plate} on {maintenance.scheduled_date}"
                
                for user in managers:
                    Notification.objects.create(
                        user=user,
                        text=notification_text,
                        link=f'/maintenance/{maintenance.id}/',
                        icon='tools',
                        level='info'
                    )
        
        self.stdout.write(self.style.SUCCESS(f"Successfully sent reminders for {upcoming_maintenance.count()} scheduled maintenance records"))
