from django.db import models
from django.utils import timezone
from vehicles.models import Vehicle

class DocumentManager(models.Manager):
    def sync_with_vehicle(self, vehicle):
        """Sync documents with vehicle expiry dates"""
        
        # Map of vehicle fields to document types
        doc_mappings = {
            'rc_valid_till': 'Registration Certificate',
            'insurance_expiry_date': 'Insurance Policy',
            'fitness_expiry': 'Fitness Certificate',
            'permit_expiry': 'Permit',
            'pollution_cert_expiry': 'Pollution Certificate'
        }
        
        # Update existing documents or create new ones
        updated_docs = []
        for field, type_name in doc_mappings.items():
            date_value = getattr(vehicle, field, None)
            if date_value:
                # Get or create document type
                doc_type, _ = DocumentType.objects.get_or_create(
                    name=type_name,
                    defaults={'description': f'Auto-generated {type_name}', 'required': True}
                )
                
                # Get or create document
                doc, created = self.get_or_create(
                    vehicle=vehicle,
                    document_type=doc_type,
                    defaults={
                        'document_number': f'AUTO-{vehicle.license_plate}',
                        'issue_date': vehicle.acquisition_date or timezone.now().date(),
                        'expiry_date': date_value,
                        'issuing_authority': vehicle.owner_name or 'Unknown',
                        'notes': f'Auto-generated from vehicle data'
                    }
                )
                
                # If document exists, update expiry date if it changed
                if not created and doc.expiry_date != date_value:
                    doc.expiry_date = date_value
                    doc.save()
                    
                updated_docs.append(doc)
                
        return updated_docs


class DocumentType(models.Model):
    """
    Different types of vehicle documents (Registration, Insurance, Pollution Certificate, etc.)
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    required = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    @property
    def document_count(self):
        """Count documents of this type."""
        return self.document_set.count()
    
    @property
    def expired_count(self):
        """Count expired documents of this type."""
        return self.document_set.filter(expiry_date__lt=timezone.now().date()).count()
    
    @property
    def expiring_soon_count(self):
        """Count documents of this type expiring in the next 30 days."""
        today = timezone.now().date()
        thirty_days_later = today + timezone.timedelta(days=30)
        return self.document_set.filter(
            expiry_date__range=[today, thirty_days_later]
        ).count()
    
    @property
    def valid_count(self):
        """Count valid documents of this type (not expired or expiring soon)."""
        thirty_days_later = timezone.now().date() + timezone.timedelta(days=30)
        return self.document_set.filter(expiry_date__gt=thirty_days_later).count()


class Document(models.Model):
    """
    Represents documents associated with vehicles (Registration, Insurance, etc.)
    """
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='documents')
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE)
    document_number = models.CharField(max_length=100)
    issue_date = models.DateField()
    expiry_date = models.DateField()
    issuing_authority = models.CharField(max_length=100)
    file = models.FileField(upload_to='vehicle_documents/', null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Add the custom manager
    objects = DocumentManager()
    
    def __str__(self):
        return f"{self.document_type.name} for {self.vehicle}"
    
    def is_expired(self):
        """Check if document is expired."""
        return self.expiry_date < timezone.now().date()
    
    def is_expiring_soon(self):
        """Check if document is expiring in the next 30 days."""
        today = timezone.now().date()
        thirty_days_later = today + timezone.timedelta(days=30)
        return today <= self.expiry_date <= thirty_days_later
    
    def days_until_expiry(self):
        """Get number of days until expiry."""
        today = timezone.now().date()
        if self.expiry_date < today:
            return 0
        return (self.expiry_date - today).days
    
    def days_since_expiry(self):
        """Get number of days since expiry if expired."""
        today = timezone.now().date()
        if self.expiry_date >= today:
            return 0
        return (today - self.expiry_date).days
    
    def status_label(self):
        """Get status as a string."""
        if self.is_expired():
            return "Expired"
        elif self.is_expiring_soon():
            return "Expiring Soon"
        else:
            return "Valid"
    
    def status_color(self):
        """Get Bootstrap color class for status."""
        if self.is_expired():
            return "danger"
        elif self.is_expiring_soon():
            return "warning"
        else:
            return "success"
    
    @classmethod
    def create_from_vehicle(cls, vehicle):
        """Create documents from vehicle data using real information"""
        from django.utils import timezone
        
        # Map of vehicle fields to document types with appropriate document number fields
        doc_type_mappings = {
            'rc_valid_till': {
                'name': 'Registration Certificate',
                'number_field': 'license_plate'  # Use license plate as the document number
            },
            'insurance_expiry_date': {
                'name': 'Insurance Policy',
                'number_field': 'license_plate'  # Use license plate as the policy number
            },
            'fitness_expiry': {
                'name': 'Fitness Certificate',
                'number_field': 'license_plate'  # Use license plate as certificate number
            },
            'permit_expiry': {
                'name': 'Permit',
                'number_field': 'license_plate'  # Use license plate as permit number
            },
            'pollution_cert_expiry': {
                'name': 'Pollution Certificate',
                'number_field': 'license_plate'  # Use license plate as certificate number
            }
        }
        
        # Get or create document types
        doc_types = {}
        for field, info in doc_type_mappings.items():
            doc_type, created = DocumentType.objects.get_or_create(
                name=info['name'],
                defaults={'description': f'{info["name"]}', 'required': True}
            )
            doc_types[field] = {
                'type': doc_type,
                'number_field': info['number_field']
            }
        
        # Create documents for each field if date exists
        docs_created = []
        for field, type_info in doc_types.items():
            date_value = getattr(vehicle, field, None)
            if date_value:
                # Check if document already exists
                existing = cls.objects.filter(
                    vehicle=vehicle,
                    document_type=type_info['type']
                ).first()
                
                if not existing:
                    # Use the specified vehicle field value as the document number
                    document_number = getattr(vehicle, type_info['number_field'])
                    
                    # Create new document
                    doc = cls.objects.create(
                        vehicle=vehicle,
                        document_type=type_info['type'],
                        document_number=document_number,
                        issue_date=vehicle.acquisition_date or timezone.now().date(),
                        expiry_date=date_value,
                        issuing_authority=vehicle.owner_name or 'Unknown',
                        notes=''  # No notes needed, this represents the real document
                    )
                    docs_created.append(doc)
                    
        return docs_created 
    
    @classmethod
    def sync_all_vehicles(cls):
        """Sync documents for all vehicles in the system."""
        updated_docs = []
        for vehicle in Vehicle.objects.all():
            docs = cls.create_from_vehicle(vehicle)
            updated_docs.extend(docs)
        return updated_docs
    
    def update_from_vehicle_data(self):
        """Update this document from vehicle data."""
        # Map document types to vehicle fields
        type_to_field_map = {
            'Registration Certificate': 'rc_valid_till',
            'Insurance Policy': 'insurance_expiry_date',
            'Fitness Certificate': 'fitness_expiry',
            'Permit': 'permit_expiry',
            'Pollution Certificate': 'pollution_cert_expiry'
        }
        
        # Find the corresponding field for this document type
        field_name = type_to_field_map.get(self.document_type.name)
        if field_name:
            # Get the date from the vehicle
            date_value = getattr(self.vehicle, field_name, None)
            if date_value and date_value != self.expiry_date:
                self.expiry_date = date_value
                self.save()
                return True
        return False