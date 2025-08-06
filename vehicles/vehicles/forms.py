from django import forms
from .models import Vehicle, VehicleType

class VehicleTypeForm(forms.ModelForm):
    """Form for VehicleType model."""
    
    class Meta:
        model = VehicleType
        fields = ['name', 'description', 'category']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'category': 'Select the category that best describes this vehicle type. This determines which fields are required when adding vehicles.',
        }

class VehicleForm(forms.ModelForm):
    """Form for Vehicle model with conditional fields based on vehicle type."""
    
    # Add a field to handle combined make and model from Excel
    make_model = forms.CharField(
        required=False, 
        label="Make & Model", 
        help_text="Used only for Excel import"
    )
    
    class Meta:
        model = Vehicle
        fields = [
            'vehicle_type', 'make', 'model', 'year', 'license_plate', 
            'vin', 'color', 'seating_capacity', 'load_capacity_kg',
            'fuel_type', 'fuel_capacity', 'average_mileage',
            'battery_capacity_kwh', 'charging_type', 'range_per_charge', 'charging_time_hours',
            'acquisition_date', 'status', 'current_odometer', 
            'owner_name', 'rc_valid_till', 'insurance_expiry_date', 
            'fitness_expiry', 'permit_expiry', 'pollution_cert_expiry',
            'gps_fitted', 'gps_name', 'driver_contact', 'assigned_driver',
            'purpose_of_vehicle', 'company_owned', 'usage_type', 'used_by',
            'image', 'notes'
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date'}),
            'rc_valid_till': forms.DateInput(attrs={'type': 'date'}),
            'insurance_expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'fitness_expiry': forms.DateInput(attrs={'type': 'date'}),
            'permit_expiry': forms.DateInput(attrs={'type': 'date'}),
            'pollution_cert_expiry': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'vehicle_type': forms.Select(attrs={'onchange': 'toggleFieldsByVehicleType()'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make some fields required
        self.fields['vehicle_type'].empty_label = None
        
        # Set initial odometer reading for new vehicles
        if not self.instance.pk:
            self.fields['current_odometer'].initial = 0
        
        # Add CSS classes and data attributes for conditional fields
        self.fields['fuel_type'].widget.attrs.update({
            'class': 'form-control fuel-field',
            'data-field-type': 'fuel'
        })
        self.fields['fuel_capacity'].widget.attrs.update({
            'class': 'form-control fuel-field',
            'data-field-type': 'fuel'
        })
        self.fields['average_mileage'].widget.attrs.update({
            'class': 'form-control fuel-field',
            'data-field-type': 'fuel'
        })
        
        self.fields['battery_capacity_kwh'].widget.attrs.update({
            'class': 'form-control electric-field',
            'data-field-type': 'electric'
        })
        self.fields['charging_type'].widget.attrs.update({
            'class': 'form-control electric-field',
            'data-field-type': 'electric'
        })
        self.fields['range_per_charge'].widget.attrs.update({
            'class': 'form-control electric-field',
            'data-field-type': 'electric'
        })
        self.fields['charging_time_hours'].widget.attrs.update({
            'class': 'form-control electric-field',
            'data-field-type': 'electric'
        })
        
        self.fields['load_capacity_kg'].widget.attrs.update({
            'class': 'form-control commercial-field',
            'data-field-type': 'commercial'
        })
        
        # Set help texts
        self.fields['seating_capacity'].help_text = "Number of seats (required for all vehicles)"
        self.fields['load_capacity_kg'].help_text = "Load capacity in KG (required for commercial vehicles)"
        self.fields['fuel_type'].help_text = "Required for non-electric vehicles"
        self.fields['fuel_capacity'].help_text = "Required for non-electric vehicles"
        self.fields['battery_capacity_kwh'].help_text = "Required for electric vehicles"
        self.fields['range_per_charge'].help_text = "Required for electric vehicles"
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Process make_model field if provided (from Excel import)
        make_model = cleaned_data.get('make_model')
        if make_model and (not cleaned_data.get('make') or not cleaned_data.get('model')):
            parts = make_model.split(' ', 1)
            if len(parts) > 0:
                cleaned_data['make'] = parts[0]
            if len(parts) > 1:
                cleaned_data['model'] = parts[1]
        
        # Validate conditional fields based on vehicle type
        vehicle_type = cleaned_data.get('vehicle_type')
        if vehicle_type:
            vehicle_type_name = vehicle_type.name.upper()
            
            # Check if it's a commercial vehicle
            is_commercial = any(word in vehicle_type_name for word in ['TRUCK', 'VAN', 'PICKUP', 'COMMERCIAL', 'LORRY'])
            if is_commercial:
                if not cleaned_data.get('load_capacity_kg'):
                    self.add_error('load_capacity_kg', 'Load capacity is required for commercial vehicles.')
            
            # Check if it's an electric vehicle
            is_electric = any(word in vehicle_type_name for word in ['ELECTRIC', 'EV', 'HYBRID'])
            if is_electric:
                if not cleaned_data.get('battery_capacity_kwh'):
                    self.add_error('battery_capacity_kwh', 'Battery capacity is required for electric vehicles.')
                if not cleaned_data.get('range_per_charge'):
                    self.add_error('range_per_charge', 'Range per charge is required for electric vehicles.')
                
                # Set fuel fields to empty for electric vehicles (don't set to None)
                cleaned_data['fuel_type'] = ''
                # Keep fuel_capacity and average_mileage as they are, don't force to None
            else:
                # For non-electric vehicles, keep electric fields as they are
                # Don't force them to None unless the user explicitly cleared them
                pass
        
        return cleaned_data
    
    def clean_license_plate(self):
        """Validate license plate is unique and formatted correctly."""
        license_plate = self.cleaned_data.get('license_plate')
        
        if license_plate:
            # Convert to uppercase
            license_plate = license_plate.upper()
            
            # Check if license plate already exists (excluding current instance)
            if Vehicle.objects.filter(license_plate=license_plate).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("A vehicle with this license plate already exists.")
        
        return license_plate
    
    def clean_vin(self):
        """Validate VIN is unique and formatted correctly."""
        vin = self.cleaned_data.get('vin')
        
        if vin:
            # Convert to uppercase
            vin = vin.upper()
            
            # Check if VIN already exists (excluding current instance)
            if Vehicle.objects.filter(vin=vin).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("A vehicle with this VIN already exists.")
        
        return vin