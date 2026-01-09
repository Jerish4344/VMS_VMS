"""
Views for personal vehicle staff to manage their own vehicles and view reimbursement info.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import timedelta

from .models import Vehicle
from trips.models import Trip
from accounts.mixins import PersonalVehicleStaffRequiredMixin


class PersonalVehicleStaffTestMixin(UserPassesTestMixin):
    """Mixin to ensure only personal vehicle staff can access these views."""
    
    def test_func(self):
        return (
            self.request.user.is_authenticated and 
            self.request.user.user_type == 'personal_vehicle_staff'
        )
    
    def handle_no_permission(self):
        messages.error(self.request, "Access denied. This section is only for personal vehicle staff.")
        return redirect('dashboard')


class MyVehicleDetailView(LoginRequiredMixin, PersonalVehicleStaffTestMixin, DetailView):
    """View for staff to see their personal vehicle details."""
    model = Vehicle
    template_name = 'vehicles/my_vehicle_detail.html'
    context_object_name = 'vehicle'
    
    def get_object(self):
        """Get the vehicle owned by the current user."""
        return get_object_or_404(
            Vehicle, 
            ownership_type='personal',
            owned_by=self.request.user
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()
        
        # Get trip statistics
        trips = Trip.objects.filter(
            vehicle=vehicle,
            driver=self.request.user,
            status='completed',
            is_deleted=False
        )
        
        # Current month statistics
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_trips = trips.filter(start_time__gte=current_month_start)
        
        # Calculate total distance for current month
        total_distance = 0
        for trip in current_month_trips:
            if trip.end_odometer is not None and trip.start_odometer is not None:
                total_distance += (trip.end_odometer - trip.start_odometer)
        
        # Calculate reimbursement
        reimbursement_amount = 0
        if vehicle.reimbursement_rate_per_km:
            reimbursement_amount = total_distance * vehicle.reimbursement_rate_per_km
        
        context['current_month_trips_count'] = current_month_trips.count()
        context['current_month_distance'] = total_distance
        context['current_month_reimbursement'] = reimbursement_amount
        
        # All-time statistics
        context['total_trips'] = trips.count()
        context['pending_trips'] = Trip.objects.filter(
            vehicle=vehicle,
            driver=self.request.user,
            status='ongoing'
        ).count()
        
        # Recent trips with distance calculation
        recent_trips = trips.order_by('-start_time')[:5]
        for trip in recent_trips:
            if trip.end_odometer is not None and trip.start_odometer is not None:
                trip.distance = trip.end_odometer - trip.start_odometer
            else:
                trip.distance = None
        
        context['recent_trips'] = recent_trips
        
        return context


class MyVehicleUpdateView(LoginRequiredMixin, PersonalVehicleStaffTestMixin, UpdateView):
    """Allow staff to update limited fields of their vehicle."""
    model = Vehicle
    template_name = 'vehicles/my_vehicle_update.html'
    fields = ['current_odometer', 'notes', 'image']
    success_url = reverse_lazy('my_vehicle')
    
    def get_object(self):
        """Get the vehicle owned by the current user."""
        return get_object_or_404(
            Vehicle, 
            ownership_type='personal',
            owned_by=self.request.user
        )
    
    def form_valid(self, form):
        messages.success(self.request, "Your vehicle information has been updated successfully!")
        return super().form_valid(form)


class MyReimbursementView(LoginRequiredMixin, PersonalVehicleStaffTestMixin, ListView):
    """View for staff to see their reimbursement history and claims."""
    model = Trip
    template_name = 'vehicles/my_reimbursement.html'
    context_object_name = 'trips'
    paginate_by = 20
    
    def get_queryset(self):
        """Get completed trips for the user's personal vehicle."""
        return Trip.objects.filter(
            driver=self.request.user,
            vehicle__ownership_type='personal',
            vehicle__owned_by=self.request.user,
            status='completed',
            is_deleted=False
        ).select_related('vehicle').order_by('-start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the user's personal vehicle
        try:
            vehicle = Vehicle.objects.get(
                ownership_type='personal',
                owned_by=self.request.user
            )
            context['vehicle'] = vehicle
            
            # Calculate monthly reimbursements
            trips = self.get_queryset()
            
            # Add distance and reimbursement to each trip
            trips_list = list(trips)
            for trip in trips_list:
                if trip.end_odometer is not None and trip.start_odometer is not None:
                    trip.distance = trip.end_odometer - trip.start_odometer
                    if vehicle.reimbursement_rate_per_km:
                        trip.reimbursement = trip.distance * vehicle.reimbursement_rate_per_km
                    else:
                        trip.reimbursement = 0
                else:
                    trip.distance = None
                    trip.reimbursement = None
            
            # Override the trips in context with calculated trips
            context['trips'] = trips_list
            
            # Group by month
            monthly_data = []
            current_date = timezone.now()
            
            for i in range(6):  # Last 6 months
                month_start = (current_date - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if i == 0:
                    month_end = current_date
                else:
                    month_end = month_start.replace(day=28) + timedelta(days=4)  # End of month
                
                month_trips = trips.filter(
                    start_time__gte=month_start,
                    start_time__lt=month_end
                )
                
                total_distance = 0
                for trip in month_trips:
                    if trip.end_odometer is not None and trip.start_odometer is not None:
                        total_distance += (trip.end_odometer - trip.start_odometer)
                
                reimbursement = 0
                if vehicle.reimbursement_rate_per_km:
                    reimbursement = total_distance * vehicle.reimbursement_rate_per_km
                
                monthly_data.append({
                    'month': month_start.strftime('%B %Y'),
                    'trips_count': month_trips.count(),
                    'distance': total_distance,
                    'reimbursement': reimbursement
                })
            
            context['monthly_data'] = monthly_data
            
        except Vehicle.DoesNotExist:
            context['vehicle'] = None
            context['monthly_data'] = []
            messages.warning(self.request, "You don't have a personal vehicle registered yet.")
        
        return context
