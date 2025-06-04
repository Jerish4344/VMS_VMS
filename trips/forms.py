from django import forms
from django.utils import timezone
from .models import Trip
from vehicles.models import Vehicle
from django.contrib.auth import get_user_model

User = get_user_model()

class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = [
            'vehicle', 'origin', 'destination', 
            'start_odometer', 'purpose', 'notes'
        ]
        widgets = {
            'origin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter starting location'}),
            'destination': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter destination'}),
            'start_odometer': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'purpose': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Client Visit, Delivery'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes (optional)'}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set up vehicle choices - only show available vehicles
        self.fields['vehicle'].queryset = Vehicle.objects.filter(status='available')
        self.fields['vehicle'].empty_label = "Choose a vehicle..."
        
        # Make notes optional
        self.fields['notes'].required = False
    
    def clean_start_odometer(self):
        """Validate start odometer is not less than vehicle's current odometer."""
        start_odometer = self.cleaned_data.get('start_odometer')
        vehicle = self.cleaned_data.get('vehicle')
        
        if vehicle and vehicle.current_odometer and start_odometer < vehicle.current_odometer:
            raise forms.ValidationError(
                f"Start odometer cannot be less than vehicle's current odometer ({vehicle.current_odometer} km)."
            )
        
        return start_odometer
    
    def clean_origin(self):
        """Validate origin field."""
        origin = self.cleaned_data.get('origin')
        if not origin or len(origin.strip()) < 3:
            raise forms.ValidationError("Please provide a valid starting location (minimum 3 characters).")
        return origin.strip()
    
    def clean_destination(self):
        """Validate destination field."""
        destination = self.cleaned_data.get('destination')
        if not destination or len(destination.strip()) < 3:
            raise forms.ValidationError("Please provide a valid destination (minimum 3 characters).")
        return destination.strip()
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        origin = cleaned_data.get('origin')
        destination = cleaned_data.get('destination')
        
        if origin and destination and origin.lower().strip() == destination.lower().strip():
            raise forms.ValidationError("Origin and destination cannot be the same.")
        
        return cleaned_data

class EndTripForm(forms.ModelForm):
    """Form for ending a trip."""
    
    class Meta:
        model = Trip
        fields = ['end_odometer', 'notes']
        widgets = {
            'end_odometer': forms.NumberInput(attrs={
                'min': 0,
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Additional trip details or final remarks...',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add custom help text
        self.fields['end_odometer'].help_text = "Current odometer reading in kilometers"
        
        # Set minimum value for end_odometer
        if self.instance and self.instance.start_odometer:
            self.fields['end_odometer'].widget.attrs['min'] = self.instance.start_odometer
    
    def clean_end_odometer(self):
        """Validate end odometer is greater than start odometer."""
        end_odometer = self.cleaned_data.get('end_odometer')
        
        if self.instance and self.instance.start_odometer:
            if end_odometer < self.instance.start_odometer:
                raise forms.ValidationError(
                    f"End odometer cannot be less than start odometer ({self.instance.start_odometer} km)."
                )
        
        return end_odometer

class ManualTripForm(forms.ModelForm):
    """Form for manually creating trips by managers."""
    
    class Meta:
        model = Trip
        fields = [
            'vehicle', 'driver', 'origin', 'destination', 
            'start_time', 'end_time', 'start_odometer', 
            'end_odometer', 'purpose', 'notes'
        ]
        widgets = {
            'start_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'end_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'origin': forms.TextInput(attrs={'class': 'form-control'}),
            'destination': forms.TextInput(attrs={'class': 'form-control'}),
            'start_odometer': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'end_odometer': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'purpose': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'driver': forms.Select(attrs={'class': 'form-select'}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up driver choices
        from accounts.models import CustomUser
        self.fields['driver'].queryset = CustomUser.objects.filter(user_type='driver')
        
        # Set up vehicle choices
        self.fields['vehicle'].queryset = Vehicle.objects.all()
        
        # Make end_time and end_odometer not required for manual forms
        self.fields['end_time'].required = False
        self.fields['end_odometer'].required = False
        self.fields['notes'].required = False
        
        # Add empty choice for dropdowns
        self.fields['driver'].empty_label = "Select a driver..."
        self.fields['vehicle'].empty_label = "Select a vehicle..."