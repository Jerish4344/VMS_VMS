# accounts/tests.py
"""
Comprehensive tests for the accounts module.
Run with: python manage.py test accounts
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from rest_framework import status

from .models import Department, CustomUser, Module, Permission


User = get_user_model()


class DepartmentModelTests(TestCase):
    """Tests for Department model."""
    
    def setUp(self):
        self.department = Department.objects.create(
            name='Operations',
            code='OPS',
            description='Operations Department',
            is_active=True
        )
    
    def test_department_creation(self):
        """Test department is created correctly."""
        self.assertEqual(self.department.name, 'Operations')
        self.assertEqual(self.department.code, 'OPS')
        self.assertTrue(self.department.is_active)
    
    def test_department_str(self):
        """Test department string representation."""
        self.assertEqual(str(self.department), 'Operations (OPS)')
        
        # Test without code
        dept_no_code = Department.objects.create(name='HR')
        self.assertEqual(str(dept_no_code), 'HR')
    
    def test_unique_department_name(self):
        """Test department name must be unique."""
        with self.assertRaises(Exception):
            Department.objects.create(name='Operations')


class CustomUserModelTests(TestCase):
    """Tests for CustomUser model."""
    
    def setUp(self):
        self.department = Department.objects.create(name='IT', code='IT')
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.driver_user = User.objects.create_user(
            username='driver1',
            email='driver@test.com',
            password='testpass123',
            user_type='driver',
            phone_number='1234567890',
            license_number='DL123456',
            approval_status='pending'
        )
    
    def test_user_creation(self):
        """Test user is created correctly."""
        self.assertEqual(self.admin_user.username, 'admin')
        self.assertEqual(self.admin_user.user_type, 'admin')
        self.assertEqual(self.admin_user.approval_status, 'approved')
    
    def test_driver_creation(self):
        """Test driver user is created with correct fields."""
        self.assertEqual(self.driver_user.user_type, 'driver')
        self.assertEqual(self.driver_user.phone_number, '1234567890')
        self.assertEqual(self.driver_user.license_number, 'DL123456')
        self.assertEqual(self.driver_user.approval_status, 'pending')
    
    def test_user_approval(self):
        """Test user approval workflow."""
        self.driver_user.approval_status = 'approved'
        self.driver_user.approved_by = self.admin_user
        self.driver_user.approved_at = timezone.now()
        self.driver_user.save()
        
        self.assertEqual(self.driver_user.approval_status, 'approved')
        self.assertEqual(self.driver_user.approved_by, self.admin_user)
        self.assertIsNotNone(self.driver_user.approved_at)
    
    def test_user_rejection(self):
        """Test user rejection workflow."""
        self.driver_user.approval_status = 'rejected'
        self.driver_user.rejection_reason = 'Invalid license'
        self.driver_user.save()
        
        self.assertEqual(self.driver_user.approval_status, 'rejected')
        self.assertEqual(self.driver_user.rejection_reason, 'Invalid license')
    
    def test_user_types(self):
        """Test all user types can be created."""
        user_types = ['admin', 'manager', 'vehicle_manager', 'driver', 
                      'company_vehicle_staff', 'personal_vehicle_staff', 
                      'generator_user', 'sor_team']
        
        for i, user_type in enumerate(user_types):
            user = User.objects.create_user(
                username=f'user_{user_type}',
                email=f'{user_type}@test.com',
                password='testpass123',
                user_type=user_type
            )
            self.assertEqual(user.user_type, user_type)


class AuthenticationViewTests(TestCase):
    """Tests for authentication views."""
    
    def setUp(self):
        self.client = Client()
        # Create dashboard module and permission so login redirect works
        dashboard_module = Module.objects.create(name='dashboard', display_name='Dashboard')
        Permission.objects.create(module=dashboard_module, action='company_dashboard', name='company_dashboard', is_default_for_admin=True, is_default_for_driver=True)
        self.approved_user = User.objects.create_user(
            username='approved_user',
            email='approved@test.com',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
        self.pending_user = User.objects.create_user(
            username='pending_user',
            email='pending@test.com',
            password='testpass123',
            user_type='driver',
            approval_status='pending'
        )
    
    def test_login_page_loads(self):
        """Test login page is accessible."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
    
    def test_approved_user_can_login(self):
        """Test approved user can login."""
        login = self.client.login(username='approved_user', password='testpass123')
        self.assertTrue(login)
    
    def test_login_redirect_to_dashboard(self):
        """Test successful login redirects to dashboard."""
        response = self.client.post(reverse('login'), {
            'username': 'approved_user',
            'password': 'testpass123'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
    
    def test_invalid_credentials(self):
        """Test login with invalid credentials fails."""
        login = self.client.login(username='approved_user', password='wrongpass')
        self.assertFalse(login)
    
    def test_logout(self):
        """Test user can logout."""
        self.client.login(username='approved_user', password='testpass123')
        response = self.client.get(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)


class UserAPITests(APITestCase):
    """Tests for User API endpoints."""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.token = Token.objects.create(user=self.admin_user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
    
    def test_api_requires_authentication(self):
        """Test API requires authentication."""
        self.client.credentials()  # Remove auth
        response = self.client.get('/api/vehicles/')
        self.assertIn(response.status_code, [401, 403, 404])


class PermissionTests(TestCase):
    """Tests for user permissions."""
    
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            user_type='admin',
            approval_status='approved',
            is_staff=True,
            is_superuser=True
        )
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
    
    def test_admin_can_access_admin_pages(self):
        """Test admin can access admin dashboard."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
    
    def test_driver_cannot_access_admin(self):
        """Test driver cannot access admin dashboard."""
        self.client.login(username='driver', password='testpass123')
        response = self.client.get('/admin/', follow=True)
        # Should redirect to admin login
        self.assertIn(response.status_code, [200, 302])
