from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import AiroTrackDevice
from vehicles.models import Vehicle

class AiroTrackDeviceForm(forms.ModelForm):
    """
    Form for creating and editing AiroTrack tracking devices.
    """
    class Meta:
        model = AiroTrackDevice
        # Only include actual fields present on the model
        fields = [
            'device_id',
            'name',
            'vehicle',
            'status',
        ]
        widgets = {
            'device_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter device ID',
                'autofocus': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter device name (optional)'
            }),
            'vehicle': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show all vehicles that currently have **no** device assigned
        self.fields['vehicle'].queryset = Vehicle.objects.filter(airotrack_device__isnull=True)
        self.fields['vehicle'].required = False
        self.fields['vehicle'].empty_label = "-- Select Vehicle (Optional) --"
        
    def clean_device_id(self):
        device_id = self.cleaned_data.get('device_id')
        if not device_id:
            raise ValidationError("Device ID is required")
        
        # Check if device_id already exists (for new devices)
        if not self.instance.pk and AiroTrackDevice.objects.filter(device_id=device_id).exists():
            raise ValidationError("A device with this ID already exists")
            
        return device_id

class VehicleAssignmentForm(forms.Form):
    """
    Form for assigning a vehicle to a tracking device.
    """
    vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.filter(airotrack_device__isnull=True, gps_fitted='yes'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        empty_label="-- Select Vehicle --",
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        # Allow passing a device to exclude vehicles that already have devices
        device = kwargs.pop('device', None)
        super().__init__(*args, **kwargs)
        
        # Always filter to vehicles with GPS fitted
        queryset = Vehicle.objects.filter(gps_fitted='yes')
        
        # Exclude vehicles that already have devices
        if device:
            queryset = queryset.filter(airotrack_device__isnull=True) | queryset.filter(airotrack_device=device)
        else:
            queryset = queryset.filter(airotrack_device__isnull=True)
            
        self.fields['vehicle'].queryset = queryset
        
class DateRangeForm(forms.Form):
    """
    Form for selecting a date range for history filtering.
    """
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        }),
        required=True
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        }),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        # Set default date range to last 7 days if not provided
        if 'initial' not in kwargs or not kwargs['initial']:
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=7)
            kwargs['initial'] = {
                'start_date': start_date,
                'end_date': end_date
            }
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("End date cannot be before start date")
            
        # Limit date range to 31 days to prevent performance issues
        if start_date and end_date and (end_date - start_date).days > 31:
            raise ValidationError("Date range cannot exceed 31 days")
            
        return cleaned_data

class AiroTrackSettingsForm(forms.Form):
    """
    Form for configuring AiroTrack API settings.
    """
    api_username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'API Username'
        }),
        required=True
    )
    
    api_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'API Password'
        }),
        required=True
    )
    
    api_base_url = forms.URLField(
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'API Base URL'
        }),
        required=True
    )
    
    sync_interval = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '60'
        }),
        min_value=1,
        max_value=60,
        help_text="Sync interval in minutes",
        required=True
    )
    
    store_history = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        required=False,
        help_text="Store location history in database"
    )
    
    history_retention_days = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '365'
        }),
        min_value=1,
        max_value=365,
        help_text="Number of days to retain location history",
        required=False
    )
