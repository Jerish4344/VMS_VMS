from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from documents.models import Document
from accounts.models import CustomUser
import datetime
import logging

logger = logging.getLogger(__name__)

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
        
        # Get admin and manager users to notify
        admins_managers = CustomUser.objects.filter(
            user_type__in=['admin', 'manager', 'vehicle_manager']
        )
        
        self.stdout.write(f"Found {admins_managers.count()} admin/manager users to notify")
        
        # Generate notification summary for all expiring documents
        notification_summary = "The following documents are expiring soon:\n\n"
        
        for document in expiring_documents:
            days_until_expiry = (document.expiry_date - today).days
            notification_summary += f"- {document.document_type.name} for {document.vehicle.license_plate}: "
            notification_summary += f"Expires in {days_until_expiry} days ({document.expiry_date})\n"
        
        # Send notification emails
        for user in admins_managers:
            if not dry_run:
                try:
                    send_mail(
                        subject=f'Vehicle Document Expiry Notification - {len(expiring_documents)} documents expiring soon',
                        message=f"Dear {user.get_full_name()},\n\n" + notification_summary + 
                               f"\nPlease login to the Vehicle Management System to review and renew these documents.\n\n" +
                               f"This is an automated notification.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Sent notification email to {user.email}"))
                except Exception as e:
                    logger.error(f"Failed to send email to {user.email}: {str(e)}")
                    self.stdout.write(self.style.ERROR(f"Failed to send email to {user.email}: {str(e)}"))
            else:
                self.stdout.write(f"[DRY RUN] Would send notification email to {user.email}")
        
        # Also create in-app notifications
        if not dry_run:
            from dashboard.models import Notification
            
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