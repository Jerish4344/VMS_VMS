# vehicles/tests.py
"""
Comprehensive tests for the vehicles module.
Run with: python manage.py test vehicles
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from datetime import date, timedelta

from .models import Vehicle, VehicleType, Firm
from accounts.models import Module, Permission


User = get_user_model()


class VehicleTypeModelTests(TestCase):
    """Tests for VehicleType model."""
    
    def setUp(self):
        self.car_type = VehicleType.objects.create(
            name='Car',
            description='Passenger cars',
            category='personal'
        )
        self.truck_type = VehicleType.objects.create(
            name='Truck',
            description='Commercial trucks',
            category='commercial'
        )
        self.ev_type = VehicleType.objects.create(
            name='Electric Car',
            description='Electric vehicles',
            category='electric'
        )
    
    def test_vehicle_type_creation(self):
        """Test vehicle type is created correctly."""
        self.assertEqual(self.car_type.name, 'Car')
        self.assertEqual(self.car_type.category, 'personal')
    
    def test_vehicle_type_str(self):
        """Test vehicle type string representation."""
        self.assertEqual(str(self.car_type), 'Car')
    
    def test_is_commercial(self):
        """Test is_commercial method."""
        self.assertFalse(self.car_type.is_commercial())
        self.assertTrue(self.truck_type.is_commercial())
    
    def test_is_electric(self):
        """Test is_electric method."""
        self.assertFalse(self.car_type.is_electric())
        self.assertTrue(self.ev_type.is_electric())


class FirmModelTests(TestCase):
    """Tests for Firm model."""
    
    def setUp(self):
        self.firm = Firm.objects.create(name='JIPL')
    
    def test_firm_creation(self):
        """Test firm is created correctly."""
        self.assertEqual(self.firm.name, 'JIPL')
    
    def test_firm_str(self):
        """Test firm string representation."""
        self.assertEqual(str(self.firm), 'JIPL')
    
    def test_unique_firm_name(self):
        """Test firm name must be unique."""
        with self.assertRaises(Exception):
            Firm.objects.create(name='JIPL')


class VehicleModelTests(TestCase):
    """Tests for Vehicle model."""
    
    def setUp(self):
        self.vehicle_type = VehicleType.objects.create(
            name='Car',
            category='personal'
        )
        self.firm = Firm.objects.create(name='TestFirm')
        
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Toyota',
            model='Camry',
            year=2023,
            license_plate='TN01AB1234',
            vin='1HGBH41JXMN109186',
            status='available',
            ownership_type='company',
            acquisition_date=date.today()
        )
        self.vehicle.firms.add(self.firm)
    
    def test_vehicle_creation(self):
        """Test vehicle is created correctly."""
        self.assertEqual(self.vehicle.make, 'Toyota')
        self.assertEqual(self.vehicle.model, 'Camry')
        self.assertEqual(self.vehicle.year, 2023)
        self.assertEqual(self.vehicle.status, 'available')
    
    def test_vehicle_str(self):
        """Test vehicle string representation."""
        expected = 'Toyota Camry (TN01AB1234)'
        self.assertIn('Toyota', str(self.vehicle))
    
    def test_vehicle_status_choices(self):
        """Test all vehicle status choices work."""
        statuses = ['available', 'in_use', 'maintenance', 'retired']
        for status in statuses:
            self.vehicle.status = status
            self.vehicle.save()
            self.assertEqual(self.vehicle.status, status)
    
    def test_unique_license_plate(self):
        """Test license plate must be unique."""
        with self.assertRaises(Exception):
            Vehicle.objects.create(
                vehicle_type=self.vehicle_type,
                make='Honda',
                model='Civic',
                year=2022,
                license_plate='TN01AB1234',  # Duplicate
                vin='UNIQUE123456789',
                acquisition_date=date.today()
            )
    
    def test_unique_vin(self):
        """Test VIN must be unique."""
        with self.assertRaises(Exception):
            Vehicle.objects.create(
                vehicle_type=self.vehicle_type,
                make='Honda',
                model='Civic',
                year=2022,
                license_plate='UNIQUE123',
                vin='1HGBH41JXMN109186',  # Duplicate
                acquisition_date=date.today()
            )
    
    def test_vehicle_firm_relationship(self):
        """Test vehicle can belong to multiple firms."""
        firm2 = Firm.objects.create(name='Kannammal')
        self.vehicle.firms.add(firm2)
        self.assertEqual(self.vehicle.firms.count(), 2)
    
    def test_vehicle_expiry_dates(self):
        """Test vehicle expiry date fields."""
        future_date = date.today() + timedelta(days=365)
        self.vehicle.insurance_expiry_date = future_date
        self.vehicle.fitness_expiry = future_date
        self.vehicle.permit_expiry = future_date
        self.vehicle.pollution_cert_expiry = future_date
        self.vehicle.save()
        
        self.assertEqual(self.vehicle.insurance_expiry_date, future_date)


class VehicleViewTests(TestCase):
    """Tests for Vehicle views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        # Create module and permissions so admin role has access
        vehicles_module = Module.objects.create(name='vehicles', display_name='Vehicles')
        Permission.objects.create(module=vehicles_module, action='view', name='vehicle_view', is_default_for_admin=True)
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
        self.client.login(username='testuser', password='testpass123')
    
    def test_vehicle_list_view(self):
        """Test vehicle list page loads."""
        response = self.client.get(reverse('vehicle_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_vehicle_detail_view(self):
        """Test vehicle detail page loads."""
        response = self.client.get(reverse('vehicle_detail', args=[self.vehicle.id]))
        self.assertEqual(response.status_code, 200)
    
    def test_vehicle_list_requires_login(self):
        """Test vehicle list requires login."""
        self.client.logout()
        response = self.client.get(reverse('vehicle_list'))
        self.assertEqual(response.status_code, 302)  # Redirects to login


class VehicleAPITests(APITestCase):
    """Tests for Vehicle API endpoints."""
    
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
            status='available',
            acquisition_date=date.today()
        )
    
    def test_list_vehicles_api(self):
        """Test listing vehicles via API."""
        response = self.client.get('/api/vehicles/')
        self.assertEqual(response.status_code, 200)
    
    def test_vehicle_detail_api(self):
        """Test getting vehicle detail via API."""
        response = self.client.get(f'/api/vehicles/{self.vehicle.id}/')
        self.assertEqual(response.status_code, 200)
    
    def test_api_authentication_required(self):
        """Test API requires authentication."""
        self.client.credentials()  # Remove auth
        response = self.client.get('/api/vehicles/')
        self.assertIn(response.status_code, [401, 403])


class VehicleOwnershipTests(TestCase):
    """Tests for vehicle ownership types."""
    
    def setUp(self):
        self.vehicle_type = VehicleType.objects.create(name='Bike')
        self.user = User.objects.create_user(
            username='staff',
            password='testpass123',
            user_type='personal_vehicle_staff',
            approval_status='approved'
        )
    
    def test_company_vehicle(self):
        """Test company vehicle creation."""
        vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Honda',
            model='Activa',
            year=2023,
            license_plate='TN01CD5678',
            vin='UNIQUE123456789AB',
            ownership_type='company',
            acquisition_date=date.today()
        )
        self.assertEqual(vehicle.ownership_type, 'company')
    
    def test_personal_vehicle(self):
        """Test personal vehicle creation with owner."""
        vehicle = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='TVS',
            model='Jupiter',
            year=2022,
            license_plate='TN01EF9012',
            vin='UNIQUE987654321AB',
            ownership_type='personal',
            owned_by=self.user,
            reimbursement_rate_per_km=5.00,
            acquisition_date=date.today()
        )
        self.assertEqual(vehicle.ownership_type, 'personal')
        self.assertEqual(vehicle.owned_by, self.user)
        self.assertEqual(vehicle.reimbursement_rate_per_km, 5.00)
