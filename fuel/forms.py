from django import forms
from django.utils import timezone
from django.db.models import Q
from .models import FuelTransaction, FuelStation
from vehicles.models import Vehicle

class FuelTransactionForm(forms.ModelForm):
    """Simplified form for the FuelTransaction model supporting both fuel and electric vehicles."""
    
    class Meta:
        model = FuelTransaction
        fields = [
            'vehicle', 'driver', 'fuel_station', 'date', 
            # Fuel vehicle fields
            'fuel_type', 'quantity', 'cost_per_liter',
            # Electric vehicle fields
            'energy_consumed', 'cost_per_kwh', 'charging_duration_minutes',
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
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default date to today
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
        
        # If user is a driver, set them as driver and hide the field
        if self.user and self.user.user_type == 'driver':
            self.fields['driver'].initial = self.user
            self.fields['driver'].widget = forms.HiddenInput()
            
            # Restrict vehicle options for drivers
            from trips.models import Trip
            
            active_trip = Trip.objects.filter(
                driver=self.user,
                status='ongoing'
            ).first()
            
            if active_trip:
                self.fields['vehicle'].queryset = Vehicle.objects.filter(
                    id=active_trip.vehicle.id
                )
                self.fields['vehicle'].initial = active_trip.vehicle
            else:
                self.fields['vehicle'].queryset = Vehicle.objects.filter(
                    Q(status='available') | Q(status='in_use')
                )
        
        # Make fields not required to avoid validation issues
        self.fields['fuel_type'].required = False
        self.fields['quantity'].required = False
        self.fields['cost_per_liter'].required = False
        self.fields['energy_consumed'].required = False
        self.fields['cost_per_kwh'].required = False
        self.fields['total_cost'].required = False
    
    def clean(self):
        """Basic validation - keep it simple to avoid issues."""
        cleaned_data = super().clean()
        vehicle = cleaned_data.get('vehicle')
        
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