"""
Views for the Generator module.

This module provides views for:
1. Store management
2. Generator information
3. Usage tracking
4. Fuel entries
5. Maintenance logs

Each set of views includes list, create, update, and delete functionality
with appropriate permissions and filtering.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Avg, Count
from django.http import JsonResponse
from django.utils import timezone

from .models import Store, Generator, UsageTracking, FuelEntry, MaintenanceLog
from .forms import StoreForm, GeneratorForm, UsageTrackingForm, FuelEntryForm, MaintenanceLogForm


# --------------------------------------------------------------------------- #
#  Mixins and Base Classes
# --------------------------------------------------------------------------- #

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only staff users can access views."""
    
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or 
            self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']
        )


class GeneratorBaseView:
    """Base view for Generator module with common methods."""
    
    def get_context_data(self, **kwargs):
        """Add common context data for generator views."""
        context = super().get_context_data(**kwargs)
        context['module_title'] = 'Generator Management'
        context['active_module'] = 'generators'
        return context


# --------------------------------------------------------------------------- #
#  Dashboard Views
# --------------------------------------------------------------------------- #

class GeneratorDashboardView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, TemplateView):
    """Dashboard for Generator module showing key metrics and recent activities."""
    
    template_name = 'generators/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get counts
        context['store_count'] = Store.objects.count()
        context['generator_count'] = Generator.objects.count()
        
        # Recent activities
        context['recent_usage'] = UsageTracking.objects.select_related(
            'generator', 'generator__store'
        ).order_by('-date', '-start_time')[:5]
        
        context['recent_fuel'] = FuelEntry.objects.select_related(
            'generator', 'store', 'filled_by'
        ).order_by('-date_of_filling')[:5]
        
        context['recent_maintenance'] = MaintenanceLog.objects.select_related(
            'generator'
        ).order_by('-date_of_service')[:5]
        
        # Get upcoming maintenance
        context['upcoming_maintenance'] = MaintenanceLog.objects.select_related(
            'generator'
        ).filter(
            next_scheduled_maintenance__gte=timezone.now().date()
        ).order_by('next_scheduled_maintenance')[:5]
        
        # Fuel consumption statistics
        context['total_fuel_consumed'] = FuelEntry.objects.aggregate(
            total=Sum('litres_filled')
        )['total'] or 0
        
        context['total_fuel_cost'] = FuelEntry.objects.aggregate(
            total=Sum('total_fuel_cost')
        )['total'] or 0
        
        return context


# --------------------------------------------------------------------------- #
#  Store Views
# --------------------------------------------------------------------------- #

class StoreListView(LoginRequiredMixin, GeneratorBaseView, ListView):
    """List all stores with search and filtering."""
    
    model = Store
    template_name = 'generators/store_list.html'
    context_object_name = 'stores'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(manager_name__icontains=search_query)
            )
        
        return queryset.annotate(
            generator_count=Count('generators')
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['title'] = 'Store List'
        return context


class StoreDetailView(LoginRequiredMixin, GeneratorBaseView, DetailView):
    """Show detailed information about a store and its generators."""
    
    model = Store
    template_name = 'generators/store_detail.html'
    context_object_name = 'store'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.get_object()
        
        context['generators'] = Generator.objects.filter(store=store)
        context['generator_count'] = context['generators'].count()
        
        # Get fuel statistics
        fuel_stats = FuelEntry.objects.filter(store=store).aggregate(
            total_litres=Sum('litres_filled'),
            total_cost=Sum('total_fuel_cost'),
            avg_rate=Avg('fuel_rate_per_litre')
        )
        
        context['fuel_stats'] = fuel_stats
        context['title'] = f'Store: {store.name}'
        
        return context


class StoreCreateView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, CreateView):
    """Create a new store."""
    
    model = Store
    form_class = StoreForm
    template_name = 'generators/store_form.html'
    # Use fully-qualified URL name with namespace
    success_url = reverse_lazy('generators:store_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Store'
        context['action'] = 'Create'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Store '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class StoreUpdateView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, UpdateView):
    """Update an existing store."""
    
    model = Store
    form_class = StoreForm
    template_name = 'generators/store_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Store: {self.object.name}'
        context['action'] = 'Update'
        return context
    
    def get_success_url(self):
        # Redirect using namespaced URL
        return reverse('generators:store_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Store '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class StoreDeleteView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, DeleteView):
    """Delete a store."""
    
    model = Store
    template_name = 'generators/store_confirm_delete.html'
    # Use namespaced list URL
    success_url = reverse_lazy('generators:store_list')
    context_object_name = 'store'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Store: {self.object.name}'
        
        # Check if store has generators
        context['has_generators'] = self.object.generators.exists()
        
        return context
    
    def delete(self, request, *args, **kwargs):
        store = self.get_object()
        store_name = store.name
        
        # Check if store has generators
        if store.generators.exists():
            messages.error(request, f"Cannot delete store '{store_name}' as it has generators assigned to it.")
            # Redirect using namespaced detail URL
            return redirect('generators:store_detail', pk=store.pk)
        
        messages.success(request, f"Store '{store_name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
#  Generator Views
# --------------------------------------------------------------------------- #

class GeneratorListView(LoginRequiredMixin, GeneratorBaseView, ListView):
    """List all generators with search and filtering."""
    
    model = Generator
    template_name = 'generators/generator_list.html'
    context_object_name = 'generators'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('store')
        search_query = self.request.GET.get('search', '')
        store_filter = self.request.GET.get('store', '')
        fuel_type_filter = self.request.GET.get('fuel_type', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(make_and_model__icontains=search_query) |
                Q(serial_number__icontains=search_query) |
                Q(store__name__icontains=search_query)
            )
        
        if store_filter:
            queryset = queryset.filter(store_id=store_filter)
            
        if fuel_type_filter:
            queryset = queryset.filter(fuel_type=fuel_type_filter)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['store_filter'] = self.request.GET.get('store', '')
        context['fuel_type_filter'] = self.request.GET.get('fuel_type', '')
        
        # Get all stores for filter dropdown
        context['stores'] = Store.objects.all()
        context['fuel_types'] = [choice for choice in Generator._meta.get_field('fuel_type').choices]
        
        context['title'] = 'Generator List'
        return context


class GeneratorDetailView(LoginRequiredMixin, GeneratorBaseView, DetailView):
    """Show detailed information about a generator."""
    
    model = Generator
    template_name = 'generators/generator_detail.html'
    context_object_name = 'generator'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        generator = self.get_object()
        
        # Get usage statistics
        usage_stats = UsageTracking.objects.filter(generator=generator).aggregate(
            total_hours=Sum('total_hours_run'),
            usage_count=Count('id')
        )
        
        # Get fuel statistics
        fuel_stats = FuelEntry.objects.filter(generator=generator).aggregate(
            total_litres=Sum('litres_filled'),
            total_cost=Sum('total_fuel_cost'),
            fuel_count=Count('id')
        )
        
        # Get maintenance statistics
        maintenance_stats = MaintenanceLog.objects.filter(generator=generator).aggregate(
            total_maintenance=Count('id'),
            total_cost=Sum('amount')
        )
        
        # Get recent usage
        context['recent_usage'] = UsageTracking.objects.filter(
            generator=generator
        ).order_by('-date', '-start_time')[:5]
        
        # Get recent fuel entries
        context['recent_fuel'] = FuelEntry.objects.filter(
            generator=generator
        ).order_by('-date_of_filling')[:5]
        
        # Get recent maintenance
        context['recent_maintenance'] = MaintenanceLog.objects.filter(
            generator=generator
        ).order_by('-date_of_service')[:5]
        
        # Get next scheduled maintenance
        try:
            context['next_maintenance'] = MaintenanceLog.objects.filter(
                generator=generator,
                next_scheduled_maintenance__gte=timezone.now().date()
            ).order_by('next_scheduled_maintenance').first()
        except MaintenanceLog.DoesNotExist:
            context['next_maintenance'] = None
        
        context['usage_stats'] = usage_stats
        context['fuel_stats'] = fuel_stats
        context['maintenance_stats'] = maintenance_stats
        context['title'] = f'Generator: {generator.make_and_model}'
        
        return context


class GeneratorCreateView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, CreateView):
    """Create a new generator."""
    
    model = Generator
    form_class = GeneratorForm
    template_name = 'generators/generator_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Generator'
        context['action'] = 'Create'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Generator '{form.instance.make_and_model}' created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('generators:generator_detail', kwargs={'pk': self.object.pk})


class GeneratorUpdateView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, UpdateView):
    """Update an existing generator."""
    
    model = Generator
    form_class = GeneratorForm
    template_name = 'generators/generator_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Generator: {self.object.make_and_model}'
        context['action'] = 'Update'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Generator '{form.instance.make_and_model}' updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        # Redirect using namespaced URL
        return reverse('generators:generator_detail', kwargs={'pk': self.object.pk})


class GeneratorDeleteView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, DeleteView):
    """Delete a generator."""
    
    model = Generator
    template_name = 'generators/generator_confirm_delete.html'
    success_url = reverse_lazy('generators:generator_list')
    context_object_name = 'generator'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Generator: {self.object.make_and_model}'
        
        # Check if generator has related records
        context['has_usage'] = self.object.usage_logs.exists()
        context['has_fuel'] = self.object.fuel_entries.exists()
        context['has_maintenance'] = self.object.maintenance_logs.exists()
        
        return context
    
    def delete(self, request, *args, **kwargs):
        generator = self.get_object()
        generator_name = generator.make_and_model
        
        # Check if generator has related records
        if (generator.usage_logs.exists() or 
            generator.fuel_entries.exists() or 
            generator.maintenance_logs.exists()):
            messages.error(
                request, 
                f"Cannot delete generator '{generator_name}' as it has related records. "
                f"Please delete those records first or consider marking it as inactive."
            )
            return redirect('generators:generator_detail', pk=generator.pk)
        
        messages.success(request, f"Generator '{generator_name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
#  Usage Tracking Views
# --------------------------------------------------------------------------- #

class UsageTrackingListView(LoginRequiredMixin, GeneratorBaseView, ListView):
    """List all usage tracking records with search and filtering."""
    
    model = UsageTracking
    template_name = 'generators/usage_tracking_list.html'
    context_object_name = 'usage_records'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('generator', 'generator__store')
        search_query = self.request.GET.get('search', '')
        generator_filter = self.request.GET.get('generator', '')
        store_filter = self.request.GET.get('store', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(reason_for_use__icontains=search_query) |
                Q(observations__icontains=search_query) |
                Q(generator__make_and_model__icontains=search_query)
            )
        
        if generator_filter:
            queryset = queryset.filter(generator_id=generator_filter)
            
        if store_filter:
            queryset = queryset.filter(generator__store_id=store_filter)
            
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
            
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset.order_by('-date', '-start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['generator_filter'] = self.request.GET.get('generator', '')
        context['store_filter'] = self.request.GET.get('store', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Get all stores and generators for filter dropdowns
        context['stores'] = Store.objects.all()
        context['generators'] = Generator.objects.all().select_related('store')
        
        # Get usage statistics
        context['total_hours'] = UsageTracking.objects.aggregate(
            total=Sum('total_hours_run')
        )['total'] or 0
        
        context['title'] = 'Usage Tracking'
        return context


class UsageTrackingCreateView(LoginRequiredMixin, GeneratorBaseView, CreateView):
    """Create a new usage tracking record."""
    
    model = UsageTracking
    form_class = UsageTrackingForm
    template_name = 'generators/usage_tracking_form.html'
    success_url = reverse_lazy('generators:usage_tracking_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        store_id = self.request.GET.get('store', None)
        if store_id:
            kwargs['store_id'] = store_id
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Usage Record'
        context['action'] = 'Create'
        context['stores'] = Store.objects.all()
        return context
    
    def form_valid(self, form):
        # Ensure the calculated hours are persisted
        form.instance.total_hours_run = form.cleaned_data.get("total_hours_run")
        messages.success(
            self.request,
            f"Usage record for {form.instance.generator} on {form.instance.date} created successfully.",
        )
        return super().form_valid(form)


class UsageTrackingUpdateView(LoginRequiredMixin, GeneratorBaseView, UpdateView):
    """Update an existing usage tracking record."""
    
    model = UsageTracking
    form_class = UsageTrackingForm
    template_name = 'generators/usage_tracking_form.html'
    success_url = reverse_lazy('generators:usage_tracking_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.object and self.object.generator and self.object.generator.store:
            kwargs['store_id'] = self.object.generator.store.id
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Usage Record: {self.object.generator} on {self.object.date}'
        context['action'] = 'Update'
        context['stores'] = Store.objects.all()
        return context
    
    def form_valid(self, form):
        # Ensure the calculated hours are persisted
        form.instance.total_hours_run = form.cleaned_data.get("total_hours_run")
        messages.success(
            self.request,
            f"Usage record for {form.instance.generator} on {form.instance.date} updated successfully.",
        )
        return super().form_valid(form)


class UsageTrackingDeleteView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, DeleteView):
    """Delete a usage tracking record."""
    
    model = UsageTracking
    template_name = 'generators/usage_tracking_confirm_delete.html'
    success_url = reverse_lazy('generators:usage_tracking_list')
    context_object_name = 'usage_record'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Usage Record: {self.object.generator} on {self.object.date}'
        return context
    
    def delete(self, request, *args, **kwargs):
        usage_record = self.get_object()
        generator_name = usage_record.generator.make_and_model
        usage_date = usage_record.date
        
        messages.success(
            request, 
            f"Usage record for {generator_name} on {usage_date} deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
#  Fuel Entry Views
# --------------------------------------------------------------------------- #

class FuelEntryListView(LoginRequiredMixin, GeneratorBaseView, ListView):
    """List all fuel entries with search and filtering."""
    
    model = FuelEntry
    template_name = 'generators/fuel_entry_list.html'
    context_object_name = 'fuel_entries'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('generator', 'store', 'filled_by')
        search_query = self.request.GET.get('search', '')
        generator_filter = self.request.GET.get('generator', '')
        store_filter = self.request.GET.get('store', '')
        fuel_type_filter = self.request.GET.get('fuel_type', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search_query) |
                Q(vendor_name__icontains=search_query) |
                Q(comments__icontains=search_query) |
                Q(generator__make_and_model__icontains=search_query)
            )
        
        if generator_filter:
            queryset = queryset.filter(generator_id=generator_filter)
            
        if store_filter:
            queryset = queryset.filter(store_id=store_filter)
            
        if fuel_type_filter:
            queryset = queryset.filter(fuel_type=fuel_type_filter)
            
        if date_from:
            queryset = queryset.filter(date_of_filling__gte=date_from)
            
        if date_to:
            queryset = queryset.filter(date_of_filling__lte=date_to)
        
        return queryset.order_by('-date_of_filling')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['generator_filter'] = self.request.GET.get('generator', '')
        context['store_filter'] = self.request.GET.get('store', '')
        context['fuel_type_filter'] = self.request.GET.get('fuel_type', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Get all stores and generators for filter dropdowns
        context['stores'] = Store.objects.all()
        context['generators'] = Generator.objects.all().select_related('store')
        context['fuel_types'] = [choice for choice in FuelEntry._meta.get_field('fuel_type').choices]
        
        # Get fuel statistics
        fuel_stats = FuelEntry.objects.aggregate(
            total_litres=Sum('litres_filled'),
            total_cost=Sum('total_fuel_cost'),
            avg_rate=Avg('fuel_rate_per_litre')
        )
        
        context['fuel_stats'] = fuel_stats
        context['title'] = 'Fuel Entries'
        return context


class FuelEntryCreateView(LoginRequiredMixin, GeneratorBaseView, CreateView):
    """Create a new fuel entry."""
    
    model = FuelEntry
    form_class = FuelEntryForm
    template_name = 'generators/fuel_entry_form.html'
    success_url = reverse_lazy('generators:fuel_entry_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Fuel Entry'
        context['action'] = 'Create'
        
        # Add JavaScript for dynamic generator filtering by store
        context['js_functions'] = """
        <script>
        function calculateTotalCost() {
            const litres = parseFloat(document.getElementById('id_litres_filled').value) || 0;
            const rate = parseFloat(document.getElementById('id_fuel_rate_per_litre').value) || 0;
            const total = litres * rate;
            document.getElementById('id_total_cost_preview').value = total.toFixed(2);
        }
        
        function updateGenerators() {
            const storeId = document.getElementById('id_store').value;
            const generatorSelect = document.getElementById('id_generator');
            
            // Clear current options
            generatorSelect.innerHTML = '';
            
            if (!storeId) {
                generatorSelect.innerHTML = '<option value="">---------</option>';
                return;
            }
            
            // Fetch generators for the selected store
            fetch(`/generators/api/generators-by-store/${storeId}/`)
                .then(response => response.json())
                .then(data => {
                    generatorSelect.innerHTML = '<option value="">---------</option>';
                    data.forEach(generator => {
                        const option = document.createElement('option');
                        option.value = generator.id;
                        option.textContent = generator.make_and_model;
                        generatorSelect.appendChild(option);
                    });
                });
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('id_store').addEventListener('change', updateGenerators);
            document.getElementById('id_litres_filled').addEventListener('input', calculateTotalCost);
            document.getElementById('id_fuel_rate_per_litre').addEventListener('input', calculateTotalCost);
        });
        </script>
        """
        
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f"Fuel entry for {form.instance.generator} on {form.instance.date_of_filling} created successfully."
        )
        return super().form_valid(form)


class FuelEntryUpdateView(LoginRequiredMixin, GeneratorBaseView, UpdateView):
    """Update an existing fuel entry."""
    
    model = FuelEntry
    form_class = FuelEntryForm
    template_name = 'generators/fuel_entry_form.html'
    success_url = reverse_lazy('generators:fuel_entry_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Fuel Entry: {self.object.generator} on {self.object.date_of_filling}'
        context['action'] = 'Update'
        
        # Add JavaScript for total cost calculation
        context['js_functions'] = """
        <script>
        function calculateTotalCost() {
            const litres = parseFloat(document.getElementById('id_litres_filled').value) || 0;
            const rate = parseFloat(document.getElementById('id_fuel_rate_per_litre').value) || 0;
            const total = litres * rate;
            document.getElementById('id_total_cost_preview').value = total.toFixed(2);
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('id_litres_filled').addEventListener('input', calculateTotalCost);
            document.getElementById('id_fuel_rate_per_litre').addEventListener('input', calculateTotalCost);
            calculateTotalCost(); // Calculate on page load
        });
        </script>
        """
        
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f"Fuel entry for {form.instance.generator} on {form.instance.date_of_filling} updated successfully."
        )
        return super().form_valid(form)


class FuelEntryDeleteView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, DeleteView):
    """Delete a fuel entry."""
    
    model = FuelEntry
    template_name = 'generators/fuel_entry_confirm_delete.html'
    success_url = reverse_lazy('generators:fuel_entry_list')
    context_object_name = 'fuel_entry'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Fuel Entry: {self.object.generator} on {self.object.date_of_filling}'
        return context
    
    def delete(self, request, *args, **kwargs):
        fuel_entry = self.get_object()
        generator_name = fuel_entry.generator.make_and_model
        entry_date = fuel_entry.date_of_filling
        
        messages.success(
            request, 
            f"Fuel entry for {generator_name} on {entry_date} deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
#  Maintenance Log Views
# --------------------------------------------------------------------------- #

class MaintenanceLogListView(LoginRequiredMixin, GeneratorBaseView, ListView):
    """List all maintenance logs with search and filtering."""
    
    model = MaintenanceLog
    template_name = 'generators/maintenance_log_list.html'
    context_object_name = 'maintenance_logs'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('generator', 'generator__store')
        search_query = self.request.GET.get('search', '')
        generator_filter = self.request.GET.get('generator', '')
        store_filter = self.request.GET.get('store', '')
        service_type_filter = self.request.GET.get('service_type', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(service_type__icontains=search_query) |
                Q(service_provider__icontains=search_query) |
                Q(invoice_number__icontains=search_query) |
                Q(generator__make_and_model__icontains=search_query)
            )
        
        if generator_filter:
            queryset = queryset.filter(generator_id=generator_filter)
            
        if store_filter:
            queryset = queryset.filter(generator__store_id=store_filter)
            
        if service_type_filter:
            queryset = queryset.filter(service_type=service_type_filter)
            
        if date_from:
            queryset = queryset.filter(date_of_service__gte=date_from)
            
        if date_to:
            queryset = queryset.filter(date_of_service__lte=date_to)
        
        return queryset.order_by('-date_of_service')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['generator_filter'] = self.request.GET.get('generator', '')
        context['store_filter'] = self.request.GET.get('store', '')
        context['service_type_filter'] = self.request.GET.get('service_type', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Get all stores and generators for filter dropdowns
        context['stores'] = Store.objects.all()
        context['generators'] = Generator.objects.all().select_related('store')
        
        # Get distinct service types for filter
        context['service_types'] = MaintenanceLog.objects.values_list(
            'service_type', flat=True
        ).distinct().order_by('service_type')
        
        # Get maintenance statistics
        maintenance_stats = MaintenanceLog.objects.aggregate(
            total_services=Count('id'),
            total_cost=Sum('amount')
        )
        
        # Get upcoming maintenance
        context['upcoming_maintenance'] = MaintenanceLog.objects.filter(
            next_scheduled_maintenance__gte=timezone.now().date()
        ).order_by('next_scheduled_maintenance')[:5]
        
        context['maintenance_stats'] = maintenance_stats
        context['title'] = 'Maintenance Logs'
        return context


class MaintenanceLogCreateView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, CreateView):
    """Create a new maintenance log."""
    
    model = MaintenanceLog
    form_class = MaintenanceLogForm
    template_name = 'generators/maintenance_log_form.html'
    success_url = reverse_lazy('generators:maintenance_log_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        store_id = self.request.GET.get('store', None)
        if store_id:
            kwargs['store_id'] = store_id
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Maintenance Log'
        context['action'] = 'Create'
        context['stores'] = Store.objects.all()
        
        # Add JavaScript for dynamic generator filtering by store
        context['js_functions'] = """
        <script>
        function updateGenerators() {
            const storeId = document.getElementById('id_store').value;
            const generatorSelect = document.getElementById('id_generator');
            
            // Clear current options
            generatorSelect.innerHTML = '';
            
            if (!storeId) {
                generatorSelect.innerHTML = '<option value="">---------</option>';
                return;
            }
            
            // Fetch generators for the selected store
            fetch(`/generators/api/generators-by-store/${storeId}/`)
                .then(response => response.json())
                .then(data => {
                    generatorSelect.innerHTML = '<option value="">---------</option>';
                    data.forEach(generator => {
                        const option = document.createElement('option');
                        option.value = generator.id;
                        option.textContent = generator.make_and_model;
                        generatorSelect.appendChild(option);
                    });
                });
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            const storeSelect = document.getElementById('id_store');
            if (storeSelect) {
                storeSelect.addEventListener('change', updateGenerators);
            }
        });
        </script>
        """
        
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f"Maintenance log for {form.instance.generator} on {form.instance.date_of_service} created successfully."
        )
        return super().form_valid(form)


class MaintenanceLogUpdateView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, UpdateView):
    """Update an existing maintenance log."""
    
    model = MaintenanceLog
    form_class = MaintenanceLogForm
    template_name = 'generators/maintenance_log_form.html'
    success_url = reverse_lazy('generators:maintenance_log_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.object and self.object.generator and self.object.generator.store:
            kwargs['store_id'] = self.object.generator.store.id
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Maintenance Log: {self.object.generator} on {self.object.date_of_service}'
        context['action'] = 'Update'
        context['stores'] = Store.objects.all()
        return context
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f"Maintenance log for {form.instance.generator} on {form.instance.date_of_service} updated successfully."
        )
        return super().form_valid(form)


class MaintenanceLogDeleteView(LoginRequiredMixin, StaffRequiredMixin, GeneratorBaseView, DeleteView):
    """Delete a maintenance log."""
    
    model = MaintenanceLog
    template_name = 'generators/maintenance_log_confirm_delete.html'
    success_url = reverse_lazy('generators:maintenance_log_list')
    context_object_name = 'maintenance_log'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Maintenance Log: {self.object.generator} on {self.object.date_of_service}'
        return context
    
    def delete(self, request, *args, **kwargs):
        maintenance_log = self.get_object()
        generator_name = maintenance_log.generator.make_and_model
        service_date = maintenance_log.date_of_service
        
        messages.success(
            request, 
            f"Maintenance log for {generator_name} on {service_date} deleted successfully."
        )
        return super().delete(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
#  API Views for AJAX
# --------------------------------------------------------------------------- #

@login_required
def generators_by_store(request, store_id):
    """API endpoint to get generators filtered by store."""
    generators = Generator.objects.filter(store_id=store_id).values('id', 'make_and_model')
    return JsonResponse(list(generators), safe=False)


@login_required
def generator_details(request, generator_id):
    """API endpoint to get generator details."""
    try:
        generator = Generator.objects.get(id=generator_id)
        data = {
            'id': generator.id,
            'make_and_model': generator.make_and_model,
            'capacity_kva': generator.capacity_kva,
            'fuel_type': generator.fuel_type,
            'store_id': generator.store_id,
            'store_name': generator.store.name,
        }
        return JsonResponse(data)
    except Generator.DoesNotExist:
        return JsonResponse({'error': 'Generator not found'}, status=404)
