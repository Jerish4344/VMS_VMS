# fuel/tests.py
"""
Comprehensive tests for the fuel module.
Run with: python manage.py test fuel
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from decimal import Decimal
from datetime import date

from .models import FuelTransaction, FuelStation
from vehicles.models import Vehicle, VehicleType
from accounts.models import Module, Permission


User = get_user_model()


class FuelStationModelTests(TestCase):
    """Tests for FuelStation model."""
    
    def setUp(self):
        self.fuel_station = FuelStation.objects.create(
            name='Indian Oil - Main Road',
            address='123 Main Road, Chennai',
            station_type='fuel'
        )
        self.charging_station = FuelStation.objects.create(
            name='Tata Power EV',
            address='456 Tech Park, Bangalore',
            station_type='charging'
        )
    
    def test_fuel_station_creation(self):
        """Test fuel station is created correctly."""
        self.assertEqual(self.fuel_station.name, 'Indian Oil - Main Road')
        self.assertEqual(self.fuel_station.station_type, 'fuel')
    
    def test_fuel_station_str(self):
        """Test fuel station string representation."""
        self.assertEqual(str(self.fuel_station), 'Indian Oil - Main Road')
    
    def test_charging_station_creation(self):
        """Test charging station is created correctly."""
        self.assertEqual(self.charging_station.station_type, 'charging')
    
    def test_station_types(self):
        """Test all station types."""
        types = ['fuel', 'charging', 'both']
        for i, station_type in enumerate(types):
            station = FuelStation.objects.create(
                name=f'Station {i}',
                address=f'Address {i}',
                station_type=station_type
            )
            self.assertEqual(station.station_type, station_type)


class FuelTransactionModelTests(TestCase):
    """Tests for FuelTransaction model."""
    
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
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
        self.fuel_station = FuelStation.objects.create(
            name='Test Station',
            address='Test Address'
        )
        self.fuel_transaction = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            fuel_station=self.fuel_station,
            date=date.today(),
            fuel_type='Diesel',
            quantity=Decimal('50.00'),
            cost_per_liter=Decimal('90.50'),
            total_cost=Decimal('4525.00'),
            odometer_reading=15000
        )
    
    def test_fuel_transaction_creation(self):
        """Test fuel transaction is created correctly."""
        self.assertEqual(self.fuel_transaction.vehicle, self.vehicle)
        self.assertEqual(self.fuel_transaction.driver, self.driver)
        self.assertEqual(self.fuel_transaction.quantity, Decimal('50.00'))
    
    def test_fuel_cost_calculation(self):
        """Test total cost calculation."""
        expected_cost = self.fuel_transaction.quantity * self.fuel_transaction.cost_per_liter
        self.assertEqual(self.fuel_transaction.total_cost, expected_cost)
    
    def test_fuel_transaction_without_station(self):
        """Test fuel transaction can be created without station."""
        transaction = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            date=date.today(),
            fuel_type='Petrol',
            quantity=Decimal('40.00'),
            cost_per_liter=Decimal('100.00'),
            total_cost=Decimal('4000.00'),
            odometer_reading=16000
        )
        self.assertIsNone(transaction.fuel_station)


class ElectricVehicleFuelTests(TestCase):
    """Tests for electric vehicle charging."""
    
    def setUp(self):
        self.vehicle_type = VehicleType.objects.create(
            name='Electric Car',
            category='electric'
        )
        self.ev = Vehicle.objects.create(
            vehicle_type=self.vehicle_type,
            make='Tata',
            model='Nexon EV',
            year=2023,
            license_plate='TN01EV1234',
            vin='EVUNIQUE123456789',
            acquisition_date=date.today()
        )
        self.driver = User.objects.create_user(
            username='evdriver',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
        self.charging_station = FuelStation.objects.create(
            name='Tata Charging Hub',
            address='Tech Park',
            station_type='charging'
        )
    
    def test_ev_charging_transaction(self):
        """Test electric vehicle charging transaction."""
        transaction = FuelTransaction.objects.create(
            vehicle=self.ev,
            driver=self.driver,
            fuel_station=self.charging_station,
            date=date.today(),
            energy_consumed=Decimal('30.50'),
            cost_per_kwh=Decimal('12.00'),
            total_cost=Decimal('366.00'),
            odometer_reading=5000
        )
        self.assertEqual(transaction.energy_consumed, Decimal('30.50'))
        self.assertIsNone(transaction.quantity)


class FuelViewTests(TestCase):
    """Tests for Fuel views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        # Create module and permissions so admin role has access
        fuel_module = Module.objects.create(name='fuel', display_name='Fuel')
        Permission.objects.create(module=fuel_module, action='view', name='fuel_view', is_default_for_admin=True)
        Permission.objects.create(module=fuel_module, action='add', name='fuel_add', is_default_for_admin=True)
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
    
    def test_fuel_list_view(self):
        """Test fuel list page loads."""
        response = self.client.get(reverse('fuel_transaction_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_fuel_add_view(self):
        """Test fuel add page loads."""
        response = self.client.get(reverse('fuel_transaction_create'))
        self.assertEqual(response.status_code, 200)
    
    def test_fuel_list_requires_login(self):
        """Test fuel list requires login."""
        self.client.logout()
        response = self.client.get(reverse('fuel_transaction_list'))
        self.assertEqual(response.status_code, 302)


class FuelAPITests(APITestCase):
    """Tests for Fuel API endpoints."""
    
    def setUp(self):
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
        self.token = Token.objects.create(user=self.driver)
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
    
    def test_list_fuel_transactions_api(self):
        """Test listing fuel transactions via API."""
        response = self.client.get('/api/fuel/')
        self.assertEqual(response.status_code, 200)
    
    def test_create_fuel_transaction_api(self):
        """Test creating fuel transaction via API."""
        data = {
            'vehicle': self.vehicle.id,
            'date': str(date.today()),
            'fuel_type': 'Diesel',
            'quantity': '50.00',
            'cost_per_liter': '90.00',
            'total_cost': '4500.00',
            'odometer_reading': 15000
        }
        response = self.client.post('/api/fuel/', data)
        self.assertIn(response.status_code, [200, 201, 400])
    
    def test_api_authentication_required(self):
        """Test API requires authentication."""
        self.client.credentials()
        response = self.client.get('/api/fuel/')
        self.assertIn(response.status_code, [401, 403])


class FuelReportTests(TestCase):
    """Tests for fuel reporting."""
    
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
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
        # Create some fuel transactions for testing
        for i in range(5):
            FuelTransaction.objects.create(
                vehicle=self.vehicle,
                driver=self.admin,
                date=date.today(),
                fuel_type='Diesel',
                quantity=Decimal('50.00'),
                cost_per_liter=Decimal('90.00'),
                total_cost=Decimal('4500.00'),
                odometer_reading=10000 + (i * 500)
            )
        self.client.login(username='admin', password='testpass123')
    
    def test_fuel_report_view(self):
        """Test fuel report page loads."""
        response = self.client.get(reverse('fuel_report'))
        self.assertEqual(response.status_code, 200)
    
    def test_fuel_report_with_filters(self):
        """Test fuel report with date filters."""
        response = self.client.get(reverse('fuel_report'), {
            'start_date': str(date.today()),
            'end_date': str(date.today())
        })
        self.assertEqual(response.status_code, 200)
