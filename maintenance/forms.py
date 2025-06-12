from django import forms
from django.utils import timezone
from .models import Maintenance, MaintenanceType, MaintenanceProvider
from vehicles.models import Vehicle

class MaintenanceForm(forms.ModelForm):
    """Form for the Maintenance model."""
    
    class Meta:
        model = Maintenance
        fields = [
            'vehicle', 'maintenance_type', 'provider', 'date_reported',
            'description', 'odometer_reading', 'status', 'scheduled_date',
            'completion_date', 'cost', 'invoice_image', 'notes'
        ]
        widgets = {
            'date_reported': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'completion_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'cost': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default date_reported to today
        if not self.instance.pk:
            self.fields['date_reported'].initial = timezone.now().date()
        
        # Only show available vehicles and those under maintenance
        self.fields['vehicle'].queryset = Vehicle.objects.filter(
            status__in=['available', 'maintenance']
        )
        
        # Make optional fields not required by default
        self.fields['provider'].required = False
        self.fields['scheduled_date'].required = False
        self.fields['completion_date'].required = False
        self.fields['cost'].required = False
        self.fields['invoice_image'].required = False
        self.fields['notes'].required = False
        
        # Make certain fields required based on status - only for existing instances
        if self.instance.pk and hasattr(self.instance, 'status'):
            if self.instance.status == 'completed':
                self.fields['completion_date'].required = True
            elif self.instance.status == 'scheduled':
                self.fields['scheduled_date'].required = True
    
    def clean(self):
        """Validate date fields to ensure they are in the correct order."""
        cleaned_data = super().clean()
        date_reported = cleaned_data.get('date_reported')
        scheduled_date = cleaned_data.get('scheduled_date')
        completion_date = cleaned_data.get('completion_date')
        status = cleaned_data.get('status')
        
        if scheduled_date and date_reported and scheduled_date < date_reported:
            self.add_error(
                'scheduled_date',
                "Scheduled date cannot be earlier than the date reported."
            )
        
        if completion_date and scheduled_date and completion_date < scheduled_date:
            self.add_error(
                'completion_date',
                "Completion date cannot be earlier than the scheduled date."
            )
        
        if status == 'completed' and not completion_date:
            self.add_error(
                'completion_date',
                "Completion date is required when status is completed."
            )
        
        if status == 'scheduled' and not scheduled_date:
            self.add_error(
                'scheduled_date',
                "Scheduled date is required when status is scheduled."
            )
        
        return cleaned_data

class MaintenanceTypeForm(forms.ModelForm):
    """Form for the MaintenanceType model."""
    
    class Meta:
        model = MaintenanceType
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class MaintenanceProviderForm(forms.ModelForm):
    """Form for the MaintenanceProvider model."""
    
    class Meta:
        model = MaintenanceProvider
        fields = ['name', 'address', 'phone', 'email', 'website']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'website': forms.URLInput(attrs={'placeholder': 'https://...'}),
        }