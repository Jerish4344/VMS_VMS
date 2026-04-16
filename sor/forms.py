from django import forms
from .models import SOR
from vehicles.models import Vehicle
from django.contrib.auth import get_user_model
from trips.models import Trip

# Custom ChoiceField that allows any value if 'Others' is selected
class LocationChoiceField(forms.ChoiceField):
    def valid_value(self, value):
        # Allow any value if 'Others' is selected
        return True

class SORForm(forms.ModelForm):
    source_type = forms.ChoiceField(
        choices=SOR.SOURCE_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    outsourced_vehicle_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter outsourced vehicle details'
        })
    )
    outsourced_driver_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter outsourced driver details'
        })
    )
    vendor_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter vendor name (optional)'
        })
    )
    start_odometer = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter start odometer',
            'step': '0.01'
        })
    )
    end_odometer = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter end odometer',
            'step': '0.01'
        })
    )
    outsourced_rate_per_km = forms.DecimalField(
        required=False,
        min_value=0,
        initial=25,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Rate per KM (default: 25)',
            'step': '0.01'
        })
    )

    # Add custom widgets for new fields to match UI
    number_of_crates = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter number of crates (optional)',
            'min': 0
        })
    )
    number_of_sac = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter number of sac (optional)',
            'min': 0
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Describe contents of crates or sac (optional)',
            'rows': 2
        })
    )
    LOCATION_CHOICES = [
        ("", "---------"),
        ("Attakulangara", "Attakulangara"),
        ("Pazhavangadi", "Pazhavangadi"),
        ("Enchakkal", "Enchakkal"),
        ("Ulloor", "Ulloor"),
        ("Attingal", "Attingal"),
        ("Vellayamvbalam", "Vellayamvbalam"),
        ("Mall Of Travancore", "Mall Of Travancore"),
        ("Neyyatinkara", "Neyyatinkara"),
        ("Courtallam", "Courtallam"),
        ("Thirumala", "Thirumala"),
        ("Nedumangadu", "Nedumangadu"),
        ("Karakkamandapam", "Karakkamandapam"),
        ("Marthandam", "Marthandam"),
        ("Panachamoodu", "Panachamoodu"),
        ("kattakada", "kattakada"),
        ("Kodapanamkunnu", "Kodapanamkunnu"),
        ("Kaval Kinaru", "Kaval Kinaru"),
        ("Ooty", "Ooty"),
        ("Hosur", "Hosur"),
        ("Enchakal Warehouse", "Enchakal Warehouse"),
        ("Muthoot Warehouse", "Muthoot Warehouse"),
        ("Hindu Warehouse", "Hindu Warehouse"),
        ("Others", "Others"),
    ]

    from_location = LocationChoiceField(choices=LOCATION_CHOICES, label="From Location", required=True)
    to_location = LocationChoiceField(choices=LOCATION_CHOICES, label="To Location", required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only commercial vehicles that are not currently on an ongoing trip
        ongoing_vehicle_ids = Trip.objects.filter(status='ongoing').values_list('vehicle_id', flat=True)
        self.fields['vehicle'].queryset = Vehicle.objects.filter(vehicle_type__category='commercial').exclude(id__in=ongoing_vehicle_ids)
        self.fields['vehicle'].widget.attrs.update({'class': 'form-select form-select-sm'})
        User = get_user_model()
        self.fields['driver'].queryset = User.objects.filter(user_type='driver', is_active=True)
        self.fields['driver'].widget.attrs.update({'class': 'form-select form-select-sm'})
        self.fields['goods_value'].widget.attrs.update({'class': 'form-control form-control-sm'})
        self.fields['from_location'].widget.attrs.update({'class': 'form-select form-select-sm'})
        self.fields['to_location'].widget.attrs.update({'class': 'form-select form-select-sm'})

        # Allow outsourced mode to be pre-selected from URL query param
        if self.initial.get('source_type') == 'outsourced_manual':
            self.fields['source_type'].initial = 'outsourced_manual'

    def clean_from_location(self):
        value = self.cleaned_data.get('from_location')
        if value == 'Others':
            other = self.data.get('from_location_other', '').strip()
            if other:
                return other
        return value

    def clean_to_location(self):
        value = self.cleaned_data.get('to_location')
        if value == 'Others':
            other = self.data.get('to_location_other', '').strip()
            if other:
                return other
        return value

    def clean(self):
        cleaned_data = super().clean()
        source_type = cleaned_data.get('source_type')
        start_odometer = cleaned_data.get('start_odometer')
        end_odometer = cleaned_data.get('end_odometer')

        if source_type == 'outsourced_manual':
            if not cleaned_data.get('outsourced_vehicle_text'):
                self.add_error('outsourced_vehicle_text', 'Vehicle is required for outsourced entry.')
            if not cleaned_data.get('outsourced_driver_text'):
                self.add_error('outsourced_driver_text', 'Driver is required for outsourced entry.')
            if start_odometer is None:
                self.add_error('start_odometer', 'Start odometer is required for outsourced entry.')
            if end_odometer is None:
                self.add_error('end_odometer', 'End odometer is required for outsourced entry.')
            if start_odometer is not None and end_odometer is not None and end_odometer < start_odometer:
                self.add_error('end_odometer', 'End odometer must be greater than or equal to start odometer.')

            # Outsourced entries do not use internal vehicle/driver assignment workflow.
            cleaned_data['vehicle'] = None
            cleaned_data['driver'] = None
        else:
            if not cleaned_data.get('vehicle'):
                self.add_error('vehicle', 'Vehicle is required for company vehicle entry.')
            if not cleaned_data.get('driver'):
                self.add_error('driver', 'Driver is required for company vehicle entry.')

        return cleaned_data

    class Meta:
        model = SOR
        fields = [
            'source_type',
            'goods_value', 'from_location', 'to_location',
            'vehicle', 'driver',
            'outsourced_vehicle_text', 'outsourced_driver_text', 'vendor_name',
            'start_odometer', 'end_odometer', 'outsourced_rate_per_km',
            'number_of_crates', 'number_of_sac', 'description'
        ]


class SORFilterForm(forms.Form):
    """Form for filtering SOR entries"""
    
    LOCATION_CHOICES = [
        ("", "All Locations"),
        ("Attakulangara", "Attakulangara"),
        ("Pazhavangadi", "Pazhavangadi"),
        ("Enchakkal", "Enchakkal"),
        ("Ulloor", "Ulloor"),
        ("Attingal", "Attingal"),
        ("Vellayamvbalam", "Vellayamvbalam"),
        ("Mall Of Travancore", "Mall Of Travancore"),
        ("Neyyatinkara", "Neyyatinkara"),
        ("Courtallam", "Courtallam"),
        ("Thirumala", "Thirumala"),
        ("Nedumangadu", "Nedumangadu"),
        ("Karakkamandapam", "Karakkamandapam"),
        ("Marthandam", "Marthandam"),
        ("Panachamoodu", "Panachamoodu"),
        ("kattakada", "kattakada"),
        ("Kodapanamkunnu", "Kodapanamkunnu"),
        ("Kaval Kinaru", "Kaval Kinaru"),
        ("Ooty", "Ooty"),
        ("Hosur", "Hosur"),
        ("Enchakal Warehouse", "Enchakal Warehouse"),
        ("Muthoot Warehouse", "Muthoot Warehouse"),
        ("Hindu Warehouse", "Hindu Warehouse"),
    ]
    
    STATUS_CHOICES = [
        ("", "All Status"),
        ("pending", "Pending"),
        ("driver_accepted", "Driver Accepted"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("", "All Types"),
        ("company", "Company Vehicle"),
        ("outsourced_manual", "Outsourced Manual Entry"),
    ]
    
    # Filter fields
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search by SOR ID, goods value...'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    source_type = forms.ChoiceField(
        choices=SOURCE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    from_location = forms.ChoiceField(
        choices=LOCATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    to_location = forms.ChoiceField(
        choices=LOCATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.filter(vehicle_type__category='commercial'),
        required=False,
        empty_label="All Vehicles",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    driver = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="All Drivers",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )

    # Hidden fields for sorting
    sort = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    order = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields['driver'].queryset = User.objects.filter(user_type='driver', is_active=True)
