from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import HttpResponseRedirect

from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin
from .consultant_models import ConsultantRate
from .models import Trip
from accounts.models import CustomUser
from vehicles.models import Vehicle

class ConsultantRateListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """
    Display a list of all consultant rates.
    """
    model = ConsultantRate
    template_name = 'trips/consultant_rate_list.html'
    context_object_name = 'consultant_rates'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter and order consultant rates."""
        queryset = super().get_queryset()
        
        # Apply search filter if provided
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(driver__first_name__icontains=search_query) |
                Q(driver__last_name__icontains=search_query) |
                Q(vehicle__license_plate__icontains=search_query) |
                Q(vehicle__make__icontains=search_query) |
                Q(vehicle__model__icontains=search_query)
            )
        
        # Apply status filter if provided
        status_filter = self.request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # Default ordering by updated_at (most recent first)
        return queryset.select_related('driver', 'vehicle')
    
    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        
        # Add search query to context for form persistence
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        
        # Add summary statistics
        context['total_rates'] = ConsultantRate.objects.count()
        context['active_rates'] = ConsultantRate.objects.filter(status='active').count()
        context['inactive_rates'] = ConsultantRate.objects.filter(status='inactive').count()
        
        return context

class ConsultantRateCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """
    Create a new consultant rate.
    """
    model = ConsultantRate
    template_name = 'trips/consultant_rate_form.html'
    fields = ['driver', 'vehicle', 'rate_per_km', 'status', 'notes']
    success_url = reverse_lazy('consultant_rate_list')
    
    def get_form(self, form_class=None):
        """Customize form field querysets."""
        form = super().get_form(form_class)
        
        # Filter drivers to only show those with driver user_type
        form.fields['driver'].queryset = CustomUser.objects.filter(user_type='driver')
        
        # Filter vehicles to only show available ones
        form.fields['vehicle'].queryset = Vehicle.objects.filter(status__in=['available', 'in_use'])
        
        return form
    
    def form_valid(self, form):
        """Process valid form data."""
        # Check if there's already an active rate for this driver-vehicle pair
        driver = form.cleaned_data['driver']
        vehicle = form.cleaned_data['vehicle']
        status = form.cleaned_data['status']
        
        if status == 'active' and ConsultantRate.objects.filter(
            driver=driver, 
            vehicle=vehicle, 
            status='active'
        ).exists():
            # If exists, deactivate the existing rate
            existing_rate = ConsultantRate.objects.get(
                driver=driver, 
                vehicle=vehicle, 
                status='active'
            )
            existing_rate.status = 'inactive'
            existing_rate.save()
            messages.warning(
                self.request, 
                f'Previous active rate for {driver.get_full_name()} and {vehicle} has been deactivated.'
            )
        
        messages.success(
            self.request, 
            f'Consultant rate for {driver.get_full_name()} and {vehicle} has been created.'
        )
        return super().form_valid(form)

class ConsultantRateUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """
    Update an existing consultant rate.
    """
    model = ConsultantRate
    template_name = 'trips/consultant_rate_form.html'
    fields = ['rate_per_km', 'status', 'notes']
    success_url = reverse_lazy('consultant_rate_list')
    
    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        return context
    
    def form_valid(self, form):
        """Process valid form data."""
        consultant_rate = self.get_object()
        status = form.cleaned_data['status']
        
        # If changing to active, deactivate any other active rates for this pair
        if status == 'active' and consultant_rate.status != 'active':
            ConsultantRate.objects.filter(
                driver=consultant_rate.driver, 
                vehicle=consultant_rate.vehicle, 
                status='active'
            ).exclude(pk=consultant_rate.pk).update(status='inactive')
            
            messages.warning(
                self.request, 
                f'Other active rates for {consultant_rate.driver.get_full_name()} and {consultant_rate.vehicle} have been deactivated.'
            )
        
        messages.success(
            self.request, 
            f'Consultant rate for {consultant_rate.driver.get_full_name()} and {consultant_rate.vehicle} has been updated.'
        )
        return super().form_valid(form)

class ConsultantRateDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """
    Delete a consultant rate.
    """
    model = ConsultantRate
    template_name = 'trips/consultant_rate_confirm_delete.html'
    success_url = reverse_lazy('consultant_rate_list')
    
    def delete(self, request, *args, **kwargs):
        """Process deletion request."""
        consultant_rate = self.get_object()
        messages.success(
            request, 
            f'Consultant rate for {consultant_rate.driver.get_full_name()} and {consultant_rate.vehicle} has been deleted.'
        )
        return super().delete(request, *args, **kwargs)

class ConsultantRateDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """
    View details of a consultant rate including trip history.
    """
    model = ConsultantRate
    template_name = 'trips/consultant_rate_detail.html'
    context_object_name = 'consultant_rate'
    
    def get_context_data(self, **kwargs):
        """Add additional context data including trip history."""
        context = super().get_context_data(**kwargs)
        consultant_rate = self.get_object()
        
        # Get completed trips for this driver-vehicle pair
        trips = Trip.objects.filter(
            driver=consultant_rate.driver,
            vehicle=consultant_rate.vehicle,
            status='completed'
        ).order_by('-end_time')
        
        # Calculate total distance and payment
        total_distance = sum(trip.distance_traveled() for trip in trips)
        total_payment = sum(trip.consultant_payment() for trip in trips)
        
        context.update({
            'trips': trips,
            'total_distance': total_distance,
            'total_payment': total_payment,
            'trip_count': trips.count()
        })
        
        return context

class ConsultantRateToggleView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """
    Toggle the status of a consultant rate between active and inactive.
    """
    model = ConsultantRate
    
    def get(self, request, *args, **kwargs):
        """Handle GET request to toggle status."""
        consultant_rate = self.get_object()
        
        if consultant_rate.status == 'active':
            consultant_rate.status = 'inactive'
            status_message = 'deactivated'
        else:
            # Deactivate any other active rates for this driver-vehicle pair
            ConsultantRate.objects.filter(
                driver=consultant_rate.driver,
                vehicle=consultant_rate.vehicle,
                status='active'
            ).update(status='inactive')
            
            consultant_rate.status = 'active'
            status_message = 'activated'
        
        consultant_rate.save()
        
        messages.success(
            request,
            f'Consultant rate for {consultant_rate.driver.get_full_name()} and {consultant_rate.vehicle} has been {status_message}.'
        )
        
        return redirect('consultant_rate_list')
