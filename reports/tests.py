"""
Tests for the reports module.
Run with: python manage.py test reports
"""
from datetime import date, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from vehicles.models import Vehicle, VehicleType

User = get_user_model()


class ReportViewTests(TestCase):
    """Tests for report views."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='rptadmin', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01RP0001', vin='VINRPT00000000001',
            status='available', ownership_type='company',
            acquisition_date=date.today(),
        )
        self.client.login(username='rptadmin', password='pass1234')

    def test_vehicle_report_view(self):
        response = self.client.get(reverse('vehicle_report'))
        self.assertEqual(response.status_code, 200)

    def test_driver_report_view(self):
        response = self.client.get(reverse('driver_report'))
        self.assertEqual(response.status_code, 200)

    def test_maintenance_report_view(self):
        response = self.client.get(reverse('maintenance_report'))
        self.assertEqual(response.status_code, 200)

    def test_fuel_report_view(self):
        response = self.client.get(reverse('fuel_report'))
        self.assertEqual(response.status_code, 200)

    def test_reports_require_login(self):
        self.client.logout()
        for url_name in ['vehicle_report', 'driver_report', 'maintenance_report', 'fuel_report']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302, f'{url_name} should require login')

    def test_vehicle_report_date_filter(self):
        start = (date.today() - timedelta(days=30)).isoformat()
        end = date.today().isoformat()
        response = self.client.get(reverse('vehicle_report'), {
            'start_date': start, 'end_date': end,
        })
        self.assertEqual(response.status_code, 200)

    def test_vehicle_report_vehicle_filter(self):
        response = self.client.get(reverse('vehicle_report'), {
            'vehicle': self.vehicle.id,
        })
        self.assertEqual(response.status_code, 200)

    def test_vehicle_report_export_csv(self):
        response = self.client.get(reverse('vehicle_report'), {
            'export': 'csv',
        })
        self.assertIn(response.status_code, [200, 302])

    def test_vehicle_report_export_excel(self):
        response = self.client.get(reverse('vehicle_report'), {
            'export': 'excel',
        })
        self.assertIn(response.status_code, [200, 302])


class ReportAccessControlTests(TestCase):
    """Test that non-admin users get appropriate access."""

    def setUp(self):
        self.client = Client()

    def test_driver_cannot_access_reports(self):
        User.objects.create_user(
            username='driver1', password='pass1234',
            user_type='driver', approval_status='approved',
        )
        self.client.login(username='driver1', password='pass1234')
        response = self.client.get(reverse('vehicle_report'))
        # Should redirect or return 403
        self.assertIn(response.status_code, [302, 403])
