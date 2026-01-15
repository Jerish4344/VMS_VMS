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
from django.http import HttpResponseRedirect

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


class MyVehicleDetailView(LoginRequiredMixin, PersonalVehicleStaffTestMixin, ListView):
    """View for staff to see all their personal vehicles."""
    model = Vehicle
    template_name = 'vehicles/my_vehicle_detail.html'
    context_object_name = 'vehicles'
    
    def get_queryset(self):
        """Get all vehicles owned by the current user."""
        return Vehicle.objects.filter(
            ownership_type='personal',
            owned_by=self.request.user
        ).order_by('license_plate')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicles = self.get_queryset()
        
        # Add statistics for each vehicle
        vehicles_with_stats = []
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        for vehicle in vehicles:
            # Get trip statistics for this vehicle
            trips = Trip.objects.filter(
                vehicle=vehicle,
                driver=self.request.user,
                status='completed',
                is_deleted=False
            )
            
            # Current month statistics
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
            
            # Recent trips for this vehicle
            recent_trips = trips.order_by('-start_time')[:3]
            for trip in recent_trips:
                if trip.end_odometer is not None and trip.start_odometer is not None:
                    trip.distance = trip.end_odometer - trip.start_odometer
                else:
                    trip.distance = None
            
            # Add stats to vehicle object
            vehicle.current_month_trips_count = current_month_trips.count()
            vehicle.current_month_distance = total_distance
            vehicle.current_month_reimbursement = reimbursement_amount
            vehicle.total_trips = trips.count()
            vehicle.pending_trips = Trip.objects.filter(
                vehicle=vehicle,
                driver=self.request.user,
                status='ongoing'
            ).count()
            vehicle.recent_trips = recent_trips
            
            vehicles_with_stats.append(vehicle)
        
        context['vehicles_with_stats'] = vehicles_with_stats
        context['total_vehicles'] = vehicles.count()
        
        return context


class MyVehicleUpdateView(LoginRequiredMixin, PersonalVehicleStaffTestMixin, UpdateView):
    """Allow staff to update limited fields of their vehicle."""
    model = Vehicle
    template_name = 'vehicles/my_vehicle_update.html'
    fields = ['current_odometer', 'notes', 'image']
    success_url = reverse_lazy('my_vehicle')
    
    def get_object(self):
        """Get the specific vehicle owned by the current user."""
        vehicle_id = self.kwargs.get('pk')
        if vehicle_id:
            return get_object_or_404(
                Vehicle, 
                pk=vehicle_id,
                ownership_type='personal',
                owned_by=self.request.user
            )
        else:
            # If no ID provided, try to get the first vehicle
            vehicles = Vehicle.objects.filter(
                ownership_type='personal',
                owned_by=self.request.user
            )
            if vehicles.count() == 1:
                return vehicles.first()
            else:
                # Multiple vehicles, need to specify which one
                messages.error(self.request, "Please select a specific vehicle to update.")
                return HttpResponseRedirect(reverse_lazy('my_vehicle'))
    
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
        
        # Get the user's personal vehicles
        vehicles = Vehicle.objects.filter(
            ownership_type='personal',
            owned_by=self.request.user
        )
        
        if vehicles.exists():
            context['vehicles'] = vehicles
            context['has_vehicles'] = True
            
            # Calculate monthly reimbursements across all vehicles
            trips = self.get_queryset()
            
            # Add distance and reimbursement to each trip
            trips_list = list(trips)
            for trip in trips_list:
                if trip.end_odometer is not None and trip.start_odometer is not None:
                    trip.distance = trip.end_odometer - trip.start_odometer
                    if trip.vehicle.reimbursement_rate_per_km:
                        trip.reimbursement = trip.distance * trip.vehicle.reimbursement_rate_per_km
                    else:
                        trip.reimbursement = 0
                else:
                    trip.distance = None
                    trip.reimbursement = None
            
            # Override the trips in context with calculated trips
            context['trips'] = trips_list
            
            # Group by month across all vehicles
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
                total_reimbursement = 0
                for trip in month_trips:
                    if trip.end_odometer is not None and trip.start_odometer is not None:
                        distance = trip.end_odometer - trip.start_odometer
                        total_distance += distance
                        
                        if trip.vehicle.reimbursement_rate_per_km:
                            total_reimbursement += distance * trip.vehicle.reimbursement_rate_per_km
                
                monthly_data.append({
                    'month': month_start.strftime('%B %Y'),
                    'trips_count': month_trips.count(),
                    'distance': total_distance,
                    'reimbursement': total_reimbursement
                })
            
            context['monthly_data'] = monthly_data
            
        else:
            context['vehicles'] = []
            context['has_vehicles'] = False
            context['monthly_data'] = []
            messages.warning(self.request, "You don't have any personal vehicles registered yet.")
        
        return context
