"""
Tests for the generators module.
Run with: python manage.py test generators
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Store, Generator, FuelType, UsageTracking, FuelEntry, MaintenanceLog

User = get_user_model()


class StoreModelTests(TestCase):
    def test_creation(self):
        store = Store.objects.create(name='Warehouse A', location='Chennai')
        self.assertEqual(str(store), 'Warehouse A')

    def test_unique_name(self):
        Store.objects.create(name='Store1', location='A')
        with self.assertRaises(Exception):
            Store.objects.create(name='Store1', location='B')

    def test_ordering(self):
        Store.objects.create(name='Zeta', location='Z')
        Store.objects.create(name='Alpha', location='A')
        stores = list(Store.objects.values_list('name', flat=True))
        self.assertEqual(stores, ['Alpha', 'Zeta'])


class GeneratorModelTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(name='Main Store', location='Chennai')

    def test_creation(self):
        gen = Generator.objects.create(
            store=self.store, make_and_model='Kirloskar 125',
            capacity_kva=125, fuel_type=FuelType.DIESEL,
        )
        self.assertEqual(gen.capacity_kva, 125)
        self.assertIn('125 kVA', str(gen))

    def test_default_fuel_type(self):
        gen = Generator.objects.create(
            store=self.store, make_and_model='Generic 50', capacity_kva=50,
        )
        self.assertEqual(gen.fuel_type, FuelType.DIESEL)


class FuelEntryModelTests(TestCase):
    def setUp(self):
        store = Store.objects.create(name='Fuel Store', location='Mumbai')
        self.gen = Generator.objects.create(
            store=store, make_and_model='CAT 200', capacity_kva=200,
        )

    def test_auto_total_cost(self):
        entry = FuelEntry(
            store=self.gen.store, generator=self.gen,
            litres_filled=Decimal('100.00'),
            fuel_rate_per_litre=Decimal('95.50'),
        )
        entry.save()
        self.assertEqual(entry.total_fuel_cost, Decimal('9550.00'))

    def test_str(self):
        entry = FuelEntry.objects.create(
            store=self.gen.store, generator=self.gen,
            litres_filled=Decimal('50'), fuel_rate_per_litre=Decimal('90'),
            total_fuel_cost=Decimal('4500'),
        )
        self.assertIn('CAT 200', str(entry))


class UsageTrackingModelTests(TestCase):
    def setUp(self):
        store = Store.objects.create(name='Usage Store', location='Delhi')
        self.gen = Generator.objects.create(
            store=store, make_and_model='Mahindra 75', capacity_kva=75,
        )

    def test_creation(self):
        usage = UsageTracking.objects.create(
            generator=self.gen, start_time='08:00',
            end_time='16:00', total_hours_run=Decimal('8.0'),
            reason_for_use='Power outage',
        )
        self.assertIn('Mahindra 75', str(usage))

    def test_ordering(self):
        """Usage logs should be ordered by -date, -start_time."""
        from datetime import time as t
        u1 = UsageTracking.objects.create(
            generator=self.gen, date=date(2024, 1, 1),
            start_time=t(8, 0), end_time=t(10, 0),
            total_hours_run=Decimal('2'), reason_for_use='Test',
        )
        u2 = UsageTracking.objects.create(
            generator=self.gen, date=date(2024, 1, 2),
            start_time=t(8, 0), end_time=t(10, 0),
            total_hours_run=Decimal('2'), reason_for_use='Test',
        )
        qs = UsageTracking.objects.all()
        self.assertEqual(qs[0], u2)


class MaintenanceLogModelTests(TestCase):
    def setUp(self):
        store = Store.objects.create(name='Maint Store', location='Kolkata')
        self.gen = Generator.objects.create(
            store=store, make_and_model='Cummins 150', capacity_kva=150,
        )

    def test_creation(self):
        log = MaintenanceLog.objects.create(
            generator=self.gen,
            service_type='Oil Change',
            service_provider='ABC Services',
            amount=Decimal('5000.00'),
        )
        self.assertIn('Cummins 150', str(log))


class GeneratorViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='genadmin', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        self.store = Store.objects.create(name='View Store', location='Test')
        self.gen = Generator.objects.create(
            store=self.store, make_and_model='Test Gen', capacity_kva=100,
        )
        self.client.login(username='genadmin', password='pass1234')

    def test_dashboard_view(self):
        response = self.client.get(reverse('generators:dashboard'))
        self.assertIn(response.status_code, [200, 302, 403])

    def test_store_list_view(self):
        response = self.client.get(reverse('generators:store_list'))
        self.assertEqual(response.status_code, 200)

    def test_generator_list_view(self):
        response = self.client.get(reverse('generators:generator_list'))
        self.assertEqual(response.status_code, 200)

    def test_store_detail_view(self):
        response = self.client.get(reverse('generators:store_detail', args=[self.store.pk]))
        self.assertEqual(response.status_code, 200)

    def test_views_require_login(self):
        self.client.logout()
        response = self.client.get(reverse('generators:dashboard'))
        self.assertEqual(response.status_code, 302)
