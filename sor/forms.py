
from django import forms
from .models import SOR
from vehicles.models import Vehicle
from django.contrib.auth import get_user_model


# Custom ChoiceField that allows any value if 'Others' is selected
class LocationChoiceField(forms.ChoiceField):
    def valid_value(self, value):
        # Allow any value if 'Others' is selected
        return True

class SORForm(forms.ModelForm):
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
        ("Enchakal Warehouse", "Enchakal Warehouse"),
        ("Muthoot Warehouse", "Muthoot Warehouse"),
        ("Hindu Warehouse", "Hindu Warehouse"),
        ("Others", "Others"),
    ]

    from_location = LocationChoiceField(choices=LOCATION_CHOICES, label="From Location", required=True)
    to_location = LocationChoiceField(choices=LOCATION_CHOICES, label="To Location", required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only commercial vehicles
        self.fields['vehicle'].queryset = Vehicle.objects.filter(vehicle_type__category='commercial')
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
        fields = ['goods_value', 'from_location', 'to_location', 'vehicle', 'driver']
