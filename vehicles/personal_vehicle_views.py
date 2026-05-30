"""
Views for personal vehicle staff to manage their own vehicles and view reimbursement info.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import (
    Sum, Q, Count, F, Value, ExpressionWrapper,
    DecimalField, IntegerField,
)
from django.db.models.functions import TruncMonth, Coalesce
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

    # Reusable SQL expressions so distance / reimbursement are computed in the
    # database instead of Python. This keeps memory flat regardless of the
    # number of trips and lets pagination actually work.
    _DISTANCE_EXPR = ExpressionWrapper(
        F('end_odometer') - F('start_odometer'),
        output_field=IntegerField(),
    )
    _REIMBURSEMENT_EXPR = ExpressionWrapper(
        (F('end_odometer') - F('start_odometer')) *
        Coalesce(
            F('vehicle__reimbursement_rate_per_km'),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )

    def get_queryset(self):
        """Completed trips for the user's personal vehicles, with distance
        and reimbursement annotated in the database."""
        return (
            Trip.objects.filter(
                driver=self.request.user,
                vehicle__ownership_type='personal',
                vehicle__owned_by=self.request.user,
                status='completed',
                is_deleted=False,
            )
            .select_related('vehicle')
            .annotate(
                distance=self._DISTANCE_EXPR,
                reimbursement=self._REIMBURSEMENT_EXPR,
            )
            .order_by('-start_time')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the user's personal vehicles
        vehicles = Vehicle.objects.filter(
            ownership_type='personal',
            owned_by=self.request.user,
        )

        if not vehicles.exists():
            context['vehicles'] = []
            context['has_vehicles'] = False
            context['monthly_data'] = []
            messages.warning(
                self.request,
                "You don't have any personal vehicles registered yet.",
            )
            return context

        context['vehicles'] = vehicles
        context['has_vehicles'] = True

        # Build the 6-month window. Use the first day of the month 5 months
        # before the current month so we cover exactly 6 calendar months.
        now = timezone.now()
        current_month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        # Step back 5 months by repeatedly subtracting one day from the
        # previous month start. Avoids the dateutil dependency.
        window_start = current_month_start
        for _ in range(5):
            window_start = (window_start - timedelta(days=1)).replace(day=1)

        # Single grouped query for all 6 months instead of 6 separate queries.
        monthly_qs = (
            Trip.objects.filter(
                driver=self.request.user,
                vehicle__ownership_type='personal',
                vehicle__owned_by=self.request.user,
                status='completed',
                is_deleted=False,
                start_odometer__isnull=False,
                end_odometer__isnull=False,
                approval_status__in=['not_required', 'approved'],
                start_time__gte=window_start,
            )
            .annotate(month=TruncMonth('start_time'))
            .values('month')
            .annotate(
                trips_count=Count('id'),
                distance=Sum(self._DISTANCE_EXPR),
                reimbursement=Sum(self._REIMBURSEMENT_EXPR),
            )
            .order_by('-month')
        )

        # Index aggregated rows by month so we can fill in months with no trips.
        by_month = {row['month'].date().replace(day=1): row for row in monthly_qs}

        monthly_data = []
        cursor = current_month_start
        for _ in range(6):
            key = cursor.date().replace(day=1)
            row = by_month.get(key)
            monthly_data.append({
                'month': cursor.strftime('%B %Y'),
                'trips_count': row['trips_count'] if row else 0,
                'distance': row['distance'] if row else 0,
                'reimbursement': row['reimbursement'] if row else 0,
            })
            # Move cursor to first day of previous month.
            cursor = (cursor - timedelta(days=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0,
            )

        context['monthly_data'] = monthly_data
        return context
