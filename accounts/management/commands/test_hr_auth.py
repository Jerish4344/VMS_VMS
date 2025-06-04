# accounts/management/commands/test_hr_auth.py
from django.core.management.base import BaseCommand
from django.contrib.auth import authenticate, get_user_model
from accounts.backends import StyleHRAuthBackend
from accounts.utils import StyleHRAPIClient, check_hr_system_health
import json
import requests
from django.conf import settings
from django.db import models

User = get_user_model()

class Command(BaseCommand):
    help = 'Test StyleHR authentication integration'
    
    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Employee ID or Email to test')
        parser.add_argument('--password', type=str, help='Password to test')
        parser.add_argument('--test-api', action='store_true', help='Test API connection only')
        parser.add_argument('--check-users', action='store_true', help='Check existing HR-authenticated users')
        parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    
    def handle(self, *args, **options):
        self.verbose = options.get('detailed', False)
        
        # Print header
        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write(self.style.HTTP_INFO('StyleHR Authentication Integration Test'))
        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        
        if options['test_api']:
            self.test_api_connection()
            return
        
        if options['check_users']:
            self.check_existing_users()
            return
        
        username = options.get('username')
        password = options.get('password')
        
        if not username or not password:
            self.stdout.write(
                self.style.ERROR('Please provide both --username and --password arguments')
            )
            self.stdout.write('Usage: python manage.py test_hr_auth --username "employee@company.com" --password "password"')
            self.stdout.write('       python manage.py test_hr_auth --test-api')
            self.stdout.write('       python manage.py test_hr_auth --check-users')
            self.stdout.write('       python manage.py test_hr_auth --username "user" --password "pass" --detailed')
            return
        
        # Run comprehensive authentication test
        self.test_user_authentication(username, password)
    
    def test_api_connection(self):
        """Test StyleHR API connectivity and response"""
        self.stdout.write(self.style.WARNING('Testing StyleHR API Connection...'))
        self.stdout.write('-' * 50)
        
        # Test 1: Basic website connectivity
        try:
            self.stdout.write('1. Testing StyleHR website accessibility...')
            response = requests.get('https://stylehr.in', timeout=10)
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ StyleHR website accessible (Status: {response.status_code})')
            )
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ Cannot reach StyleHR website: {str(e)}')
            )
            return
        
        # Test 2: API endpoint accessibility
        try:
            self.stdout.write('\n2. Testing API endpoint with dummy credentials...')
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                'email': 'test@example.com',
                'password': 'dummy_password_12345'
            }
            
            response = requests.post(
                'https://stylehr.in/api/login/',
                json=payload,
                headers=headers,
                timeout=10
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ API endpoint accessible (Status: {response.status_code})')
            )
            
            # Analyze response
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    self.stdout.write(f'   → Response type: {type(response_data).__name__}')
                    if self.verbose:
                        self.stdout.write(f'   → Response sample: {str(response_data)[:200]}...')
                except:
                    self.stdout.write('   → Response is not JSON format')
            else:
                response_text = response.text[:200]
                self.stdout.write(f'   → Response: {response_text}')
                if 'Invalid username/password' in response_text:
                    self.stdout.write(self.style.SUCCESS('   ✓ Expected error response received'))
                
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'   ✗ Cannot reach StyleHR API: {str(e)}')
            )
            return
        
        # Test 3: Configuration check
        self.stdout.write('\n3. Checking Django configuration...')
        auth_backends = getattr(settings, 'AUTHENTICATION_BACKENDS', [])
        if 'accounts.backends.StyleHRAuthBackend' in auth_backends:
            self.stdout.write(self.style.SUCCESS('   ✓ StyleHR backend configured in AUTHENTICATION_BACKENDS'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ StyleHR backend not found in AUTHENTICATION_BACKENDS'))
        
        stylehr_timeout = getattr(settings, 'STYLEHR_API_TIMEOUT', None)
        if stylehr_timeout:
            self.stdout.write(self.style.SUCCESS(f'   ✓ API timeout configured: {stylehr_timeout} seconds'))
        else:
            self.stdout.write(self.style.WARNING('   ! API timeout not configured (using default)'))
        
        # Test 4: System health check
        self.stdout.write('\n4. Overall system health...')
        if check_hr_system_health():
            self.stdout.write(self.style.SUCCESS('   ✓ StyleHR system is accessible'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ StyleHR system appears to be down'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ API connectivity test completed!'))
    
    def test_user_authentication(self, username, password):
        """Test user authentication with StyleHR"""
        self.stdout.write(self.style.WARNING(f'Testing StyleHR Authentication for: {username}'))
        self.stdout.write('-' * 60)
        
        # Test 1: Direct StyleHR API call
        self.stdout.write('1. Testing direct StyleHR API call...')
        api_client = StyleHRAPIClient()
        hr_data = api_client.authenticate_user(username, password)
        
        if hr_data:
            self.stdout.write(self.style.SUCCESS('   ✓ StyleHR API authentication successful'))
            if self.verbose:
                self.stdout.write('   → HR Data received:')
                for key, value in hr_data.items():
                    self.stdout.write(f'      {key}: {value}')
            
            # Check driver role
            is_driver = api_client.validate_driver_role(hr_data)
            if is_driver:
                self.stdout.write(self.style.SUCCESS('   ✓ User identified as driver'))
            else:
                self.stdout.write(self.style.ERROR('   ✗ User is not identified as driver'))
                self.stdout.write('   → Check driver role detection logic in backends.py')
        else:
            self.stdout.write(self.style.ERROR('   ✗ StyleHR API authentication failed'))
            return
        
        # Test 2: StyleHR Authentication Backend
        self.stdout.write('\n2. Testing StyleHR Authentication Backend...')
        backend = StyleHRAuthBackend()
        user = backend.authenticate(None, username=username, password=password)
        
        if user:
            self.stdout.write(self.style.SUCCESS('   ✓ Backend authentication successful'))
            self.display_user_info(user, '   ')
        else:
            self.stdout.write(self.style.ERROR('   ✗ Backend authentication failed'))
            return
        
        # Test 3: Django's authenticate function
        self.stdout.write('\n3. Testing Django authenticate() function...')
        django_user = authenticate(username=username, password=password)
        
        if django_user:
            self.stdout.write(self.style.SUCCESS('   ✓ Django authentication successful'))
            if django_user.pk == user.pk:
                self.stdout.write('   ✓ Same user returned by both methods')
            else:
                self.stdout.write(self.style.WARNING('   ! Different users returned'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ Django authentication failed'))
        
        # Test 4: User data validation
        self.stdout.write('\n4. Validating user data...')
        self.validate_user_data(user)
        
        # Test 5: Check if user can access system
        self.stdout.write('\n5. System access validation...')
        if user.is_active:
            self.stdout.write(self.style.SUCCESS('   ✓ User account is active'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ User account is inactive'))
        
        if user.user_type == 'driver':
            self.stdout.write(self.style.SUCCESS('   ✓ User has driver role'))
        else:
            self.stdout.write(self.style.WARNING(f'   ! User role is: {user.user_type}'))
        
        # Test 6: Check for any issues
        self.stdout.write('\n6. Checking for potential issues...')
        issues = []
        
        if not user.email:
            issues.append('Email address is missing')
        
        if not user.phone_number:
            issues.append('Phone number is missing')
        
        if user.user_type == 'driver':
            if not user.license_number:
                issues.append('License number is missing')
            
            if not user.license_expiry:
                issues.append('License expiry date is missing')
            elif not user.is_license_valid():
                issues.append('Driving license has expired')
        
        if issues:
            self.stdout.write(self.style.WARNING('   ! Issues found:'))
            for issue in issues:
                self.stdout.write(f'     - {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('   ✓ No issues found'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Authentication test completed successfully!'))
        self.stdout.write(f'User {username} can access the VMS system as a driver.')
    
    def display_user_info(self, user, indent=''):
        """Display user information"""
        self.stdout.write(f'{indent}→ User Details:')
        self.stdout.write(f'{indent}  Full Name: {user.get_full_name()}')
        self.stdout.write(f'{indent}  Username: {user.username}')
        self.stdout.write(f'{indent}  Email: {user.email}')
        self.stdout.write(f'{indent}  User Type: {user.get_user_type_display()}')
        self.stdout.write(f'{indent}  Phone: {user.phone_number or "Not provided"}')
        self.stdout.write(f'{indent}  Active: {user.is_active}')
        
        if user.user_type == 'driver':
            self.stdout.write(f'{indent}  License: {user.license_number or "Not provided"}')
            self.stdout.write(f'{indent}  License Expiry: {user.license_expiry or "Not provided"}')
            if user.license_expiry:
                self.stdout.write(f'{indent}  License Valid: {user.is_license_valid()}')
    
    def validate_user_data(self, user):
        """Validate user data completeness"""
        validations = [
            ('Username', user.username, True),
            ('Email', user.email, False),
            ('First Name', user.first_name, False),
            ('Last Name', user.last_name, False),
            ('Phone Number', user.phone_number, False),
        ]
        
        if user.user_type == 'driver':
            validations.extend([
                ('License Number', user.license_number, True),
                ('License Expiry', user.license_expiry, True),
            ])
        
        for field_name, field_value, is_required in validations:
            if field_value:
                self.stdout.write(f'   ✓ {field_name}: {field_value}')
            elif is_required:
                self.stdout.write(self.style.ERROR(f'   ✗ {field_name}: Missing (Required)'))
            else:
                self.stdout.write(self.style.WARNING(f'   ! {field_name}: Missing (Optional)'))
    
    def check_existing_users(self):
        """Check existing HR-authenticated users"""
        self.stdout.write(self.style.WARNING('Checking Existing HR-Authenticated Users...'))
        self.stdout.write('-' * 50)
        
        # Get all drivers
        all_drivers = User.objects.filter(user_type='driver')
        hr_drivers = all_drivers.filter(hr_authenticated=True) if hasattr(User, 'hr_authenticated') else []
        
        self.stdout.write(f'Total drivers in system: {all_drivers.count()}')
        if hasattr(User, 'hr_authenticated'):
            self.stdout.write(f'HR-authenticated drivers: {hr_drivers.count()}')
            
            if hr_drivers.exists():
                self.stdout.write('\nHR-Authenticated Drivers:')
                for user in hr_drivers[:10]:  # Show first 10
                    sync_status = ''
                    if hasattr(user, 'last_hr_sync') and user.last_hr_sync:
                        sync_status = f' (Last sync: {user.last_hr_sync.strftime("%Y-%m-%d %H:%M")})'
                    
                    self.stdout.write(f'  • {user.username} - {user.get_full_name()}{sync_status}')
                
                if hr_drivers.count() > 10:
                    self.stdout.write(f'  ... and {hr_drivers.count() - 10} more')
        
        # Check for users without email
        users_no_email = all_drivers.filter(email='')
        if users_no_email.exists():
            self.stdout.write(self.style.WARNING(f'\n⚠️  {users_no_email.count()} drivers without email addresses'))
        
        # Check for users with expired licenses
        from django.utils import timezone
        expired_licenses = all_drivers.filter(
            license_expiry__lt=timezone.now().date()
        ).exclude(license_expiry__isnull=True)
        
        if expired_licenses.exists():
            self.stdout.write(self.style.ERROR(f'\n❌ {expired_licenses.count()} drivers with expired licenses'))
        
        # Check for users with missing license info
        missing_license = all_drivers.filter(
            models.Q(license_number='') | models.Q(license_expiry__isnull=True)
        )
        
        if missing_license.exists():
            self.stdout.write(self.style.WARNING(f'\n⚠️  {missing_license.count()} drivers with incomplete license information'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ User check completed!'))

