"""
Tests for the core API module.
Run with: python manage.py test core
"""
from datetime import date
from django.test import TestCase
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token

from vehicles.models import Vehicle, VehicleType
from core.serializers import (
    LoginSerializer, UserSerializer, VehicleSerializer,
    TripSerializer, DocumentSerializer,
)

User = get_user_model()


class LoginSerializerTests(TestCase):
    def test_valid_data(self):
        s = LoginSerializer(data={'username': 'user', 'password': 'pass'})
        self.assertTrue(s.is_valid())

    def test_missing_password(self):
        s = LoginSerializer(data={'username': 'user'})
        self.assertFalse(s.is_valid())
        self.assertIn('password', s.errors)


class UserSerializerTests(TestCase):
    def test_full_name_field(self):
        user = User.objects.create_user(
            username='testuser', password='pass1234',
            first_name='John', last_name='Doe',
            user_type='admin', approval_status='approved',
        )
        data = UserSerializer(user).data
        self.assertEqual(data['full_name'], 'John Doe')

    def test_read_only_fields(self):
        user = User.objects.create_user(
            username='testuser2', password='pass1234',
            user_type='driver', approval_status='approved',
        )
        data = UserSerializer(user).data
        self.assertIn('id', data)
        self.assertIn('user_type', data)


class VehicleSerializerTests(TestCase):
    def test_serialize_vehicle(self):
        vtype = VehicleType.objects.create(name='Car', category='personal')
        vehicle = Vehicle.objects.create(
            vehicle_type=vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01AA0001', vin='VINCORE00000000001',
            status='available', acquisition_date=date.today(),
        )
        data = VehicleSerializer(vehicle).data
        self.assertEqual(data['license_plate'], 'TN01AA0001')
        self.assertEqual(data['status'], 'available')


class AuthAPITests(APITestCase):
    """Test authentication API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='apiuser', password='testpass123',
            user_type='admin', approval_status='approved',
        )
        self.token = Token.objects.create(user=self.user)

    def test_login_success(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'apiuser', 'password': 'testpass123',
        })
        self.assertIn(response.status_code, [200, 201])
        self.assertIn('token', response.data)

    def test_login_wrong_password(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'apiuser', 'password': 'wrongpassword',
        })
        self.assertIn(response.status_code, [400, 401])

    def test_profile_authenticated(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'apiuser')

    def test_profile_unauthenticated(self):
        response = self.client.get('/api/auth/profile/')
        self.assertIn(response.status_code, [401, 403])

    def test_logout(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.post('/api/auth/logout/')
        self.assertIn(response.status_code, [200, 204])


class VehicleAPITests(APITestCase):
    """Test vehicle API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser2', password='testpass123',
            user_type='admin', approval_status='approved',
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01AA0002', vin='VINCORE00000000002',
            status='available', acquisition_date=date.today(),
        )

    def test_list_vehicles(self):
        response = self.client.get('/api/vehicles/')
        self.assertEqual(response.status_code, 200)

    def test_vehicle_detail(self):
        response = self.client.get(f'/api/vehicles/{self.vehicle.id}/')
        self.assertEqual(response.status_code, 200)

    def test_api_requires_auth(self):
        self.client.credentials()
        response = self.client.get('/api/vehicles/')
        self.assertIn(response.status_code, [401, 403])


class DashboardAPITests(APITestCase):
    """Test dashboard API endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dashuser', password='testpass123',
            user_type='admin', approval_status='approved',
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_dashboard_stats(self):
        response = self.client.get('/api/dashboard/stats/')
        self.assertIn(response.status_code, [200, 403])

    def test_dashboard_requires_auth(self):
        self.client.credentials()
        response = self.client.get('/api/dashboard/stats/')
        self.assertIn(response.status_code, [401, 403])
