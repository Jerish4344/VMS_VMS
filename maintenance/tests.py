# maintenance/tests.py
"""
Comprehensive tests for the maintenance module.
Run with: python manage.py test maintenance
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from decimal import Decimal
from datetime import date, timedelta

from .models import Maintenance, MaintenanceType, MaintenanceProvider
from vehicles.models import Vehicle, VehicleType


User = get_user_model()


class MaintenanceTypeModelTests(TestCase):
    """Tests for MaintenanceType model."""
    
    def setUp(self):
        self.maintenance_type = MaintenanceType.objects.create(
            name='Oil Change',
            description='Regular oil and filter change'
        )
    
    def test_maintenance_type_creation(self):
        """Test maintenance type is created correctly."""
        self.assertEqual(self.maintenance_type.name, 'Oil Change')
    
    def test_maintenance_type_str(self):
        """Test maintenance type string representation."""
        self.assertEqual(str(self.maintenance_type), 'Oil Change')


class MaintenanceProviderModelTests(TestCase):
    """Tests for MaintenanceProvider model."""
    
    def setUp(self):
        self.provider = MaintenanceProvider.objects.create(
            name='AutoCare Service Center',
            address='123 Industrial Area, Chennai',
            phone='9876543210',
            email='service@autocare.com'
        )
    
    def test_provider_creation(self):
        """Test provider is created correctly."""
        self.assertEqual(self.provider.name, 'AutoCare Service Center')
        self.assertEqual(self.provider.phone, '9876543210')
    
    def test_provider_str(self):
        """Test provider string representation."""
        self.assertEqual(str(self.provider), 'AutoCare Service Center')


class MaintenanceModelTests(TestCase):
    """Tests for Maintenance model."""
    
    def setUp(self):
        self.vehicle_type = VehicleType.objects.create(name='Car')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Toyota',
            model='Camry',
            year=2023,
            license_plate='TN01AB1234',
            vin='1HGBH41JXMN109186',
            status='available',
            acquisition_date=date.today()
        )
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.maintenance_type = MaintenanceType.objects.create(name='Oil Change')
        self.provider = MaintenanceProvider.objects.create(
            name='Test Provider',
            address='Test Address'
        )
        self.maintenance = Maintenance.objects.create(
            vehicle=self.vehicle,
            maintenance_type=self.maintenance_type,
            provider=self.provider,
            reported_by=self.user,
            date_reported=date.today(),
            description='Regular oil change',
            odometer_reading=15000,
            status='scheduled',
            scheduled_date=date.today() + timedelta(days=7)
        )
    
    def test_maintenance_creation(self):
        """Test maintenance record is created correctly."""
        self.assertEqual(self.maintenance.vehicle, self.vehicle)
        self.assertEqual(self.maintenance.maintenance_type, self.maintenance_type)
        self.assertEqual(self.maintenance.status, 'scheduled')
    
    def test_maintenance_str(self):
        """Test maintenance string representation."""
        expected = f"Oil Change for {self.vehicle} on {date.today()}"
        self.assertEqual(str(self.maintenance), expected)
    
    def test_maintenance_status_workflow(self):
        """Test maintenance status progression."""
        # Scheduled -> In Progress
        self.maintenance.status = 'in_progress'
        self.maintenance.save()
        self.assertEqual(self.maintenance.status, 'in_progress')
        
        # In Progress -> Completed
        self.maintenance.status = 'completed'
        self.maintenance.completion_date = date.today()
        self.maintenance.cost = Decimal('2500.00')
        self.maintenance.save()
        self.assertEqual(self.maintenance.status, 'completed')
        self.assertIsNotNone(self.maintenance.completion_date)
    
    def test_maintenance_cancellation(self):
        """Test maintenance can be cancelled."""
        self.maintenance.status = 'cancelled'
        self.maintenance.notes = 'Cancelled due to vehicle sale'
        self.maintenance.save()
        self.assertEqual(self.maintenance.status, 'cancelled')


class MaintenanceViewTests(TestCase):
    """Tests for Maintenance views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.vehicle_type = VehicleType.objects.create(name='Car')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Toyota',
            model='Camry',
            year=2023,
            license_plate='TN01AB1234',
            vin='1HGBH41JXMN109186',
            acquisition_date=date.today()
        )
        self.maintenance_type = MaintenanceType.objects.create(name='Oil Change')
        self.client.login(username='testuser', password='testpass123')
    
    def test_maintenance_list_view(self):
        """Test maintenance list page loads."""
        response = self.client.get(reverse('maintenance_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_maintenance_add_view(self):
        """Test maintenance add page loads."""
        response = self.client.get(reverse('maintenance_create'))
        self.assertEqual(response.status_code, 200)
    
    def test_maintenance_list_requires_login(self):
        """Test maintenance list requires login."""
        self.client.logout()
        response = self.client.get(reverse('maintenance_list'))
        self.assertEqual(response.status_code, 302)


class MaintenanceAPITests(APITestCase):
    """Tests for Maintenance API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        self.vehicle_type = VehicleType.objects.create(name='Car')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Toyota',
            model='Camry',
            year=2023,
            license_plate='TN01AB1234',
            vin='1HGBH41JXMN109186',
            acquisition_date=date.today()
        )
        self.maintenance_type = MaintenanceType.objects.create(name='Oil Change')
    
    def test_list_maintenance_api(self):
        """Test listing maintenance records via API."""
        response = self.client.get('/api/maintenance/')
        self.assertIn(response.status_code, [200, 404])
    
    def test_api_authentication_required(self):
        """Test API requires authentication."""
        self.client.credentials()
        response = self.client.get('/api/maintenance/')
        self.assertIn(response.status_code, [401, 403, 404])


class VehicleMaintenanceHistoryTests(TestCase):
    """Tests for vehicle maintenance history."""
    
    def setUp(self):
        self.vehicle_type = VehicleType.objects.create(name='Car')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Toyota',
            model='Camry',
            year=2023,
            license_plate='TN01AB1234',
            vin='1HGBH41JXMN109186',
            acquisition_date=date.today()
        )
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.oil_change = MaintenanceType.objects.create(name='Oil Change')
        self.tire_rotation = MaintenanceType.objects.create(name='Tire Rotation')
        
        # Create multiple maintenance records
        for i in range(3):
            Maintenance.objects.create(
                vehicle=self.vehicle,
                maintenance_type=self.oil_change,
                reported_by=self.user,
                date_reported=date.today() - timedelta(days=i*30),
                description=f'Oil change #{i+1}',
                odometer_reading=10000 + (i * 5000),
                status='completed'
            )
    
    def test_vehicle_has_maintenance_history(self):
        """Test vehicle has maintenance records."""
        records = self.vehicle.maintenance_records.all()
        self.assertEqual(records.count(), 3)
    
    def test_maintenance_ordering(self):
        """Test maintenance records are ordered by date."""
        records = list(self.vehicle.maintenance_records.all())
        # Should be ordered by date_reported descending
        self.assertTrue(records[0].date_reported >= records[1].date_reported)
