"""
Tests for the documents module.
Run with: python manage.py test documents
"""
from datetime import date, timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from vehicles.models import Vehicle, VehicleType
from .models import Document, DocumentType, DocumentManager

User = get_user_model()


class DocumentTypeModelTests(TestCase):
    def test_creation(self):
        dt = DocumentType.objects.create(name='Insurance Policy', required=True)
        self.assertEqual(str(dt), 'Insurance Policy')
        self.assertTrue(dt.required)

    def test_document_count(self):
        dt = DocumentType.objects.create(name='RC')
        self.assertEqual(dt.document_count, 0)


class DocumentModelTests(TestCase):
    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01DC0001', vin='VINDOC00000000001',
            acquisition_date=date.today(),
        )
        self.doc_type = DocumentType.objects.create(name='Insurance', required=True)

    def test_document_creation(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-001',
            issue_date=date.today() - timedelta(days=365),
            expiry_date=date.today() + timedelta(days=180),
        )
        self.assertIn('Insurance', str(doc))

    def test_is_expired(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-002',
            issue_date=date.today() - timedelta(days=730),
            expiry_date=date.today() - timedelta(days=1),
        )
        self.assertTrue(doc.is_expired())

    def test_is_not_expired(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-003',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        self.assertFalse(doc.is_expired())

    def test_is_expiring_soon(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-004',
            issue_date=date.today() - timedelta(days=300),
            expiry_date=date.today() + timedelta(days=15),
        )
        self.assertTrue(doc.is_expiring_soon())

    def test_is_not_expiring_soon(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-005',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=90),
        )
        self.assertFalse(doc.is_expiring_soon())

    def test_days_until_expiry(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-006',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=100),
        )
        self.assertEqual(doc.days_until_expiry(), 100)

    def test_days_until_expiry_expired(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-007',
            issue_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=10),
        )
        self.assertEqual(doc.days_until_expiry(), 0)

    def test_status_label_valid(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-008',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        self.assertEqual(doc.status_label(), 'Valid')

    def test_status_label_expired(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-009',
            issue_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=5),
        )
        self.assertEqual(doc.status_label(), 'Expired')

    def test_status_label_expiring_soon(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-010',
            issue_date=date.today() - timedelta(days=300),
            expiry_date=date.today() + timedelta(days=10),
        )
        self.assertEqual(doc.status_label(), 'Expiring Soon')

    def test_status_color(self):
        doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-011',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        self.assertEqual(doc.status_color(), 'success')

    def test_missing_required_for_vehicle(self):
        dt2 = DocumentType.objects.create(name='Fitness', required=True)
        Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='INS-012',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        missing = Document.objects.missing_required_for_vehicle(self.vehicle)
        self.assertIn(dt2, missing)
        self.assertNotIn(self.doc_type, missing)


class DocumentSyncTests(TestCase):
    def setUp(self):
        self.vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=self.vtype, make='Honda', model='City', year=2023,
            license_plate='TN01DC0002', vin='VINDOC00000000002',
            acquisition_date=date.today(),
            insurance_expiry_date=date.today() + timedelta(days=180),
            fitness_expiry=date.today() + timedelta(days=90),
        )

    def test_create_from_vehicle(self):
        docs = Document.create_from_vehicle(self.vehicle)
        self.assertTrue(len(docs) >= 1)

    def test_sync_does_not_duplicate(self):
        docs1 = Document.create_from_vehicle(self.vehicle)
        docs2 = Document.create_from_vehicle(self.vehicle)
        self.assertEqual(len(docs2), 0)  # No new docs on second sync


class DocumentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='docadmin', password='pass1234',
            user_type='admin', approval_status='approved',
        )
        vtype = VehicleType.objects.create(name='Car', category='personal')
        self.vehicle = Vehicle.objects.create(
            vehicle_type=vtype, make='Toyota', model='Camry', year=2023,
            license_plate='TN01DC0003', vin='VINDOC00000000003',
            acquisition_date=date.today(),
        )
        self.doc_type = DocumentType.objects.create(name='Insurance', required=True)
        self.doc = Document.objects.create(
            vehicle=self.vehicle, document_type=self.doc_type,
            document_number='DOC-001',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        self.client.login(username='docadmin', password='pass1234')

    def test_document_list_view(self):
        response = self.client.get(reverse('document_list'))
        self.assertEqual(response.status_code, 200)

    def test_document_detail_view(self):
        response = self.client.get(reverse('document_detail', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)

    def test_document_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('document_list'))
        self.assertEqual(response.status_code, 302)

    def test_document_type_list(self):
        response = self.client.get(reverse('document_type_list'))
        self.assertEqual(response.status_code, 200)
