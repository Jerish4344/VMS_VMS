# maintenance/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin
from .models import Maintenance, MaintenanceType, MaintenanceProvider
from .forms import MaintenanceForm, MaintenanceTypeForm, MaintenanceProviderForm
from vehicles.models import Vehicle

class MaintenanceListView(LoginRequiredMixin, ListView):
    model = Maintenance
    template_name = 'maintenance/maintenance_list.html'
    context_object_name = 'maintenance_records'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('vehicle', 'maintenance_type', 'provider', 'reported_by')
        
        # Search functionality
        search_query = self.request.GET.get('search', None)
        if search_query:
            queryset = queryset.filter(
                vehicle__license_plate__icontains=search_query
            ) | queryset.filter(
                maintenance_type__name__icontains=search_query
            ) | queryset.filter(
                provider__name__icontains=search_query
            )
            
        # Filter by status
        status_filter = self.request.GET.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # Filter by vehicle
        vehicle_filter = self.request.GET.get('vehicle', None)
        if vehicle_filter:
            queryset = queryset.filter(vehicle_id=vehicle_filter)
            
        # Filter by maintenance type
        type_filter = self.request.GET.get('type', None)
        if type_filter:
            queryset = queryset.filter(maintenance_type_id=type_filter)
            
        # Default ordering
        return queryset.order_by('-date_reported')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicles'] = Vehicle.objects.all()
        context['maintenance_types'] = MaintenanceType.objects.all()
        # Fix: Access the choices through the model's meta
        context['statuses'] = dict(Maintenance._meta.get_field('status').choices)
        
        # Add these lines to calculate status counts
        context['scheduled_count'] = Maintenance.objects.filter(status='scheduled').count()
        context['in_progress_count'] = Maintenance.objects.filter(status='in_progress').count()
        context['completed_count'] = Maintenance.objects.filter(status='completed').count()
        context['cancelled_count'] = Maintenance.objects.filter(status='cancelled').count()
        
        # You might also want to add this for the quick links section
        context['maintenance_providers_count'] = MaintenanceProvider.objects.count()
        
        return context

class MaintenanceDetailView(LoginRequiredMixin, DetailView):
    model = Maintenance
    template_name = 'maintenance/maintenance_detail.html'
    context_object_name = 'maintenance'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add related maintenance records for the same vehicle
        context['related_records'] = Maintenance.objects.filter(
            vehicle=self.object.vehicle
        ).exclude(id=self.object.id).order_by('-date_reported')[:5]
        return context

class MaintenanceCreateView(VehicleManagerRequiredMixin, CreateView):
    model = Maintenance
    form_class = MaintenanceForm
    template_name = 'maintenance/maintenance_form.html'
    success_url = reverse_lazy('maintenance_list')
    
    def form_valid(self, form):
        # Set the reported_by field to the current user
        form.instance.reported_by = self.request.user
        # If the status is changed to 'in_progress' or 'completed', update vehicle status
        if form.instance.status == 'in_progress':
            vehicle = form.instance.vehicle
            vehicle.status = 'maintenance'
            vehicle.save()
        messages.success(self.request, 'Maintenance record created successfully.')
        return super().form_valid(form)

class MaintenanceUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = Maintenance
    form_class = MaintenanceForm
    template_name = 'maintenance/maintenance_form.html'
    
    def get_success_url(self):
        return reverse_lazy('maintenance_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        # If the status is changed to 'in_progress', update vehicle status
        old_status = self.get_object().status
        new_status = form.instance.status
        
        if old_status != new_status:
            vehicle = form.instance.vehicle
            
            if new_status == 'in_progress':
                vehicle.status = 'maintenance'
                vehicle.save()
            elif old_status == 'in_progress' and new_status == 'completed':
                vehicle.status = 'available'
                vehicle.save()
        
        messages.success(self.request, 'Maintenance record updated successfully.')
        return super().form_valid(form)

class MaintenanceDeleteView(AdminRequiredMixin, DeleteView):
    model = Maintenance
    template_name = 'maintenance/maintenance_confirm_delete.html'
    success_url = reverse_lazy('maintenance_list')
    
    def delete(self, request, *args, **kwargs):
        maintenance = self.get_object()
        # If maintenance was in progress, set vehicle back to available
        if maintenance.status == 'in_progress':
            maintenance.vehicle.status = 'available'
            maintenance.vehicle.save()
        
        messages.success(request, f'Maintenance record for {maintenance.vehicle} has been deleted successfully.')
        return super().delete(request, *args, **kwargs)

# Maintenance Type Views
class MaintenanceTypeListView(VehicleManagerRequiredMixin, ListView):
    model = MaintenanceType
    template_name = 'maintenance/maintenance_type_list.html'
    context_object_name = 'maintenance_types'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', None)
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        return queryset.order_by('name')

class MaintenanceTypeCreateView(VehicleManagerRequiredMixin, CreateView):
    model = MaintenanceType
    form_class = MaintenanceTypeForm
    template_name = 'maintenance/maintenance_type_form.html'
    success_url = reverse_lazy('maintenance_type_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Maintenance type created successfully.')
        return super().form_valid(form)

class MaintenanceTypeUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = MaintenanceType
    form_class = MaintenanceTypeForm
    template_name = 'maintenance/maintenance_type_form.html'
    success_url = reverse_lazy('maintenance_type_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Maintenance type updated successfully.')
        return super().form_valid(form)

class MaintenanceTypeDeleteView(AdminRequiredMixin, DeleteView):
    model = MaintenanceType
    template_name = 'maintenance/maintenance_type_confirm_delete.html'
    success_url = reverse_lazy('maintenance_type_list')
    
    def delete(self, request, *args, **kwargs):
        maintenance_type = self.get_object()
        # Check if this type is being used
        maintenance_count = Maintenance.objects.filter(maintenance_type=maintenance_type).count()
        if maintenance_count > 0:
            messages.error(request, f'Cannot delete "{maintenance_type.name}" because it is being used by {maintenance_count} maintenance record(s).')
            return self.get(request, *args, **kwargs)
        
        messages.success(request, f'Maintenance type "{maintenance_type.name}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)

# Maintenance Provider Views
class MaintenanceProviderListView(VehicleManagerRequiredMixin, ListView):
    model = MaintenanceProvider
    template_name = 'maintenance/maintenance_provider_list.html'
    context_object_name = 'maintenance_providers'

class MaintenanceProviderCreateView(VehicleManagerRequiredMixin, CreateView):
    model = MaintenanceProvider
    form_class = MaintenanceProviderForm
    template_name = 'maintenance/maintenance_provider_form.html'
    success_url = reverse_lazy('maintenance_provider_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Maintenance provider created successfully.')
        return super().form_valid(form)

class MaintenanceProviderUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = MaintenanceProvider
    form_class = MaintenanceProviderForm
    template_name = 'maintenance/maintenance_provider_form.html'
    success_url = reverse_lazy('maintenance_provider_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Maintenance provider updated successfully.')
        return super().form_valid(form)

class MaintenanceProviderDeleteView(AdminRequiredMixin, DeleteView):
    model = MaintenanceProvider
    template_name = 'maintenance/maintenance_provider_confirm_delete.html'
    success_url = reverse_lazy('maintenance_provider_list')
    
    def delete(self, request, *args, **kwargs):
        provider = self.get_object()
        # Check if this provider is being used
        maintenance_count = Maintenance.objects.filter(provider=provider).count()
        if maintenance_count > 0:
            messages.error(request, f'Cannot delete "{provider.name}" because it is being used by {maintenance_count} maintenance record(s).')
            return self.get(request, *args, **kwargs)
        
        messages.success(request, f'Maintenance provider "{provider.name}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)