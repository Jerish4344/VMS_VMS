from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser

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
            # Get managers to notify
            managers = CustomUser.objects.filter(
                user_type__in=['admin', 'manager', 'vehicle_manager'],
                is_active=True,
                email__isnull=False
            ).exclude(email='')
            
            if managers.exists():
                subject = f'Urgent: {urgent_requests.count()} Employee Approval Requests Pending'
                
                # Build email content
                message_lines = [
                    f'You have {urgent_requests.count()} employee approval requests that have been pending for more than 24 hours:',
                    '',
                ]
                
                for employee in urgent_requests[:10]:  # Limit to 10 in email
                    days_pending = (timezone.now() - employee.hr_authenticated_at).days
                    hr_role = employee.hr_designation or "Employee"
                    if employee.hr_department:
                        hr_role += f" ({employee.hr_department})"
                    
                    message_lines.append(f'• {employee.get_full_name()} - {hr_role} - {days_pending} days pending')
                
                if urgent_requests.count() > 10:
                    message_lines.append(f'... and {urgent_requests.count() - 10} more')
                
                message_lines.extend([
                    '',
                    'Please log in to the Vehicle Management System to review and approve these requests.',
                    f'Login at: {settings.SITE_URL if hasattr(settings, "SITE_URL") else "Your VMS URL"}',
                ])
                
                message = '\n'.join(message_lines)
                
                # Send to all managers
                manager_emails = [m.email for m in managers]
                
                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        manager_emails,
                        fail_silently=False
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Sent reminder to {len(manager_emails)} managers')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to send emails: {e}')
                    )
        else:
            self.stdout.write(
                self.style.SUCCESS('No urgent approval requests found')
            )