# accidents/forms.py

from django import forms
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import Accident, AccidentImage
from vehicles.models import Vehicle
from trips.models import Trip

class AccidentForm(forms.ModelForm):
    """Form for creating a new accident report."""
    
    class Meta:
        model = Accident
        fields = [
            'vehicle', 'driver', 'date_time', 'location', 'latitude', 'longitude',
            'description', 'damage_description', 'third_party_involved',
            'police_report_number', 'injuries', 'injuries_description',
            'estimated_cost', 'insurance_claim_number', 'notes'
        ]
        widgets = {
            'date_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'description': forms.Textarea(attrs={'rows': 3}),
            'damage_description': forms.Textarea(attrs={'rows': 3}),
            'injuries_description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
            'estimated_cost': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default date_time to now
        if not self.instance.pk:
            self.fields['date_time'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
        
        # If user is a driver, restrict some fields
        if self.user and self.user.user_type == 'driver':
            self.fields['driver'].initial = self.user
            self.fields['driver'].widget = forms.HiddenInput()
            
            # Get the vehicle from active trip
            active_trip = Trip.objects.filter(
                driver=self.user,
                status='ongoing'
            ).first()
            
            if active_trip:
                self.fields['vehicle'].queryset = Vehicle.objects.filter(id=active_trip.vehicle.id)
                self.fields['vehicle'].initial = active_trip.vehicle
                self.fields['vehicle'].widget.attrs['readonly'] = True
            else:
                # Show all vehicles but with a warning
                self.fields['vehicle'].help_text = (
                    "You don't have an active trip. If this accident occurred during a trip, "
                    "please select the vehicle that was involved."
                )
    
    def clean_date_time(self):
        """Validate date_time is not in the future."""
        date_time = self.cleaned_data.get('date_time')
        
        if date_time and date_time > timezone.now():
            raise forms.ValidationError("Accident date and time cannot be in the future.")
        
        return date_time
    
    def clean(self):
        """Validate required fields based on conditions."""
        cleaned_data = super().clean()
        injuries = cleaned_data.get('injuries')
        injuries_description = cleaned_data.get('injuries_description')
        third_party_involved = cleaned_data.get('third_party_involved')
        police_report_number = cleaned_data.get('police_report_number')
        
        if injuries and not injuries_description:
            self.add_error(
                'injuries_description',
                "Please provide a description of the injuries."
            )
        
        if third_party_involved and not police_report_number:
            self.add_error(
                'police_report_number',
                "Police report number is required for accidents involving third parties."
            )
        
        return cleaned_data

class AccidentUpdateForm(forms.ModelForm):
    """Form for updating an existing accident report."""
    
    class Meta:
        model = Accident
        fields = [
            'location', 'latitude', 'longitude', 'description', 'damage_description',
            'third_party_involved', 'police_report_number', 'injuries',
            'injuries_description', 'estimated_cost', 'actual_cost',
            'insurance_claim_number', 'status', 'resolution_date', 'notes'
        ]
        widgets = {
            'resolution_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'damage_description': forms.Textarea(attrs={'rows': 3}),
            'injuries_description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
            'estimated_cost': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'actual_cost': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
        }
    
    def clean(self):
        """Validate fields based on status."""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        resolution_date = cleaned_data.get('resolution_date')
        
        if status == 'resolved' and not resolution_date:
            self.add_error(
                'resolution_date',
                "Resolution date is required when status is set to 'resolved'."
            )
        
        return cleaned_data

class AccidentImageForm(forms.ModelForm):
    """Form for accident images."""
    
    class Meta:
        model = AccidentImage
        fields = ['image', 'caption']
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Brief description of the image'}),
        }

# Create formset for multiple accident images
AccidentImageFormSet = inlineformset_factory(
    Accident,
    AccidentImage,
    form=AccidentImageForm,
    extra=3,
    can_delete=True
)