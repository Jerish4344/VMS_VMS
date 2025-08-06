from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin
from .models import Vehicle, VehicleType
from .forms import VehicleForm, VehicleTypeForm
from .utils import import_vehicles_from_excel
import pandas as pd
from django import forms
import io
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = 'vehicles/vehicle_list.html'
    context_object_name = 'vehicles'
    paginate_by = 10 # Optional: if you want pagination

    def get_queryset(self):
        queryset = super().get_queryset().order_by('license_plate') # Start with the base queryset

        search_query = self.request.GET.get('search', '').strip()
        vehicle_type_filter = self.request.GET.get('vehicle_type', '').strip()
        status_filter = self.request.GET.get('status', '').strip()

        if search_query:
            queryset = queryset.filter(
                Q(license_plate__icontains=search_query) |
                Q(make__icontains=search_query) |
                Q(model__icontains=search_query)
            )
        
        if vehicle_type_filter:
            queryset = queryset.filter(vehicle_type_id=vehicle_type_filter)
            
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate status counts from all vehicles (not just the filtered ones)
        all_vehicles = Vehicle.objects.all()
        context['available_count'] = all_vehicles.filter(status='available').count()
        context['in_use_count'] = all_vehicles.filter(status='in_use').count()
        context['maintenance_count'] = all_vehicles.filter(status='maintenance').count()
        context['retired_count'] = all_vehicles.filter(status='retired').count()
        
        context['vehicle_types'] = VehicleType.objects.all()
        
        # To keep filter values in the form after submission
        context['search_params'] = self.request.GET
        return context

class VehicleDetailView(LoginRequiredMixin, DetailView):
    model = Vehicle
    template_name = 'vehicles/vehicle_detail.html'
    context_object_name = 'vehicle'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()
        context['documents'] = vehicle.documents.all()
        context['maintenance_records'] = vehicle.maintenance_records.all()
        context['fuel_transactions'] = vehicle.fuel_transactions.all()
        context['trips'] = vehicle.trips.all().order_by('-start_time')[:10]  # Last 10 trips
        context['accidents'] = vehicle.accidents.all()
        return context

class VehicleCreateView(VehicleManagerRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Auto-create documents from vehicle data
        from documents.models import Document
        Document.create_from_vehicle(self.object)
        
        return response

class VehicleUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'
    
    def get_success_url(self):
        return reverse_lazy('vehicle_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Auto-create documents from vehicle data if updated
        from documents.models import Document
        Document.create_from_vehicle(self.object)
        
        return response

class VehicleDeleteView(AdminRequiredMixin, DeleteView):
    model = Vehicle
    template_name = 'vehicles/vehicle_confirm_delete.html'
    success_url = reverse_lazy('vehicle_list')

# VehicleType views
class VehicleTypeListView(VehicleManagerRequiredMixin, ListView):
    model = VehicleType
    template_name = 'vehicles/vehicle_type_list.html'
    context_object_name = 'vehicle_types'

class VehicleTypeCreateView(VehicleManagerRequiredMixin, CreateView):
    model = VehicleType
    form_class = VehicleTypeForm
    template_name = 'vehicles/vehicle_type_form.html'
    success_url = reverse_lazy('vehicle_type_list')

class VehicleTypeUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = VehicleType
    form_class = VehicleTypeForm
    template_name = 'vehicles/vehicle_type_form.html'
    success_url = reverse_lazy('vehicle_type_list')

class ImportVehiclesView(AdminRequiredMixin, FormView):
    template_name = 'vehicles/import_vehicles.html'
    form_class = forms.Form
    success_url = reverse_lazy('vehicle_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['excel_file'] = forms.FileField(
            label='Excel File',
            help_text='Upload Excel file with vehicle data (.xlsx or .xls format)',
            widget=forms.FileInput(attrs={
                'accept': '.xlsx,.xls',
                'class': 'form-control'
            })
        )
        form.fields['preview_only'] = forms.BooleanField(
            label='Preview Only',
            required=False,
            initial=True,
            help_text='Check to preview data without importing',
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
        )
        return form
    
    def form_valid(self, form):
        excel_file = form.cleaned_data['excel_file']
        preview_only = form.cleaned_data['preview_only']
        
        try:
            # Validate file type
            if not excel_file.name.lower().endswith(('.xlsx', '.xls')):
                messages.error(self.request, 'Please upload a valid Excel file (.xlsx or .xls)')
                return self.form_invalid(form)
            
            # Read the Excel file with better error handling
            try:
                # Try to read the file to validate it's a proper Excel file
                df = pd.read_excel(excel_file, skiprows=2)  # Skip first 2 rows as they seem to be empty
                
                # Clean column names
                df.columns = [str(col).strip() if col else f'Column_{i}' for i, col in enumerate(df.columns)]
                
                # Remove completely empty rows
                df = df.dropna(how='all')
                
            except Exception as e:
                messages.error(self.request, f'Error reading Excel file: {str(e)}')
                return self.form_invalid(form)
            
            # If preview only, show the data
            if preview_only:
                # Limit to first 10 rows for preview
                preview_data = df.head(10)
                
                # Create better HTML table
                html_table = preview_data.to_html(
                    classes='table table-striped table-bordered',
                    table_id='preview-table',
                    escape=False,
                    index=False
                )
                
                context = self.get_context_data(
                    form=form,
                    preview_data=html_table,
                    file_name=excel_file.name,
                    total_rows=len(df),
                    columns=list(df.columns)
                )
                return render(self.request, self.template_name, context)
            
            # Otherwise, import the data
            # Reset file pointer to beginning
            excel_file.seek(0)
            
            # Create a temporary file-like object
            temp_file = io.BytesIO()
            temp_file.write(excel_file.read())
            temp_file.seek(0)
            
            # Import the vehicles
            result = import_vehicles_from_excel(temp_file)
            
            # Show success message
            if result['success_count'] > 0:
                messages.success(
                    self.request, 
                    f"Successfully imported {result['success_count']} vehicles."
                )
                
                # Show which vehicles were imported
                if result['imported_vehicles']:
                    imported_list = ', '.join(result['imported_vehicles'][:10])  # Show first 10
                    if len(result['imported_vehicles']) > 10:
                        imported_list += f" and {len(result['imported_vehicles']) - 10} more..."
                    messages.info(self.request, f"Imported vehicles: {imported_list}")
            
            # Show error message if any
            if result['error_count'] > 0:
                error_message = f"Failed to import {result['error_count']} vehicles."
                if result['errors']:
                    # Show first few errors
                    error_details = '; '.join(result['errors'][:3])
                    if len(result['errors']) > 3:
                        error_details += f" and {len(result['errors']) - 3} more errors..."
                    error_message += f" Errors: {error_details}"
                messages.error(self.request, error_message)
            
            # If no vehicles were processed at all
            if result['success_count'] == 0 and result['error_count'] == 0:
                messages.warning(
                    self.request, 
                    "No valid vehicle data found in the Excel file. Please check the file format and try again."
                )
            
            return redirect(self.success_url)
            
        except Exception as e:
            messages.error(self.request, f"Unexpected error during import: {str(e)}")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        # Add custom error handling
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)
    

@require_http_methods(["GET"])
def vehicle_details_api(request, vehicle_id):
    """API endpoint to get vehicle details for forms."""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    
    data = {
        'id': vehicle.id,
        'license_plate': vehicle.license_plate,
        'make': vehicle.make,
        'model': vehicle.model,
        'year': vehicle.year,
        'vehicle_type_name': vehicle.vehicle_type.name,
        'fuel_type': vehicle.fuel_type or 'Electric' if vehicle.is_electric() else vehicle.fuel_type,
        'current_odometer': vehicle.current_odometer,
        'is_electric': vehicle.is_electric(),
        'is_commercial': vehicle.is_commercial(),
        'seating_capacity': vehicle.seating_capacity,
        'status': vehicle.status,
    }
    
    # Add electric vehicle specific data
    if vehicle.is_electric():
        data.update({
            'battery_capacity_kwh': float(vehicle.battery_capacity_kwh) if vehicle.battery_capacity_kwh else None,
            'range_per_charge': vehicle.range_per_charge,
            'charging_type': vehicle.charging_type,
        })
    else:
        # Add fuel vehicle specific data
        data.update({
            'fuel_capacity': float(vehicle.fuel_capacity) if vehicle.fuel_capacity else None,
            'average_mileage': float(vehicle.average_mileage) if vehicle.average_mileage else None,
        })
    
    # Add commercial vehicle data
    if vehicle.is_commercial():
        data['load_capacity_kg'] = float(vehicle.load_capacity_kg) if vehicle.load_capacity_kg else None
    
    return JsonResponse(data)