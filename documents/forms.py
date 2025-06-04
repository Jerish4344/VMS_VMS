from django import forms
from django.conf import settings
from django.utils import timezone
import os
from .models import Document, DocumentType
from vehicles.models import Vehicle

class DocumentForm(forms.ModelForm):
    """Form for the Document model."""
    
    class Meta:
        model = Document
        fields = [
            'vehicle', 'document_type', 'document_number', 'issue_date',
            'expiry_date', 'issuing_authority', 'file', 'notes'
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default dates if creating a new document
        if not self.instance.pk:
            self.fields['issue_date'].initial = timezone.now().date()
            
            # Default expiry to one year from now
            self.fields['expiry_date'].initial = (
                timezone.now().date() + timezone.timedelta(days=365)
            )
        
        # Get vehicle ID from GET parameter if provided
        vehicle_id = kwargs.get('initial', {}).get('vehicle')
        if vehicle_id:
            try:
                self.fields['vehicle'].initial = Vehicle.objects.get(pk=vehicle_id)
            except Vehicle.DoesNotExist:
                pass
    
    def clean_file(self):
        """Validate file size and type."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size
            if file.size > settings.MAX_DOCUMENT_SIZE:
                max_size_mb = settings.MAX_DOCUMENT_SIZE / (1024 * 1024)
                raise forms.ValidationError(f"File size exceeds the maximum allowed size ({max_size_mb} MB).")
            
            # Check file extension
            ext = os.path.splitext(file.name)[1].lower()[1:]
            allowed_extensions = settings.ALLOWED_DOCUMENT_TYPES
            
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        return file
    
    def clean(self):
        """Validate issue_date and expiry_date."""
        cleaned_data = super().clean()
        issue_date = cleaned_data.get('issue_date')
        expiry_date = cleaned_data.get('expiry_date')
        
        if issue_date and expiry_date and issue_date > expiry_date:
            self.add_error('expiry_date', "Expiry date cannot be earlier than issue date.")
        
        # Check if expiry date is in the past
        today = timezone.now().date()
        if expiry_date and expiry_date < today:
            self.add_error(
                'expiry_date',
                "Warning: The expiry date is in the past. This document is already expired."
            )
        
        return cleaned_data

class DocumentTypeForm(forms.ModelForm):
    """Form for the DocumentType model."""
    
    class Meta:
        model = DocumentType
        fields = ['name', 'description', 'required']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }