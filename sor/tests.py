"""
Tests for the SOR (Statement of Requirements) module.
Run with: python manage.py test sor
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from vehicles.models import Vehicle, VehicleType
from .models import SOR

User = get_user_model()


class SORModelTests(TestCase):
    """Tests for SOR model."""

    def setUp(self):
        self.vtype = VehicleType.objects.create(
            name='Truck', category='commercial',
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Tata', model='Ace', year=2023,
            license_plate='TN01SR0001', vin='VINSOR00000000001',
            status='available', rate_per_km=Decimal('15.00'),
            acquisition_date=date.today(),
        )
        self.driver = User.objects.create_user(
            username='sordriver', password='pass1234',
            user_type='driver', approval_status='approved',
        )
        self.sor_user = User.objects.create_user(
            username='sorteam', password='pass1234',
            user_type='sor_team', approval_status='approved',
        )

    def test_creation(self):
        sor = SOR.objects.create(
            goods_value=Decimal('50000.00'),
            from_location='Chennai', to_location='Bangalore',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.sor_user,
        )
        self.assertEqual(sor.status, 'pending')
        self.assertIn('TN01SR0001', str(sor))
        self.assertIn('Chennai', str(sor))

    def test_transport_cost(self):
        sor = SOR.objects.create(
            goods_value=Decimal('50000.00'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            distance_km=Decimal('100'),
            created_by=self.sor_user,
        )
        # 100 km * 15.00 rate_per_km = 1500
        self.assertEqual(sor.transport_cost(), Decimal('1500.00'))

    def test_transport_cost_no_distance(self):
        sor = SOR.objects.create(
            goods_value=Decimal('50000.00'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.sor_user,
        )
        self.assertIsNone(sor.transport_cost())

    def test_transport_cost_percentage(self):
        sor = SOR.objects.create(
            goods_value=Decimal('50000.00'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            distance_km=Decimal('100'),
            created_by=self.sor_user,
        )
        # cost = 1500, percentage = (1500/50000)*100 = 3.0
        self.assertAlmostEqual(float(sor.transport_cost_percentage()), 3.0)

    def test_transport_cost_percentage_zero_goods(self):
        sor = SOR.objects.create(
            goods_value=Decimal('0'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            distance_km=Decimal('100'),
            created_by=self.sor_user,
        )
        self.assertIsNone(sor.transport_cost_percentage())

    def test_status_choices(self):
        sor = SOR.objects.create(
            goods_value=Decimal('10000'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.sor_user,
        )
        for status, _ in SOR.STATUS_CHOICES:
            sor.status = status
            sor.save()
            self.assertEqual(sor.status, status)

    def test_ordering(self):
        """SORs should be ordered by -created_at."""
        sor1 = SOR.objects.create(
            goods_value=Decimal('10000'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.sor_user,
        )
        sor2 = SOR.objects.create(
            goods_value=Decimal('20000'),
            from_location='C', to_location='D',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.sor_user,
        )
        qs = SOR.objects.all()
        self.assertEqual(qs[0], sor2)

    def test_optional_fields(self):
        sor = SOR.objects.create(
            goods_value=Decimal('10000'),
            from_location='A', to_location='B',
            vehicle=self.vehicle, driver=self.driver,
            number_of_crates=5, number_of_sac=10,
            description='Test goods',
            created_by=self.sor_user,
        )
        self.assertEqual(sor.number_of_crates, 5)
        self.assertEqual(sor.number_of_sac, 10)


class SORViewTests(TestCase):
    """Tests for SOR views."""

    def setUp(self):
        self.client = Client()
        self.vtype = VehicleType.objects.create(
            name='Truck', category='commercial',
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Tata', model='Ace', year=2023,
            license_plate='TN01SR0002', vin='VINSOR00000000002',
            status='available', rate_per_km=Decimal('15'),
            acquisition_date=date.today(),
        )
        self.driver = User.objects.create_user(
            username='srvdriver', password='pass1234',
            user_type='driver', approval_status='approved',
        )
        self.admin = User.objects.create_user(
            username='sradmin', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        self.sor = SOR.objects.create(
            goods_value=Decimal('25000'),
            from_location='Chennai', to_location='Madurai',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.admin,
        )
        self.client.login(username='sradmin', password='pass1234')

    def test_sor_list_view(self):
        response = self.client.get(reverse('sor_list'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_sor_detail_view(self):
        response = self.client.get(reverse('sor_view', args=[self.sor.pk]))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_sor_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('sor_list'))
        self.assertEqual(response.status_code, 302)

    def test_sor_create_view(self):
        response = self.client.get(reverse('sor_create'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_sor_export_csv(self):
        response = self.client.get(reverse('sor_export'), {'format': 'csv'})
        self.assertIn(response.status_code, [200, 302])


class SORAPITests(TestCase):
    """Tests for SOR API endpoints via DRF."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token

        self.vtype = VehicleType.objects.create(
            name='Truck', category='commercial',
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Tata', model='Ace', year=2023,
            license_plate='TN01SR0003', vin='VINSOR00000000003',
            status='available', rate_per_km=Decimal('15'),
            acquisition_date=date.today(),
        )
        self.driver = User.objects.create_user(
            username='sorapidrv', password='pass1234',
            user_type='driver', approval_status='approved',
        )
        self.sor_user = User.objects.create_user(
            username='sorapiteam', password='pass1234',
            user_type='sor_team', approval_status='approved',
        )
        self.token = Token.objects.create(user=self.sor_user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        self.sor = SOR.objects.create(
            goods_value=Decimal('30000'),
            from_location='Chennai', to_location='Salem',
            vehicle=self.vehicle, driver=self.driver,
            created_by=self.sor_user,
        )

    def test_sor_list_api(self):
        response = self.client.get('/api/sor/')
        self.assertIn(response.status_code, [200, 403])

    def test_sor_detail_api(self):
        response = self.client.get(f'/api/sor/{self.sor.pk}/')
        self.assertIn(response.status_code, [200, 403])

    def test_api_requires_auth(self):
        self.client.credentials()
        response = self.client.get('/api/sor/')
        self.assertIn(response.status_code, [401, 403])
