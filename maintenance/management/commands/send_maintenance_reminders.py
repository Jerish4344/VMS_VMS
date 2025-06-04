from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from maintenance.models import Maintenance
from accounts.models import CustomUser
import datetime
import logging

logger = logging.getLogger(__name__)

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
        
        # Get vehicle managers and admins to notify
        managers = CustomUser.objects.filter(
            user_type__in=['admin', 'manager', 'vehicle_manager']
        )
        
        self.stdout.write(f"Found {managers.count()} managers to notify")
        
        # Generate notification summary for all upcoming maintenance
        notification_summary = "The following maintenance is scheduled in the next few days:\n\n"
        
        for maintenance in upcoming_maintenance:
            notification_summary += f"- {maintenance.maintenance_type.name} for {maintenance.vehicle.license_plate}: "
            notification_summary += f"Scheduled on {maintenance.scheduled_date}"
            if maintenance.provider:
                notification_summary += f" at {maintenance.provider.name}"
            notification_summary += "\n"
        
        # Send notification emails
        for user in managers:
            if not dry_run:
                try:
                    send_mail(
                        subject=f'Maintenance Reminder - {len(upcoming_maintenance)} maintenance records scheduled',
                        message=f"Dear {user.get_full_name()},\n\n" + notification_summary + 
                               f"\nPlease login to the Vehicle Management System to review these scheduled maintenance tasks.\n\n" +
                               f"This is an automated notification.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Sent reminder email to {user.email}"))
                except Exception as e:
                    logger.error(f"Failed to send email to {user.email}: {str(e)}")
                    self.stdout.write(self.style.ERROR(f"Failed to send email to {user.email}: {str(e)}"))
            else:
                self.stdout.write(f"[DRY RUN] Would send reminder email to {user.email}")
        
        # Also create in-app notifications
        if not dry_run:
            from dashboard.models import Notification
            
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