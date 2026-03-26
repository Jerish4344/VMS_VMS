from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from documents.models import Document
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
    help = 'Send notifications for documents that are about to expire'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days in advance to check for expiring documents'
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
        expiry_date = today + datetime.timedelta(days=days)
        
        # Get documents expiring within the specified days
        expiring_documents = Document.objects.filter(
            expiry_date__range=[today, expiry_date]
        ).select_related('vehicle', 'document_type')
        
        self.stdout.write(f"Found {expiring_documents.count()} documents expiring in the next {days} days")
        
        if expiring_documents.count() == 0:
            return
        
        recipients = getattr(settings, 'ZEPTO_ALERT_RECIPIENTS', [])
        self.stdout.write(f"Sending to {len(recipients)} ZEPTO_ALERT_RECIPIENTS")
        
        # Build HTML email body
        doc_rows = ""
        for document in expiring_documents:
            days_until_expiry = (document.expiry_date - today).days
            color = '#d32f2f' if days_until_expiry <= 7 else '#e65100' if days_until_expiry <= 14 else '#333'
            doc_rows += f"""
            <tr>
              <td style='padding: 8px; border: 1px solid #ddd;'>{document.vehicle.license_plate}</td>
              <td style='padding: 8px; border: 1px solid #ddd;'>{document.document_type.name}</td>
              <td style='padding: 8px; border: 1px solid #ddd;'>{document.expiry_date}</td>
              <td style='padding: 8px; border: 1px solid #ddd; color: {color}; font-weight: bold;'>{days_until_expiry} days</td>
            </tr>"""
        
        subject = f"📋 Document Expiry Alert: {expiring_documents.count()} document(s) expiring soon"
        html_body = f"""
        <div style='font-family: Arial, sans-serif; background: #f9f9f9; padding: 24px;'>
          <div style='max-width: 600px; margin: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #eee; padding: 32px;'>
            <h2 style='color: #e65100; margin-top: 0;'>📋 Document Expiry Notification</h2>
            <p style='font-size: 15px; color: #333;'>
              <b>{expiring_documents.count()}</b> vehicle document(s) are expiring in the next <b>{days}</b> days.
            </p>
            <table style='width: 100%; border-collapse: collapse; margin: 16px 0;'>
              <thead>
                <tr style='background: #f5f5f5;'>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Vehicle</th>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Document</th>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Expiry Date</th>
                  <th style='padding: 8px; border: 1px solid #ddd; text-align: left;'>Remaining</th>
                </tr>
              </thead>
              <tbody>{doc_rows}</tbody>
            </table>
            <p style='color: #555;'>Please review and renew these documents.</p>
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
                self.stdout.write(self.style.SUCCESS(f"Sent notification email to {len(recipients)} recipients"))
            except Exception as e:
                logger.error(f"Failed to send document expiry email: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Failed to send email: {str(e)}"))
        else:
            self.stdout.write(f"[DRY RUN] Would send to {recipients}")
        
        # Also create in-app notifications for admin/manager users
        if not dry_run:
            from dashboard.models import Notification
            admins_managers = CustomUser.objects.filter(
                user_type__in=['admin', 'manager', 'vehicle_manager']
            )
            
            for document in expiring_documents:
                days_until_expiry = (document.expiry_date - today).days
                notification_text = f"{document.document_type.name} for {document.vehicle.license_plate} expires in {days_until_expiry} days"
                
                for user in admins_managers:
                    Notification.objects.create(
                        user=user,
                        text=notification_text,
                        link=f'/documents/{document.id}/',
                        icon='file-alt',
                        level='warning'
                    )
        
        self.stdout.write(self.style.SUCCESS(f"Successfully sent notifications for {expiring_documents.count()} expiring documents"))
