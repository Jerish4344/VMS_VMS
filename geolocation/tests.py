"""
Tests for the geolocation module.
Run with: python manage.py test geolocation
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from vehicles.models import Vehicle, VehicleType
from .models import AiroTrackDevice, VehicleLocation, LocationHistory

User = get_user_model()


class AiroTrackDeviceModelTests(TestCase):
    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Truck', category='commercial')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Tata', model='Ace', year=2023,
            license_plate='TN01GE0001', vin='VINGEO00000000001',
            acquisition_date=date.today(),
        )

    def test_device_creation(self):
        device = AiroTrackDevice.objects.create(
            device_id='DEV001', name='Tracker 1',
            vehicle=self.vehicle, status='online',
        )
        self.assertEqual(device.device_id, 'DEV001')
        self.assertIn('Tracker 1', str(device))

    def test_is_online(self):
        device = AiroTrackDevice.objects.create(
            device_id='DEV002', vehicle=self.vehicle, status='online',
        )
        self.assertTrue(device.is_online())
        device.status = 'offline'
        self.assertFalse(device.is_online())

    def test_update_status(self):
        device = AiroTrackDevice.objects.create(
            device_id='DEV003', vehicle=self.vehicle, status='unknown',
        )
        device.update_status('online')
        device.refresh_from_db()
        self.assertEqual(device.status, 'online')
        self.assertIsNotNone(device.last_update)

    def test_unique_device_id(self):
        AiroTrackDevice.objects.create(device_id='DEV004')
        with self.assertRaises(Exception):
            AiroTrackDevice.objects.create(device_id='DEV004')


class VehicleLocationModelTests(TestCase):
    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Truck', category='commercial')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Ashok Leyland', model='Dost', year=2023,
            license_plate='TN01GE0002', vin='VINGEO00000000002',
            acquisition_date=date.today(),
        )
        self.device = AiroTrackDevice.objects.create(
            device_id='DEV010', vehicle=self.vehicle, status='online',
        )
        self.now = timezone.now()

    def test_location_creation(self):
        loc = VehicleLocation.objects.create(
            vehicle=self.vehicle, device=self.device,
            latitude=Decimal('13.0827000'), longitude=Decimal('80.2707000'),
            device_time=self.now, server_time=self.now,
        )
        self.assertIn('Ashok Leyland', str(loc))

    def test_coordinates(self):
        loc = VehicleLocation.objects.create(
            vehicle=self.vehicle, device=self.device,
            latitude=Decimal('13.0827000'), longitude=Decimal('80.2707000'),
            device_time=self.now, server_time=self.now,
        )
        self.assertEqual(loc.coordinates(), (13.0827, 80.2707))

    def test_to_geojson(self):
        loc = VehicleLocation.objects.create(
            vehicle=self.vehicle, device=self.device,
            latitude=Decimal('13.0827000'), longitude=Decimal('80.2707000'),
            speed=Decimal('45.50'), ignition=True,
            device_time=self.now, server_time=self.now,
        )
        geojson = loc.to_geojson()
        self.assertEqual(geojson['type'], 'Feature')
        self.assertEqual(geojson['geometry']['type'], 'Point')
        self.assertEqual(geojson['properties']['ignition'], True)


class LocationHistoryModelTests(TestCase):
    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Van', category='commercial')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Mahindra', model='Supro', year=2023,
            license_plate='TN01GE0003', vin='VINGEO00000000003',
            acquisition_date=date.today(),
        )
        self.device = AiroTrackDevice.objects.create(
            device_id='DEV020', vehicle=self.vehicle, status='online',
        )

    def test_history_creation(self):
        hist = LocationHistory.objects.create(
            vehicle=self.vehicle, device=self.device,
            latitude=Decimal('12.9716000'), longitude=Decimal('77.5946000'),
            device_time=timezone.now(),
        )
        self.assertIn('Mahindra', str(hist))

    def test_ordering(self):
        from datetime import timedelta
        now = timezone.now()
        old = LocationHistory.objects.create(
            vehicle=self.vehicle, device=self.device,
            latitude=Decimal('12.97'), longitude=Decimal('77.59'),
            device_time=now - timedelta(hours=1),
        )
        new = LocationHistory.objects.create(
            vehicle=self.vehicle, device=self.device,
            latitude=Decimal('12.98'), longitude=Decimal('77.60'),
            device_time=now,
        )
        qs = LocationHistory.objects.all()
        self.assertEqual(qs[0], new)


class GeolocationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='geoadmin', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        self.client.login(username='geoadmin', password='pass1234')

    def test_tracking_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('tracking_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_tracking_dashboard(self):
        response = self.client.get(reverse('tracking_dashboard'))
        self.assertEqual(response.status_code, 200)
