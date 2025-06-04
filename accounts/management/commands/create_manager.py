from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a manager/admin user for the approval system'
    
    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username')
        parser.add_argument('--email', type=str, required=True, help='Email address')
        parser.add_argument('--password', type=str, required=True, help='Password')
        parser.add_argument('--type', choices=['admin', 'manager', 'vehicle_manager'], 
                          default='manager', help='User type')
        parser.add_argument('--first-name', type=str, help='First name')
        parser.add_argument('--last-name', type=str, help='Last name')
    
    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        user_type = options['type']
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.ERROR(f'User with username "{username}" already exists')
            )
            return
        
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.ERROR(f'User with email "{email}" already exists')
            )
            return
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            user_type=user_type,
            first_name=options.get('first_name', ''),
            last_name=options.get('last_name', ''),
            is_active=True,
            approval_status='approved'  # Managers don't need approval
        )
        
        if user_type == 'admin':
            user.is_staff = True
            user.is_superuser = True
            user.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {user_type}: {username}')
        )
        self.stdout.write(f'Email: {email}')
        self.stdout.write(f'Type: {user.get_user_type_display()}')
        self.stdout.write(f'Can approve drivers: {user.has_approval_permissions()}')