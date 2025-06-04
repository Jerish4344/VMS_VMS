from django.core.management.base import BaseCommand
from accounts.models import CustomUser
import json

class Command(BaseCommand):
    help = 'Debug StyleHR data structure for pending employees'
    
    def handle(self, *args, **options):
        self.stdout.write('=== StyleHR Data Debug ===')
        
        # Get all pending employees
        pending_employees = CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending'
        ).order_by('-hr_authenticated_at')
        
        if not pending_employees.exists():
            self.stdout.write(self.style.WARNING('No pending employees found'))
            return
        
        for employee in pending_employees:
            self.stdout.write(f'\n--- Employee: {employee.username} ---')
            self.stdout.write(f'Django Full Name: {employee.get_full_name()}')
            self.stdout.write(f'First Name: {employee.first_name}')
            self.stdout.write(f'Last Name: {employee.last_name}')
            self.stdout.write(f'Email: {employee.email}')
            self.stdout.write(f'HR Employee ID: {employee.hr_employee_id}')
            self.stdout.write(f'HR Department: {employee.hr_department}')
            self.stdout.write(f'HR Designation: {employee.hr_designation}')
            
            if employee.hr_data:
                self.stdout.write(f'\nRaw HR Data:')
                self.stdout.write(json.dumps(employee.hr_data, indent=2))
            else:
                self.stdout.write('No HR data stored')
            
            self.stdout.write('-' * 50)