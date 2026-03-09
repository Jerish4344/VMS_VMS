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
    class Meta:
        model = SOR
        fields = [
            'goods_value', 'from_location', 'to_location', 'vehicle', 'driver',
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
