"""
Forms for the Generator module.

This includes forms for:
1. Store details
2. Generator information
3. Usage tracking
4. Fuel entries
5. Maintenance logs

Each form includes appropriate validation and widgets to enhance the user experience.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Store, Generator, UsageTracking, FuelEntry, MaintenanceLog


class StoreForm(forms.ModelForm):
    """Form for creating and updating Store information."""

    class Meta:
        model = Store
        fields = ["name", "location", "manager_name", "contact_info"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Store Name/Code"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Location"}),
            "manager_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Manager Name (Optional)"}),
            "contact_info": forms.TextInput(attrs={"class": "form-control", "placeholder": "Contact Information"}),
        }


class GeneratorForm(forms.ModelForm):
    """Form for creating and updating Generator information."""

    class Meta:
        model = Generator
        fields = ["store", "make_and_model", "capacity_kva", "fuel_type", "serial_number"]
        widgets = {
            "store": forms.Select(attrs={"class": "form-select"}),
            "make_and_model": forms.TextInput(attrs={"class": "form-control", "placeholder": "Make & Model"}),
            "capacity_kva": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Capacity (kVA)"}),
            "fuel_type": forms.Select(attrs={"class": "form-select"}),
            "serial_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Serial Number (Optional)"}),
        }

    def clean_capacity_kva(self):
        """Ensure capacity is a positive number."""
        capacity = self.cleaned_data.get("capacity_kva")
        if capacity is not None and capacity <= 0:
            raise ValidationError("Capacity must be a positive number")
        return capacity


class UsageTrackingForm(forms.ModelForm):
    """Form for tracking generator usage."""

    class Meta:
        model = UsageTracking
        fields = ["generator", "date", "start_time", "end_time", "reason_for_use", "observations"]
        widgets = {
            "generator": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "end_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "reason_for_use": forms.TextInput(attrs={"class": "form-control", "placeholder": "Reason for Use"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Observations/Comments"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form with store filtering."""
        store_id = kwargs.pop('store_id', None)
        super().__init__(*args, **kwargs)
        
        # If a store is specified, filter generators by that store
        if store_id:
            self.fields['generator'].queryset = Generator.objects.filter(store_id=store_id)

    def clean(self):
        """Validate form data and calculate total hours run."""
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        
        if start_time and end_time:
            # Convert to datetime for comparison
            date = cleaned_data.get("date") or timezone.now().date()
            start_dt = datetime.combine(date, start_time)
            end_dt = datetime.combine(date, end_time)
            
            # Handle overnight running by adding a day if end_time < start_time
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            
            # Calculate hours difference
            time_diff = end_dt - start_dt
            hours_run = time_diff.total_seconds() / 3600
            
            if hours_run <= 0:
                raise ValidationError("End time must be after start time")
            
            # Add calculated field to cleaned_data
            cleaned_data["total_hours_run"] = round(Decimal(hours_run), 2)
        
        return cleaned_data


class FuelEntryForm(forms.ModelForm):
    """Form for recording generator fuel entries."""

    class Meta:
        model = FuelEntry
        fields = [
            "date_of_filling", "store", "generator", "fuel_type", 
            "litres_filled", "fuel_rate_per_litre", "invoice_number", 
            "vendor_name", "filled_by", "comments"
        ]
        widgets = {
            "date_of_filling": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "store": forms.Select(attrs={"class": "form-select"}),
            "generator": forms.Select(attrs={"class": "form-select"}),
            "fuel_type": forms.Select(attrs={"class": "form-select"}),
            "litres_filled": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Litres Filled", "step": "0.01"}),
            "fuel_rate_per_litre": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Rate per Litre", "step": "0.01"}),
            "invoice_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Invoice Number (Optional)"}),
            "vendor_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Vendor Name (Optional)"}),
            "filled_by": forms.Select(attrs={"class": "form-select"}),
            "comments": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Purpose/Comments"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form with dynamic generator filtering."""
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set the current user as default for filled_by
        if user and not self.instance.pk:
            self.fields['filled_by'].initial = user
        
        # Add a calculated field for total cost preview
        self.fields['total_cost_preview'] = forms.DecimalField(
            required=False,
            disabled=True,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly',
                'placeholder': 'Auto-calculated'
            })
        )
        
        # Add JavaScript for client-side calculation
        self.fields['litres_filled'].widget.attrs.update({
            'onchange': 'calculateTotalCost()',
            'onkeyup': 'calculateTotalCost()'
        })
        self.fields['fuel_rate_per_litre'].widget.attrs.update({
            'onchange': 'calculateTotalCost()',
            'onkeyup': 'calculateTotalCost()'
        })

    def clean(self):
        """Validate form data and ensure positive numbers."""
        cleaned_data = super().clean()
        litres = cleaned_data.get("litres_filled")
        rate = cleaned_data.get("fuel_rate_per_litre")
        
        if litres is not None and litres <= 0:
            self.add_error("litres_filled", "Litres filled must be a positive number")
        
        if rate is not None and rate <= 0:
            self.add_error("fuel_rate_per_litre", "Fuel rate must be a positive number")
        
        # Update store-generator relationship
        store = cleaned_data.get("store")
        generator = cleaned_data.get("generator")
        
        if store and generator and generator.store != store:
            self.add_error("generator", "This generator does not belong to the selected store")
        
        return cleaned_data


class MaintenanceLogForm(forms.ModelForm):
    """Form for recording generator maintenance logs."""

    class Meta:
        model = MaintenanceLog
        fields = [
            "generator", "date_of_service", "service_type", 
            "next_scheduled_maintenance", "service_provider", 
            "invoice_number", "amount"
        ]
        widgets = {
            "generator": forms.Select(attrs={"class": "form-select"}),
            "date_of_service": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "service_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "Type of Service"}),
            "next_scheduled_maintenance": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "service_provider": forms.TextInput(attrs={"class": "form-control", "placeholder": "Service Provider/Technician"}),
            "invoice_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Invoice Number (Optional)"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Amount", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form with store filtering."""
        store_id = kwargs.pop('store_id', None)
        super().__init__(*args, **kwargs)
        
        # If a store is specified, filter generators by that store
        if store_id:
            self.fields['generator'].queryset = Generator.objects.filter(store_id=store_id)
        
        # Set default next maintenance date (3 months from service date)
        if not self.instance.pk:  # Only for new instances
            self.fields['next_scheduled_maintenance'].initial = (
                timezone.now() + timedelta(days=90)
            ).date()

    def clean(self):
        """Validate form data and ensure dates are logical."""
        cleaned_data = super().clean()
        service_date = cleaned_data.get("date_of_service")
        next_maintenance = cleaned_data.get("next_scheduled_maintenance")
        amount = cleaned_data.get("amount")
        
        if service_date and next_maintenance and next_maintenance < service_date:
            self.add_error(
                "next_scheduled_maintenance", 
                "Next scheduled maintenance date cannot be before the service date"
            )
        
        if amount is not None and amount < 0:
            self.add_error("amount", "Amount cannot be negative")
        
        return cleaned_data
