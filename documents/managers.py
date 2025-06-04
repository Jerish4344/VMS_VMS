# documents/managers.py
from django.db import models
from django.utils import timezone

class DocumentManager(models.Manager):
    def sync_with_vehicle(self, vehicle):
        """Sync documents with vehicle expiry dates"""
        from .models import DocumentType
        
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