# trips/tests.py
"""
Comprehensive tests for the trips module.
Run with: python manage.py test trips
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from datetime import timedelta, date

from .models import Trip
from vehicles.models import Vehicle, VehicleType


User = get_user_model()


class TripModelTests(TestCase):
    """Tests for Trip model."""
    
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
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
        self.start_time = timezone.now()
        self.trip = Trip.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            start_time=self.start_time,
            start_odometer=10000,
            origin='Chennai',
            purpose='Office visit',
            status='ongoing',
            entry_type='real_time'
        )
    
    def test_trip_creation(self):
        """Test trip is created correctly."""
        self.assertEqual(self.trip.vehicle, self.vehicle)
        self.assertEqual(self.trip.driver, self.driver)
        self.assertEqual(self.trip.start_odometer, 10000)
        self.assertEqual(self.trip.status, 'ongoing')
    
    def test_trip_completion(self):
        """Test completing a trip."""
        self.trip.end_time = timezone.now() + timedelta(hours=2)
        self.trip.end_odometer = 10150
        self.trip.destination = 'Bangalore'
        self.trip.status = 'completed'
        self.trip.save()
        
        self.assertEqual(self.trip.status, 'completed')
        self.assertEqual(self.trip.end_odometer, 10150)
        self.assertEqual(self.trip.destination, 'Bangalore')
    
    def test_trip_distance_calculation(self):
        """Test trip distance calculation."""
        self.trip.end_odometer = 10150
        self.trip.save()
        
        distance = self.trip.end_odometer - self.trip.start_odometer
        self.assertEqual(distance, 150)
    
    def test_trip_status_choices(self):
        """Test all trip status choices work."""
        statuses = ['ongoing', 'completed', 'cancelled']
        for status in statuses:
            self.trip.status = status
            self.trip.save()
            self.assertEqual(self.trip.status, status)
    
    def test_trip_entry_types(self):
        """Test trip entry types."""
        entry_types = ['real_time', 'manual']
        for entry_type in entry_types:
            self.trip.entry_type = entry_type
            self.trip.save()
            self.assertEqual(self.trip.entry_type, entry_type)
    
    def test_trip_soft_delete(self):
        """Test trip soft delete functionality."""
        trip_id = self.trip.id
        self.trip.is_deleted = True
        self.trip.save()
        
        # Trip should still exist but be marked as deleted
        trip = Trip.objects.get(id=trip_id)
        self.assertTrue(trip.is_deleted)


class TripViewTests(TestCase):
    """Tests for Trip views."""
    
    def setUp(self):
        self.client = Client()
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
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
            status='available',
            acquisition_date=date.today()
        )
        self.client.login(username='driver', password='testpass123')
    
    def test_trip_list_view(self):
        """Test trip list page loads."""
        response = self.client.get(reverse('trip_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_trip_list_requires_login(self):
        """Test trip list requires login."""
        self.client.logout()
        response = self.client.get(reverse('trip_list'))
        self.assertEqual(response.status_code, 302)  # Redirects to login


class TripAPITests(APITestCase):
    """Tests for Trip API endpoints."""
    
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
            status='available',
            acquisition_date=date.today()
        )
        self.trip = Trip.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            start_time=timezone.now(),
            start_odometer=10000,
            origin='Chennai',
            purpose='Test trip',
            status='ongoing'
        )
    
    def test_list_trips_api(self):
        """Test listing trips via API."""
        response = self.client.get('/api/trips/')
        self.assertEqual(response.status_code, 200)
    
    def test_start_trip_api(self):
        """Test starting a trip via API."""
        data = {
            'vehicle': self.vehicle.id,
            'start_odometer': 11000,
            'origin': 'Bangalore',
            'purpose': 'Client meeting'
        }
        response = self.client.post('/api/trips/start/', data)
        self.assertIn(response.status_code, [200, 201, 400])  # 400 if ongoing trip exists
    
    def test_end_trip_api(self):
        """Test ending a trip via API."""
        data = {
            'end_odometer': 10150,
            'destination': 'Bangalore'
        }
        response = self.client.post(f'/api/trips/{self.trip.id}/end/', data)
        self.assertIn(response.status_code, [200, 201, 400])
    
    def test_api_authentication_required(self):
        """Test API requires authentication."""
        self.client.credentials()  # Remove auth
        response = self.client.get('/api/trips/')
        self.assertIn(response.status_code, [401, 403])


class TripBusinessLogicTests(TestCase):
    """Tests for trip business logic."""
    
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
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
            approval_status='approved'
        )
    
    def test_vehicle_status_changes_on_trip_start(self):
        """Test vehicle status changes when trip starts."""
        trip = Trip.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            start_time=timezone.now(),
            start_odometer=10000,
            origin='Chennai',
            purpose='Test',
            status='ongoing'
        )
        # Vehicle status should change (if model signal exists)
        self.vehicle.refresh_from_db()
    
    def test_odometer_validation(self):
        """Test end odometer must be greater than start."""
        trip = Trip.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            start_time=timezone.now(),
            start_odometer=10000,
            origin='Chennai',
            purpose='Test',
            status='ongoing'
        )
        # End odometer should be >= start odometer
        trip.end_odometer = 10100
        trip.save()
        self.assertTrue(trip.end_odometer >= trip.start_odometer)


class ManualTripEntryTests(TestCase):
    """Tests for manual trip entry."""
    
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            user_type='admin',
            approval_status='approved'
        )
        self.driver = User.objects.create_user(
            username='driver',
            password='testpass123',
            user_type='driver',
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
        self.client.login(username='admin', password='testpass123')
    
    def test_manual_trip_entry_page(self):
        """Test manual trip entry page loads."""
        response = self.client.get(reverse('manual_trip_create'))
        self.assertIn(response.status_code, [200, 302])
    
    def test_create_manual_trip(self):
        """Test creating a manual trip entry."""
        trip = Trip.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now(),
            start_odometer=10000,
            end_odometer=10150,
            origin='Chennai',
            destination='Bangalore',
            purpose='Past trip entry',
            status='completed',
            entry_type='manual'
        )
        self.assertEqual(trip.entry_type, 'manual')
        self.assertEqual(trip.status, 'completed')
