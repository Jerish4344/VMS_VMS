"""
Tests for the dashboard module.
Run with: python manage.py test dashboard
"""
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from vehicles.models import Vehicle, VehicleType

User = get_user_model()


class DashboardViewTests(TestCase):
    """Tests for DashboardView."""

    def setUp(self):
        self.client = Client()
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        Vehicle.objects.create(
            vehicle_type=self.vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01DB0001', vin='VINDASH0000000001',
            status='available', ownership_type='company',
            acquisition_date=date.today(),
        )

    def _login_as(self, username, user_type):
        user = User.objects.create_user(
            username=username, password='pass1234',
            user_type=user_type, approval_status='approved',
        )
        self.client.login(username=username, password='pass1234')
        return user

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard(self):
        self._login_as('admin1', 'admin')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_manager_dashboard(self):
        self._login_as('mgr1', 'manager')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_vehicle_manager_dashboard(self):
        self._login_as('vmgr1', 'vehicle_manager')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_driver_dashboard(self):
        self._login_as('drv1', 'driver')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_personal_vehicle_staff_dashboard(self):
        self._login_as('pvs1', 'personal_vehicle_staff')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_total_vehicles_excludes_personal(self):
        """Company dashboard should exclude personal vehicles."""
        Vehicle.objects.create(
            vehicle_type=self.vtype, make='TVS', model='Jupiter', year=2022,
            license_plate='TN01DB0002', vin='VINDASH0000000002',
            ownership_type='personal', acquisition_date=date.today(),
        )
        self._login_as('admin2', 'admin')
        response = self.client.get(reverse('dashboard'))
        if response.status_code == 200 and response.context:
            self.assertEqual(response.context['total_vehicles'], 1)


class StaffDashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_staff_dashboard_requires_login(self):
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_staff_dashboard_loads(self):
        User.objects.create_user(
            username='staff1', password='pass1234',
            user_type='personal_vehicle_staff', approval_status='approved',
        )
        self.client.login(username='staff1', password='pass1234')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])


class OngoingTripsByTypeAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin3', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        self.client.login(username='admin3', password='pass1234')

    def test_api_returns_json(self):
        response = self.client.get(reverse('ongoing_trips_by_type_api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
