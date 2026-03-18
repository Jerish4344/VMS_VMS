"""
Tests for the accidents module.
Run with: python manage.py test accidents
"""
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from vehicles.models import Vehicle, VehicleType
from .models import Accident, AccidentImage
from .forms import AccidentForm, AccidentUpdateForm

User = get_user_model()


class AccidentModelTests(TestCase):
    """Tests for Accident model."""

    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01AB1234', vin='VIN00000000000001',
            status='available', acquisition_date=date.today(),
        )
        self.driver = User.objects.create_user(
            username='driver1', password='pass1234',
            user_type='driver', approval_status='approved',
        )

    def test_accident_creation(self):
        acc = Accident.objects.create(
            vehicle=self.vehicle, driver=self.driver,
            date_time=timezone.now(), location='Chennai',
            description='Rear-end collision', damage_description='Bumper dent',
        )
        self.assertEqual(acc.status, 'reported')
        self.assertIn('Toyota', str(acc))

    def test_new_accident_sets_vehicle_maintenance(self):
        """Creating a new accident should set the vehicle to maintenance."""
        self.assertEqual(self.vehicle.status, 'available')
        Accident.objects.create(
            vehicle=self.vehicle, driver=self.driver,
            date_time=timezone.now(), location='Mumbai',
            description='Side swipe', damage_description='Door scratch',
        )
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, 'maintenance')

    def test_status_choices(self):
        acc = Accident.objects.create(
            vehicle=self.vehicle, driver=self.driver,
            date_time=timezone.now(), location='Delhi',
            description='Test', damage_description='Test',
        )
        for status, _ in Accident.STATUS_CHOICES:
            acc.status = status
            acc.save()
            self.assertEqual(acc.status, status)

    def test_ordering(self):
        """Accidents should be ordered by -date_time."""
        older = Accident.objects.create(
            vehicle=self.vehicle, driver=self.driver,
            date_time=timezone.now() - timedelta(days=1),
            location='A', description='Old', damage_description='Old',
        )
        newer = Accident.objects.create(
            vehicle=self.vehicle, driver=self.driver,
            date_time=timezone.now(), location='B',
            description='New', damage_description='New',
        )
        qs = Accident.objects.all()
        self.assertEqual(qs[0], newer)
        self.assertEqual(qs[1], older)

    def test_cost_fields(self):
        acc = Accident.objects.create(
            vehicle=self.vehicle, driver=self.driver,
            date_time=timezone.now(), location='Test',
            description='Test', damage_description='Test',
            estimated_cost=Decimal('5000.00'), actual_cost=Decimal('4500.50'),
        )
        self.assertEqual(acc.estimated_cost, Decimal('5000.00'))
        self.assertEqual(acc.actual_cost, Decimal('4500.50'))


class AccidentImageTests(TestCase):
    def setUp(self):
        vtype = VehicleType.objects.create(name='Car', category='personal')
        vehicle = Vehicle.objects.create(
            vehicle_type=vtype, make='Honda', model='City', year=2023,
            license_plate='TN02CD5678', vin='VIN00000000000002',
            acquisition_date=date.today(),
        )
        driver = User.objects.create_user(
            username='driver2', password='pass1234',
            user_type='driver', approval_status='approved',
        )
        self.accident = Accident.objects.create(
            vehicle=vehicle, driver=driver,
            date_time=timezone.now(), location='Test',
            description='Test', damage_description='Test',
        )

    def test_image_str_with_caption(self):
        img = AccidentImage.objects.create(accident=self.accident, caption='Front damage')
        self.assertEqual(str(img), 'Front damage')

    def test_image_str_without_caption(self):
        img = AccidentImage.objects.create(accident=self.accident)
        self.assertIn('Image for accident', str(img))


class AccidentFormTests(TestCase):
    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN03EF9012', vin='VIN00000000000003',
            acquisition_date=date.today(),
        )
        self.driver = User.objects.create_user(
            username='driver3', password='pass1234',
            user_type='driver', approval_status='approved',
        )

    def test_future_date_rejected(self):
        future_dt = timezone.now() + timedelta(hours=2)
        form = AccidentForm(data={
            'vehicle': self.vehicle.id, 'driver': self.driver.id,
            'date_time': future_dt,
            'location': 'Test', 'description': 'Test', 'damage_description': 'Test',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('date_time', form.errors)

    def test_injuries_without_description_rejected(self):
        form = AccidentForm(data={
            'vehicle': self.vehicle.id, 'driver': self.driver.id,
            'date_time': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'location': 'Test', 'description': 'Test', 'damage_description': 'Test',
            'injuries': True, 'injuries_description': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('injuries_description', form.errors)

    def test_update_form_resolved_requires_date(self):
        form = AccidentUpdateForm(data={
            'location': 'Test', 'description': 'Test', 'damage_description': 'Test',
            'status': 'resolved', 'resolution_date': '',
            'third_party_involved': False, 'injuries': False,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('resolution_date', form.errors)


class AccidentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin1', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN04GH3456', vin='VIN00000000000004',
            acquisition_date=date.today(),
        )
        self.accident = Accident.objects.create(
            vehicle=self.vehicle, driver=self.admin,
            date_time=timezone.now(), location='Chennai',
            description='Test accident', damage_description='Minor damage',
        )
        self.client.login(username='admin1', password='pass1234')

    def test_accident_list_view(self):
        response = self.client.get(reverse('accident_list'))
        self.assertEqual(response.status_code, 200)

    def test_accident_detail_view(self):
        response = self.client.get(reverse('accident_detail', args=[self.accident.pk]))
        self.assertEqual(response.status_code, 200)

    def test_accident_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('accident_list'))
        self.assertEqual(response.status_code, 302)

    def test_accident_search_filter(self):
        response = self.client.get(reverse('accident_list'), {'search': 'Chennai'})
        self.assertEqual(response.status_code, 200)

    def test_accident_status_filter(self):
        response = self.client.get(reverse('accident_list'), {'status': 'reported'})
        self.assertEqual(response.status_code, 200)
