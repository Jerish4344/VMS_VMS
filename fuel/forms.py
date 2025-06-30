from django import forms
from django.utils import timezone
from django.db.models import Q
from .models import FuelTransaction, FuelStation
from vehicles.models import Vehicle

class FuelTransactionForm(forms.ModelForm):
    """Form for the FuelTransaction model supporting both fuel and electric vehicles."""
    
    class Meta:
        model = FuelTransaction
        fields = [
            'vehicle', 'driver', 'fuel_station', 'date', 
            # Fuel vehicle fields
            'fuel_type', 'quantity', 'cost_per_liter',
            # Electric vehicle fields
            'energy_consumed', 'cost_per_kwh', 'charging_duration_minutes',
            # Invoice/Finance fields
            'company_invoice_number', 'station_invoice_number',
            # Common fields
            'total_cost', 'odometer_reading', 'receipt_image', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'quantity': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'cost_per_liter': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'energy_consumed': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'cost_per_kwh': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'charging_duration_minutes': forms.NumberInput(attrs={'min': 0}),
            'total_cost': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'odometer_reading': forms.NumberInput(attrs={'min': 0}),
            'company_invoice_number': forms.TextInput(attrs={'placeholder': 'e.g., INV-2024-001'}),
            'station_invoice_number': forms.TextInput(attrs={'placeholder': 'e.g., RCP-12345'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default date to today
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
        
        # Restrict access for drivers - they should not be able to add transactions manually
        if self.user and self.user.user_type == 'driver':
            # Hide all fields for drivers since they shouldn't add transactions manually
            for field_name in self.fields:
                self.fields[field_name].widget = forms.HiddenInput()
            
            # Add a note for drivers
            self.fields['notes'].widget = forms.Textarea(attrs={
                'readonly': True,
                'placeholder': 'Fuel transactions are added by admin/manager only. Please contact your manager for fuel transaction entries.',
                'rows': 2
            })
        else:
            # For admin/managers, show all fields properly
            
            # Make invoice fields more prominent for finance tracking
            self.fields['company_invoice_number'].help_text = "Internal company invoice number for finance department tracking"
            self.fields['station_invoice_number'].help_text = "Invoice/receipt number provided by the fuel station"
        
        # Make fields not required to avoid validation issues
        self.fields['fuel_type'].required = False
        self.fields['quantity'].required = False
        self.fields['cost_per_liter'].required = False
        self.fields['energy_consumed'].required = False
        self.fields['cost_per_kwh'].required = False
        self.fields['total_cost'].required = False
        
        # Invoice fields are optional but helpful for finance
        self.fields['company_invoice_number'].required = False
        self.fields['station_invoice_number'].required = False
    
    def clean(self):
        """Enhanced validation with invoice number recommendations."""
        cleaned_data = super().clean()
        vehicle = cleaned_data.get('vehicle')
        
        # Block drivers from submitting if they somehow access the form
        if self.user and self.user.user_type == 'driver':
            raise forms.ValidationError("Drivers are not authorized to add fuel transactions. Please contact your manager.")
        
        # Basic validation - just ensure we have minimum required data
        if not vehicle:
            self.add_error('vehicle', 'Vehicle is required.')
            return cleaned_data
        
        # Ensure total_cost has a value
        total_cost = cleaned_data.get('total_cost')
        if not total_cost or total_cost <= 0:
            # Try to calculate it
            if vehicle.is_electric():
                energy = cleaned_data.get('energy_consumed')
                cost_per_kwh = cleaned_data.get('cost_per_kwh')
                if energy and cost_per_kwh:
                    cleaned_data['total_cost'] = energy * cost_per_kwh
                elif not total_cost:
                    self.add_error('total_cost', 'Total cost is required for electric vehicles. Either enter total cost or energy consumed + cost per kWh.')
            else:
                quantity = cleaned_data.get('quantity')
                cost_per_liter = cleaned_data.get('cost_per_liter')
                if quantity and cost_per_liter:
                    cleaned_data['total_cost'] = quantity * cost_per_liter
                elif not total_cost:
                    self.add_error('total_cost', 'Total cost is required for fuel vehicles. Either enter total cost or quantity + cost per liter.')
        
        # Set fuel type for electric vehicles
        if vehicle.is_electric():
            cleaned_data['fuel_type'] = 'Electric'
        elif not cleaned_data.get('fuel_type'):
            # Set default fuel type for non-electric vehicles
            cleaned_data['fuel_type'] = vehicle.fuel_type or 'Petrol'
        
        # Validate invoice numbers format (optional but recommended)
        company_invoice = cleaned_data.get('company_invoice_number')
        station_invoice = cleaned_data.get('station_invoice_number')
        
        if company_invoice and len(company_invoice.strip()) < 3:
            self.add_error('company_invoice_number', 'Company invoice number should be at least 3 characters long.')
            
        if station_invoice and len(station_invoice.strip()) < 3:
            self.add_error('station_invoice_number', 'Station invoice number should be at least 3 characters long.')
        
        return cleaned_data

class FuelStationForm(forms.ModelForm):
    """Form for the FuelStation model."""
    
    class Meta:
        model = FuelStation
        fields = ['name', 'address', 'station_type', 'latitude', 'longitude']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
        }
    
    def clean_latitude(self):
        """Validate latitude is within range."""
        latitude = self.cleaned_data.get('latitude')
        
        if latitude is not None and (latitude < -90 or latitude > 90):
            raise forms.ValidationError("Latitude must be between -90 and 90 degrees.")
        
        return latitude
    
    def clean_longitude(self):
        """Validate longitude is within range."""
        longitude = self.cleaned_data.get('longitude')
        
        if longitude is not None and (longitude < -180 or longitude > 180):
            raise forms.ValidationError("Longitude must be between -180 and 180 degrees.")
        
        return longitude
