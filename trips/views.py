from django.forms import ValidationError
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from accounts.models import CustomUser
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin, DriverRequiredMixin
from .models import Trip
from .gps_models import GPSTrackingSession
from vehicles.models import Vehicle
# For filter dropdown
from vehicles.models import VehicleType
from .forms import TripForm, EndTripForm, ManualTripForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.db import transaction
from datetime import datetime, timedelta
import csv
import json
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from django.conf import settings
from trips.tasks import send_trip_alert_email_async

# Conditional import of xlsxwriter
try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

import logging

logger = logging.getLogger(__name__)

class CanDriveVehicleMixin:
    """
    Mixin to check if user can drive vehicles.
    Allows: drivers, admins, managers, vehicle_managers, personal_vehicle_staff, and company_vehicle_staff
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Allow these user types to drive vehicles
        allowed_user_types = ['driver', 'admin', 'manager', 'vehicle_manager', 'personal_vehicle_staff', 'company_vehicle_staff']
        
        if request.user.user_type not in allowed_user_types:
            messages.error(request, 'You do not have permission to access this feature.')
            raise PermissionDenied("User does not have vehicle driving permissions")
        
        return super().dispatch(request, *args, **kwargs)

class TripListView(LoginRequiredMixin, ListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'
    paginate_by = 20
    
    def get_queryset(self):
        # Get base queryset based on user permissions
        if self.request.user.user_type == 'driver':
            queryset = Trip.objects.filter(driver=self.request.user, is_deleted=False)
        elif self.request.user.user_type == 'personal_vehicle_staff':
            # Personal vehicle staff only see trips with their personal vehicles
            queryset = Trip.objects.filter(
                driver=self.request.user,
                vehicle__ownership_type='personal',
                vehicle__owned_by=self.request.user,
                is_deleted=False
            )
        elif self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']:
            queryset = Trip.objects.filter(is_deleted=False)
        else:
            queryset = Trip.objects.none()
        
        # Apply search filter
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search_query) |
                Q(vehicle__make__icontains=search_query) |
                Q(vehicle__model__icontains=search_query) |
                Q(driver__first_name__icontains=search_query) |
                Q(driver__last_name__icontains=search_query) |
                Q(origin__icontains=search_query) |
                Q(destination__icontains=search_query) |
                Q(purpose__icontains=search_query)
            )
            
        # Apply vehicle filter
        vehicle_id = self.request.GET.get('vehicle', '')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        # Apply vehicle type filter
        vehicle_type_id = self.request.GET.get('vehicle_type')
        if vehicle_type_id and vehicle_type_id.isdigit():
            queryset = queryset.filter(vehicle__vehicle_type_id=int(vehicle_type_id))
            
        # Apply status filter
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        # FIXED: Simple and reliable date filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from and date_to:
            try:
                # Parse the dates
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                # Create timezone-aware datetime objects for the full day range
                from django.utils import timezone
                
                # Start of the from_date (00:00:00)
                date_from_start = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
                # End of the to_date (23:59:59.999999)
                date_to_end = timezone.make_aware(
                    datetime.combine(date_to_obj, datetime.max.time())
                )
                
                # Filter trips that started within this range
                queryset = queryset.filter(
                    start_time__gte=date_from_start,
                    start_time__lte=date_to_end
                )
                
            except ValueError:
                logger.warning(f"Invalid date format: date_from={date_from}, date_to={date_to}")
                
        elif date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_from_start = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
                
                # Get trips that started on or after this date
                queryset = queryset.filter(start_time__gte=date_from_start)
                
            except ValueError:
                logger.warning(f"Invalid date_from: {date_from}")
                
        elif date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                date_to_end = timezone.make_aware(
                    datetime.combine(date_to_obj, datetime.max.time())
                )
                
                # Get trips that started on or before this date
                queryset = queryset.filter(start_time__lte=date_to_end)
                
            except ValueError:
                logger.warning(f"Invalid date_to: {date_to}")
            
        return queryset.select_related('vehicle', 'driver').order_by('-start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the paginated trips (current page only)
        paginated_trips = context['trips']  # This is the paginated queryset
        
        # Separate trips by status from the current page only
        ongoing_trips = []
        completed_trips = []
        cancelled_trips = []
        
        for trip in paginated_trips:
            if trip.status == 'ongoing':
                ongoing_trips.append(trip)
            elif trip.status == 'completed':
                completed_trips.append(trip)
            elif trip.status == 'cancelled':
                cancelled_trips.append(trip)
        
        # Add separated trips to context
        context['ongoing_trips'] = ongoing_trips
        context['completed_trips'] = completed_trips
        context['cancelled_trips'] = cancelled_trips
        
        # Add counts for current page
        context['ongoing_count'] = len(ongoing_trips)
        context['completed_count'] = len(completed_trips)
        context['cancelled_count'] = len(cancelled_trips)
        
        # If you need total counts across all pages (for stats cards), 
        # get them separately with a more efficient query
        full_queryset = self.get_queryset()
        context['total_ongoing_count'] = full_queryset.filter(status='ongoing').count()
        context['total_completed_count'] = full_queryset.filter(status='completed').count()
        context['total_cancelled_count'] = full_queryset.filter(status='cancelled').count()
        
        # Add vehicles for filter - exclude personal vehicles for drivers
        if self.request.user.user_type == 'driver':
            context['vehicles'] = Vehicle.objects.filter(
                ownership_type='company'
            ).filter(
                Q(assigned_driver=self.request.user) | 
                Q(trips__driver=self.request.user)
            ).distinct()
        else:
            context['vehicles'] = Vehicle.objects.filter(ownership_type='company')
        # Vehicle types for UI filter
        context['vehicle_types'] = VehicleType.objects.all().order_by('name')
        
        # Add search parameters for maintaining filters in pagination
        search_params = {}
        if self.request.GET.get('search'):
            search_params['search'] = self.request.GET.get('search')
        if self.request.GET.get('vehicle'):
            search_params['vehicle'] = self.request.GET.get('vehicle')
        if self.request.GET.get('vehicle_type'):
            search_params['vehicle_type'] = self.request.GET.get('vehicle_type')
        if self.request.GET.get('status'):
            search_params['status'] = self.request.GET.get('status')
        if self.request.GET.get('date_from'):
            search_params['date_from'] = self.request.GET.get('date_from')
        if self.request.GET.get('date_to'):
            search_params['date_to'] = self.request.GET.get('date_to')
        
        context['search_params'] = search_params
        
        # Add user permissions context
        context['can_start_trip'] = self.request.user.user_type in ['driver', 'admin', 'manager', 'vehicle_manager', 'personal_vehicle_staff', 'company_vehicle_staff']

        # Check if GPS tracking should be auto-started for a newly created trip
        if 'start_gps_tracking' in self.request.session:
            context['start_gps_tracking'] = self.request.session.pop('start_gps_tracking')
        
        return context

class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = 'trips/trip_detail.html'
    context_object_name = 'trip'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip = self.get_object()
        
        # Add locations if you have a location tracking model
        if hasattr(trip, 'locations'):
            context['locations'] = trip.locations.all().order_by('timestamp')
        
        # Add route information for display
        context['route_summary'] = trip.get_route_summary()
        
        # Check if user can end this trip
        context['can_end_trip'] = trip.can_be_ended_by(self.request.user)
        
        return context
    
# ---------------------------------------------------------------------------
#  DriverTripsView – list trips for a specific driver (from Driver Report link)
# ---------------------------------------------------------------------------

class DriverTripsView(LoginRequiredMixin, ListView):
    """
    Show all trips for a specific driver.  This view is reached by clicking a
    driver name in the Driver Performance Report.
    """
    model = Trip
    template_name = 'trips/driver_trips.html'
    context_object_name = 'trips'
    paginate_by = 20

    # ---- helpers ----------------------------------------------------------
    def _get_driver(self):
        """Return the driver object referenced by the URL, or current user for personal vehicle staff."""
        driver_id = self.kwargs.get('driver_id')
        
        # If no driver_id in URL, return current user (for personal vehicle staff accessing their own trips)
        if not driver_id:
            return self.request.user
            
        # For management users viewing other drivers
        return get_object_or_404(CustomUser, id=driver_id, user_type__in=['driver', 'personal_vehicle_staff'])

    # ---- queryset ---------------------------------------------------------
    def get_queryset(self):
        """
        Base queryset -> all trips for the driver, optionally filtered
        by status / date range, ordered by most-recent first.
        """
        driver = self._get_driver()
        
        # For personal vehicle staff, only show trips with their personal vehicles
        if driver.user_type == 'personal_vehicle_staff':
            qs = Trip.objects.filter(
                driver=driver,
                vehicle__ownership_type='personal',
                vehicle__owned_by=driver,
                is_deleted=False
            ).select_related('vehicle', 'driver')
        else:
            qs = Trip.objects.filter(driver=driver, is_deleted=False).select_related('vehicle', 'driver')

        # Status filter
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)

        # ----------------------------------------------------
        # Robust Date-Range Filtering
        #   HTML <input type="date"> sends value as YYYY-MM-DD.
        #   Build a single filter_kwargs dict so an incomplete
        #   range (only from / only to) is also respected.
        # ----------------------------------------------------
        date_from_raw = self.request.GET.get('date_from', '').strip()
        date_to_raw   = self.request.GET.get('date_to', '').strip()

        filter_kwargs = {}

        if date_from_raw:
            try:
                date_from_obj = datetime.strptime(date_from_raw, '%Y-%m-%d').date()
                filter_kwargs['start_time__gte'] = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
            except ValueError:
                logger.warning("DriverTripsView: invalid date_from %s", date_from_raw)

        if date_to_raw:
            try:
                date_to_obj = datetime.strptime(date_to_raw, '%Y-%m-%d').date()
                filter_kwargs['start_time__lte'] = timezone.make_aware(
                    datetime.combine(date_to_obj, datetime.max.time())
                )
            except ValueError:
                logger.warning("DriverTripsView: invalid date_to %s", date_to_raw)

        if filter_kwargs:
            qs = qs.filter(**filter_kwargs)

        # Debug: log final count after filtering
        logger.debug(
            "DriverTripsView: driver=%s filters=%s resulting_count=%d",
            driver.id, filter_kwargs, qs.count()
        )

        # Order newest first
        return qs.order_by('-start_time')

    # ---- context ----------------------------------------------------------
    def get_context_data(self, **kwargs):
        """
        Add driver object and current filters to template context for use in
        breadcrumb navigation and retaining filters across pagination.
        """
        context = super().get_context_data(**kwargs)

        driver = self._get_driver()
        context['driver'] = driver

        # ------------------------------------------------------------------
        # Preserve *all* filter values (including blanks) so templates can
        # safely reference `filter_params.<key>` without extra existence
        # checks.  This helps pagination / form-persistence and makes the
        # behaviour explicit.
        # ------------------------------------------------------------------
        filter_params = {
            'status':    self.request.GET.get('status', '').strip(),
            'date_from': self.request.GET.get('date_from', '').strip(),
            'date_to':   self.request.GET.get('date_to', '').strip(),
        }

        # Debug log for easier troubleshooting in development
        logger.debug(
            "DriverTripsView context filter_params for driver=%s -> %s",
            driver.id,
            filter_params,
        )

        context['filter_params'] = filter_params

        return context

class TripTrackingView(LoginRequiredMixin, CanDriveVehicleMixin, TemplateView):
    """
    View for users to track their active trip with geolocation.
    - Drivers: See tracking controls to record their own location
    - Admins/Managers: See real-time view of driver's recorded GPS data
    """
    template_name = 'trips/trip_tracking.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip_id = self.kwargs.get('pk')
        trip = get_object_or_404(Trip, pk=trip_id)
        
        # Check permissions - trip driver or management users can track
        if (trip.driver != self.request.user and 
            self.request.user.user_type not in ['admin', 'manager', 'vehicle_manager']):
            messages.error(self.request, "You can only track trips assigned to you.")
            return redirect('trip_list')
        
        # Trip should be active
        if trip.status != 'ongoing':
            messages.error(self.request, "This trip is not currently active.")
            return redirect('trip_list')
        
        context['trip'] = trip
        
        # Determine if user is the driver or a viewer (admin/manager watching)
        context['is_driver'] = (trip.driver == self.request.user)
        context['is_viewer'] = (trip.driver != self.request.user)
        
        # Get fleet manager for emergency contact
        fleet_managers = CustomUser.objects.filter(user_type__in=['manager', 'vehicle_manager'])
        context['fleet_manager'] = fleet_managers.first() if fleet_managers.exists() else None
        
        # Get nearby fuel stations (could be enhanced with geolocation API)
        context['fuel_stations'] = True  # Placeholder for actual fuel station data
        
        return context

class StartTripView(LoginRequiredMixin, CanDriveVehicleMixin, CreateView):
    """
    View for starting a new trip.
    Accessible by: drivers, admins, managers, and vehicle_managers
    """
    model = Trip
    form_class = TripForm
    template_name = 'trips/start_trip.html'
    success_url = reverse_lazy('trip_list')
    
    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add available vehicles to the context based on user type
        if self.request.user.user_type == 'personal_vehicle_staff':
            # Personal vehicle staff only see their own vehicles
            available_vehicles = Vehicle.objects.filter(
                ownership_type='personal',
                owned_by=self.request.user,
                status='available'
            ).select_related('vehicle_type')
        else:
            # Check if driver has active consultant rate assignments
            from trips.consultant_models import ConsultantRate
            consultant_vehicle_ids = list(ConsultantRate.objects.filter(
                driver=self.request.user, status='active'
            ).values_list('vehicle_id', flat=True))
            if consultant_vehicle_ids:
                # Consultant drivers see their assigned vehicles (exclude only retired)
                available_vehicles = Vehicle.objects.filter(
                    id__in=consultant_vehicle_ids
                ).exclude(status='retired').select_related('vehicle_type')
            else:
                # Other users see company vehicles
                available_vehicles = Vehicle.objects.filter(
                    ownership_type='company',
                    status='available'
                ).select_related('vehicle_type')
        
        context['available_vehicles'] = available_vehicles
        
        # Add vehicle types for filter buttons
        try:
            from vehicles.models import VehicleType
            context['vehicle_types'] = VehicleType.objects.all()
        except ImportError:
            # If VehicleType model doesn't exist, set empty queryset
            context['vehicle_types'] = []
        
        # Add user role information for template display
        context['user_role'] = self.request.user.get_user_type_display()
        context['is_management'] = self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']
        
        # Check if user has active trips
        active_trips = Trip.objects.filter(
            driver=self.request.user, 
            status='ongoing'
        )
        context['active_trips'] = active_trips
        context['has_active_trip'] = active_trips.exists()
        
        # Add drivers for management users (for manual assignment)
        if self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']:
            context['drivers'] = CustomUser.objects.filter(user_type='driver').order_by('first_name', 'last_name')
        
        return context
    
    def form_valid(self, form):
        # Check if user already has an active trip (optional restriction for drivers)
        current_driver = self.request.user
        
        # If management user is starting trip for another driver, get that driver
        selected_driver_id = self.request.POST.get('driver')
        if (self.request.user.user_type in ['admin', 'manager', 'vehicle_manager'] and 
            selected_driver_id):
            try:
                current_driver = CustomUser.objects.get(id=selected_driver_id, user_type='driver')
            except (CustomUser.DoesNotExist, ValueError):
                current_driver = self.request.user
        
        # Check for active trips for the actual driver
        active_trips = Trip.objects.filter(
            driver=current_driver, 
            status='ongoing'
        )
        
        if active_trips.exists():
            messages.warning(
                self.request,
                f'{current_driver.get_full_name()} already has an active trip. Please end the current trip before starting a new one.'
            )
            return self.form_invalid(form)
        
        # Set the driver
        form.instance.driver = current_driver
        form.instance.status = 'ongoing'
        
        # Set the start time to the current time automatically
        form.instance.start_time = timezone.now()

        # Auto-enable GPS tracking for ALL trips (even if browser location permission denied)
        form.instance.gps_tracking_enabled = True
        
        # Handle GPS coordinates if provided (optional)
        gps_start_lat = self.request.POST.get('gps_start_lat')
        gps_start_lon = self.request.POST.get('gps_start_lon')
        
        print(f"GPS Debug - Auto-enabled GPS tracking, Lat: {gps_start_lat}, Lon: {gps_start_lon}")
        
        if gps_start_lat and gps_start_lon:
            try:
                from decimal import Decimal
                form.instance.gps_start_lat = Decimal(gps_start_lat)
                form.instance.gps_start_lon = Decimal(gps_start_lon)
                print(f"GPS Debug - Starting coordinates saved: {form.instance.gps_start_lat}, {form.instance.gps_start_lon}")
            except (ValueError, Exception) as e:
                print(f"GPS Debug - Error saving coordinates: {str(e)}")
                messages.warning(self.request, f'GPS coordinates could not be saved: {str(e)}')
        else:
            print("GPS Debug - No starting coordinates provided (location permission denied or unavailable)")
        
        # Update vehicle status to 'in_use'
        vehicle = form.instance.vehicle
        vehicle.status = 'in_use'
        vehicle.save()

        # Save the trip first to get the trip ID
        response = super().form_valid(form)
        
        # Create GPS tracking session if GPS is enabled
        if form.instance.gps_tracking_enabled:
            try:
                GPSTrackingSession.objects.create(
                    trip=form.instance,
                    status='active'
                )
            except Exception as e:
                messages.warning(self.request, f'GPS tracking session could not be created: {str(e)}')
        
        # Success message with user role indication
        if current_driver == self.request.user:
            success_msg = f'Trip started successfully from {form.instance.origin}!'
            if form.instance.gps_tracking_enabled:
                success_msg += ' GPS tracking is active.'
                # Store trip ID in session to start GPS tracking on trip list page
                self.request.session['start_gps_tracking'] = form.instance.id
            messages.success(self.request, success_msg)
        else:
            success_msg = f'Trip started successfully for {current_driver.get_full_name()} from {form.instance.origin}!'
            if form.instance.gps_tracking_enabled:
                success_msg += ' GPS tracking is active.'
            messages.success(self.request, success_msg)
        
        return response
    
    def form_invalid(self, form):
        # Add specific error messages
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field.title()}: {error}")
        
        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(self.request, error)
        
        return super().form_invalid(form)

class EndTripView(LoginRequiredMixin, UpdateView):
    model = Trip
    form_class = EndTripForm  # Use the form class instead of fields
    template_name = 'trips/end_trip_form.html'
    
    def get_object(self):
        trip = get_object_or_404(Trip, pk=self.kwargs['pk'], status='ongoing')
        
        # Check permissions
        if not trip.can_be_ended_by(self.request.user):
            messages.error(self.request, 'You do not have permission to end this trip.')
            raise PermissionDenied("Cannot end this trip")
        
        return trip
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip = self.get_object()
        context['trip'] = trip
        
        # Add user role information
        context['user_role'] = self.request.user.get_user_type_display()
        context['is_driver'] = trip.driver == self.request.user
        context['is_management'] = self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']
        
        return context
    
    def form_valid(self, form):
        trip = form.instance
        destination = form.cleaned_data.get('destination')
        end_odometer = form.cleaned_data.get('end_odometer')

        # Handle GPS end coordinates if tracking was enabled
        if trip.gps_tracking_enabled:
            gps_end_lat = self.request.POST.get('gps_end_lat')
            gps_end_lon = self.request.POST.get('gps_end_lon')
            
            if gps_end_lat and gps_end_lon:
                try:
                    from decimal import Decimal
                    trip.gps_end_lat = Decimal(gps_end_lat)
                    trip.gps_end_lon = Decimal(gps_end_lon)
                except (ValueError, Exception) as e:
                    messages.warning(self.request, f'GPS end coordinates could not be saved: {str(e)}')

        try:
            # Use the model's end_trip method
            trip.end_trip(
                destination=destination,
                end_odometer=end_odometer, 
                notes=form.cleaned_data.get('notes')
            )
            # Update SOR status if this trip is linked to a SOR
            from sor.models import SOR
            try:
                sor = SOR.objects.get(trip=trip)
                sor.status = 'completed'
                # Set SOR distance_km from trip distance
                sor.distance_km = trip.distance_traveled()
                sor.save()
            except SOR.DoesNotExist:
                pass

            # --- ZeptoMail alert for suspicious distance (async via Celery) ---
            if trip.distance_traveled() > 120:
                send_trip_alert_email_async.delay(trip.pk)

            # Success message with role indication and GPS info
            user_role = self.request.user.get_user_type_display()
            ended_by = "you" if trip.driver == self.request.user else f"{user_role}"
            success_msg = f'Trip ended successfully by {ended_by}! Distance: {trip.distance_traveled()} km'
            
            # Add GPS tracking info if enabled
            if trip.gps_tracking_enabled:
                try:
                    gps_session = GPSTrackingSession.objects.get(trip=trip)
                    if gps_session.requires_review:
                        success_msg += f' (Flagged for review: {gps_session.review_reason})'
                except GPSTrackingSession.DoesNotExist:
                    pass
            
            messages.success(self.request, success_msg)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'Error ending trip: {str(e)}')
            return self.form_invalid(form)
        return redirect('trip_detail', pk=trip.pk)
    
    def form_invalid(self, form):
        # Add form errors to messages
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        return super().form_invalid(form)
    
class ManualTripCreateView(LoginRequiredMixin, VehicleManagerRequiredMixin, CreateView):
    """
    View for manually creating trips by admins/managers for drivers without mobile devices.
    """
    model = Trip
    template_name = 'trips/manual_trip_create.html'
    fields = ['vehicle', 'driver', 'origin', 'destination', 'start_time', 'end_time', 
              'start_odometer', 'end_odometer', 'purpose', 'notes']
    success_url = reverse_lazy('trip_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get company vehicles only for selection
        context['vehicles'] = Vehicle.objects.filter(ownership_type='company').select_related('vehicle_type')
        
        # Get all drivers
        from accounts.models import CustomUser
        context['drivers'] = CustomUser.objects.filter(
            user_type='driver'
        ).order_by('first_name', 'last_name')
        
        # Add available vehicle types for filtering
        try:
            from vehicles.models import VehicleType
            context['vehicle_types'] = VehicleType.objects.all()
        except ImportError:
            context['vehicle_types'] = []
        
        return context
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                trip = form.instance
                
                # Validate dates
                if trip.end_time and trip.start_time and trip.end_time <= trip.start_time:
                    messages.error(self.request, 'End time must be after start time.')
                    return self.form_invalid(form)
                
                # Validate odometer readings
                if trip.end_odometer and trip.start_odometer:
                    if trip.end_odometer <= trip.start_odometer:
                        messages.error(
                            self.request, 
                            f'End odometer ({trip.end_odometer}) must be greater than start odometer ({trip.start_odometer}).'
                        )
                        return self.form_invalid(form)
                
                # Set status based on whether end time is provided
                if trip.end_time and trip.end_odometer:
                    trip.status = 'completed'
                else:
                    trip.status = 'ongoing'
                
                # Save the trip
                trip.save()
                
                # Update vehicle odometer if trip is completed
                if trip.status == 'completed' and trip.end_odometer:
                    vehicle = trip.vehicle
                    if not vehicle.current_odometer or trip.end_odometer > vehicle.current_odometer:
                        vehicle.current_odometer = trip.end_odometer
                        vehicle.save()
                
                # Add success message
                user_role = self.request.user.get_user_type_display()
                messages.success(
                    self.request,
                    f'Trip manually added by {user_role} for {trip.driver.get_full_name()} - {trip.get_route_summary()}'
                )
                
                return super().form_valid(form)
                
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'Error creating trip: {str(e)}')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        # Add form errors to messages
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        return super().form_invalid(form)


# Update your ManualTripListView in views.py

logger = logging.getLogger(__name__)

class ManualTripListView(LoginRequiredMixin, VehicleManagerRequiredMixin, ListView):
    model = Trip
    template_name = 'trips/manual_trip_list.html'
    context_object_name = 'trips'
    paginate_by = 20

    def get_queryset(self):
        queryset = Trip.objects.filter(is_deleted=False).select_related('vehicle', 'driver').order_by('-start_time')

        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search) |
                Q(driver__first_name__icontains=search) |
                Q(driver__last_name__icontains=search) |
                Q(origin__icontains=search) |
                Q(destination__icontains=search) |
                Q(purpose__icontains=search)
            )

        # Improved date filtering logic
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from and date_to:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                # If same day, use exact date match instead of range
                if date_from_obj == date_to_obj:
                    queryset = queryset.filter(start_time__date=date_from_obj)
                else:
                    queryset = queryset.filter(
                        start_time__date__gte=date_from_obj,
                        start_time__date__lte=date_to_obj
                    )
            except ValueError:
                logger.warning(f"Invalid date format: date_from={date_from}, date_to={date_to}")
        elif date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(start_time__date__gte=date_from_obj)
            except ValueError:
                logger.warning(f"Invalid date_from: {date_from}")
        elif date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(start_time__date__lte=date_to_obj)
            except ValueError:
                logger.warning(f"Invalid date_to: {date_to}")

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        driver_id = self.request.GET.get('driver')
        if driver_id and driver_id.isdigit():
            queryset = queryset.filter(driver_id=int(driver_id))

        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id and vehicle_id.isdigit():
            queryset = queryset.filter(vehicle_id=int(vehicle_id))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_params'] = {
            'search': self.request.GET.get('search', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'status': self.request.GET.get('status', ''),
            'driver': self.request.GET.get('driver', ''),
            'vehicle': self.request.GET.get('vehicle', ''),
            'date_filter': self.request.GET.get('date_filter', ''),  # Add date_filter parameter
        }

        context['all_drivers'] = CustomUser.objects.filter(user_type='driver').order_by('first_name', 'last_name')
        context['all_vehicles'] = Vehicle.objects.filter(ownership_type='company').order_by('license_plate')

        all_trips = self.get_queryset()
        context['total_trips'] = all_trips.count()
        context['ongoing_trips'] = all_trips.filter(status='ongoing').count()
        context['completed_trips'] = all_trips.filter(status='completed').count()
        context['cancelled_trips'] = all_trips.filter(status='cancelled').count()

        completed_trips = all_trips.filter(
            status='completed',
            end_odometer__isnull=False,
            start_odometer__isnull=False
        )
        context['total_distance'] = sum(
            trip.distance_traveled() for trip in completed_trips if trip.distance_traveled() > 0
        )

        return context

from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def trip_edit(request, pk):
    """Edit a trip - handles both manual and auto-tracked trips"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Check permissions - only admins and managers can edit trips
    if request.user.user_type not in ['admin', 'manager']:
        messages.error(request, "You don't have permission to edit this trip.")
        return redirect('trip_detail', pk=trip.pk)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                driver_id = request.POST.get('driver')
                vehicle_id = request.POST.get('vehicle')
                
                if not driver_id or not vehicle_id:
                    messages.error(request, 'Driver and Vehicle are required.')
                    return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                try:
                    driver = User.objects.get(id=driver_id)
                    vehicle = Vehicle.objects.get(id=vehicle_id)
                except (User.DoesNotExist, Vehicle.DoesNotExist, ValueError):
                    messages.error(request, 'Invalid driver or vehicle selected.')
                    return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                # Store original values for comparison
                original_vehicle = trip.vehicle
                original_status = trip.status
                
                # Update trip fields
                trip.driver = driver
                trip.vehicle = vehicle
                trip.origin = request.POST.get('origin', trip.origin).strip()
                trip.destination = request.POST.get('destination', trip.destination).strip()
                trip.purpose = request.POST.get('purpose', trip.purpose).strip()
                trip.notes = request.POST.get('notes', trip.notes).strip()
                trip.status = request.POST.get('status', trip.status)
                
                # Validate required fields
                if not trip.origin or not trip.destination or not trip.purpose:
                    messages.error(request, 'Origin, destination, and purpose are required.')
                    return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                # Handle datetime fields
                start_time_str = request.POST.get('start_time')
                if start_time_str:
                    try:
                        trip.start_time = timezone.make_aware(datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M'))
                    except ValueError:
                        messages.error(request, 'Invalid start time format.')
                        return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                end_time_str = request.POST.get('end_time')
                if end_time_str:
                    try:
                        trip.end_time = timezone.make_aware(datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M'))
                    except ValueError:
                        messages.error(request, 'Invalid end time format.')
                        return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                else:
                    trip.end_time = None
                
                # Validate end time is after start time
                if trip.end_time and trip.start_time and trip.end_time <= trip.start_time:
                    messages.error(request, 'End time must be after start time.')
                    return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                # Handle odometer fields
                start_odometer_str = request.POST.get('start_odometer')
                if start_odometer_str:
                    try:
                        trip.start_odometer = int(start_odometer_str)
                    except (ValueError, TypeError):
                        messages.error(request, 'Invalid start odometer value.')
                        return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                end_odometer_str = request.POST.get('end_odometer')
                if end_odometer_str:
                    try:
                        trip.end_odometer = int(end_odometer_str)
                    except (ValueError, TypeError):
                        messages.error(request, 'Invalid end odometer value.')
                        return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                else:
                    trip.end_odometer = None
                
                # Validate odometer readings
                if (trip.end_odometer and trip.start_odometer and 
                    trip.end_odometer <= trip.start_odometer):
                    messages.error(request, 'End odometer must be greater than start odometer.')
                    return render(request, 'trips/trip_edit.html', get_edit_context(trip))
                
                # Handle vehicle status changes
                if original_vehicle != vehicle:
                    # If changing vehicles and trip is ongoing
                    if trip.status == 'ongoing':
                        # Set original vehicle back to available
                        original_vehicle.status = 'available'
                        original_vehicle.save()
                        # Set new vehicle to in_use
                        vehicle.status = 'in_use'
                        vehicle.save()
                
                # Handle status changes
                if original_status != trip.status:
                    if trip.status == 'ongoing':
                        vehicle.status = 'in_use'
                        vehicle.save()
                    elif original_status == 'ongoing' and trip.status in ['completed', 'cancelled']:
                        vehicle.status = 'available'
                        if trip.status == 'completed' and trip.end_odometer:
                            vehicle.current_odometer = trip.end_odometer
                        vehicle.save()
                
                # Save the trip
                trip.save()
                
                messages.success(request, f'Trip #{trip.id} updated successfully!')
                return redirect('trip_detail', pk=trip.pk)
                
        except Exception as e:
            messages.error(request, f'Error updating trip: {str(e)}')
            return render(request, 'trips/trip_edit.html', get_edit_context(trip))
    
    # GET request - show the edit form
    return render(request, 'trips/trip_edit.html', get_edit_context(trip))


def get_edit_context(trip):
    """Helper function to get context for trip edit form"""
    # Get all drivers - you can customize this based on your User model
    drivers = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    # Get company vehicles only
    vehicles = Vehicle.objects.filter(ownership_type='company').order_by('license_plate')
    
    return {
        'trip': trip,
        'drivers': drivers,
        'vehicles': vehicles
    }

# Alternative version if you want to be more specific about filtering
@login_required 
def trip_edit_filtered(request, pk):
    """Alternative version with better filtering"""
    trip = get_object_or_404(Trip, pk=pk)
    
    if request.method == 'POST':
        # ... same POST logic as above ...
        pass
    
    # Get drivers - you can customize this based on your User model
    drivers = User.objects.all()
    
    # Get company vehicles only
    vehicles = Vehicle.objects.filter(ownership_type='company')
    
    # If you know the exact status values, use something like:
    # vehicles = Vehicle.objects.filter(status__in=['active', 'available', 'operational'])
    
    context = {
        'trip': trip,
        'drivers': drivers,
        'vehicles': vehicles
    }
    
    return render(request, 'trips/trip_edit.html', context)

@login_required
def trip_update(request, pk):
    """AJAX trip update"""
    if request.method == 'POST':
        trip = get_object_or_404(Trip, pk=pk)
        # Handle AJAX update logic here
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})

@login_required
@require_http_methods(["DELETE", "POST"])
def trip_delete(request, pk):
    """Delete a trip"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Check permissions - only admins and managers can delete trips
    if request.user.user_type not in ['admin', 'manager']:
        messages.error(request, "You don't have permission to delete this trip.")
        return redirect('trip_detail', pk=trip.pk)
    
    # Store trip info for the success message before deletion
    trip_info = f"Trip {trip.id} - {trip.vehicle.license_plate} ({trip.get_route_summary()})"
    
    if request.method == 'DELETE' or request.method == 'POST':
        try:
            # If the trip is ongoing, update vehicle status back to available
            if trip.status == 'ongoing':
                vehicle = trip.vehicle
                vehicle.status = 'available'
                vehicle.save()
            
            # Delete the trip
            trip.soft_delete(request.user)
            
            # Handle different response types
            if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
                return JsonResponse({'status': 'success', 'message': f'{trip_info} deleted successfully!'})
            else:
                messages.success(request, f'{trip_info} deleted successfully!')
                return redirect('trip_list')
                
        except Exception as e:
            error_msg = f'Error deleting trip: {str(e)}'
            if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
                return JsonResponse({'status': 'error', 'message': error_msg})
            else:
                messages.error(request, error_msg)
                return redirect('trip_detail', pk=pk)
    
    # If GET request, redirect to trip detail
    return redirect('trip_detail', pk=pk)
@login_required
@require_http_methods(["GET"])
def export_manual_trips(request):
    """Export manual trips in various formats"""
    
    # Check permissions
    if request.user.user_type not in ['admin', 'manager', 'vehicle_manager']:
        return HttpResponse('Unauthorized', status=401)
    
    # Get export parameters
    export_format = request.GET.get('format', 'csv')
    include_notes = request.GET.get('include_notes', 'true') == 'true'
    include_driver = request.GET.get('include_driver', 'true') == 'true'
    include_vehicle = request.GET.get('include_vehicle', 'true') == 'true'
    
    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    search = request.GET.get('search')
    trip_ids = request.GET.get('trip_ids')
    vehicle_type_id = request.GET.get('vehicle_type')
    
    # Build queryset
    queryset = Trip.objects.filter(is_deleted=False).select_related('vehicle', 'driver').order_by('-start_time')
    
    # Apply filters
    if trip_ids:
        # Export specific trips
        trip_id_list = [int(id) for id in trip_ids.split(',') if id.isdigit()]
        queryset = queryset.filter(id__in=trip_id_list)
    else:
        # Apply general filters
        if date_from and date_to:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                # Convert dates to timezone-aware datetime objects
                date_from_start = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
                date_to_end = timezone.make_aware(
                    datetime.combine(date_to_obj, datetime.max.time())
                )
                
                # Filter for trips that were active during this period
                queryset = queryset.filter(
                    Q(start_time__lte=date_to_end) & 
                    (Q(end_time__gte=date_from_start) | Q(end_time__isnull=True))
                )
                
            except ValueError:
                logger.warning(f"Invalid date format in manual export: date_from={date_from}, date_to={date_to}")
                
        elif date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_from_start = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
                
                queryset = queryset.filter(
                    Q(end_time__gte=date_from_start) | Q(end_time__isnull=True)
                )
            except ValueError:
                logger.warning(f"Invalid date_from in manual export: {date_from}")
                
        elif date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                date_to_end = timezone.make_aware(
                    datetime.combine(date_to_obj, datetime.max.time())
                )
                
                queryset = queryset.filter(start_time__lte=date_to_end)
            except ValueError:
                logger.warning(f"Invalid date_to in manual export: {date_to}")
                
        if status:
            queryset = queryset.filter(status=status)
        if vehicle_type_id and vehicle_type_id.isdigit():
            queryset = queryset.filter(vehicle__vehicle_type_id=int(vehicle_type_id))
        if search:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search) |
                Q(driver__first_name__icontains=search) |
                Q(driver__last_name__icontains=search) |
                Q(origin__icontains=search) |
                Q(destination__icontains=search)
            )
    
    # Limit export to prevent server overload
    MAX_EXPORT_ROWS = 50000
    queryset = queryset[:MAX_EXPORT_ROWS]
    
    # Generate export based on format
    if export_format == 'csv':
        return export_trips_csv(queryset, include_notes, include_driver, include_vehicle)
    elif export_format == 'excel':
        return export_trips_excel(queryset, include_notes, include_driver, include_vehicle)
    elif export_format == 'pdf':
        return export_trips_pdf(queryset, include_notes, include_driver, include_vehicle)
    else:
        return HttpResponse('Invalid format', status=400)


def export_trips_csv(queryset, include_notes, include_driver, include_vehicle):
    """Export trips to CSV format using .values() for speed"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="manual_trips_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response['X-Accel-Buffering'] = 'no'
    
    writer = csv.writer(response)
    
    # Build headers
    headers = ['Trip ID', 'Origin', 'Destination', 'Start Date', 'Start Time', 'End Date', 'End Time', 
               'Start Odometer', 'End Odometer', 'Distance (km)', 'Status', 'Purpose']
    
    if include_driver:
        headers.extend(['Driver Name', 'Driver Email'])
    if include_vehicle:
        headers.extend(['Vehicle Type', 'Vehicle License Plate', 'Vehicle Make', 'Vehicle Model', 'Rate per KM (₹)'])
    
    headers.append('Cost (₹)')
    
    if include_notes:
        headers.append('Notes')
    
    writer.writerow(headers)
    
    # Use .values() to avoid model instantiation - much faster
    fields = [
        'id', 'origin', 'destination', 'start_time', 'end_time',
        'start_odometer', 'end_odometer', 'status', 'purpose', 'notes',
        'driver__first_name', 'driver__last_name', 'driver__email',
        'vehicle__vehicle_type__name', 'vehicle__license_plate', 'vehicle__make', 'vehicle__model', 'vehicle__rate_per_km',
    ]
    
    for trip in queryset.values(*fields).iterator():
        start_odo = trip['start_odometer']
        end_odo = trip['end_odometer']
        distance = max(0, end_odo - start_odo) if end_odo and start_odo else None
        
        rate = trip['vehicle__rate_per_km']
        if distance and rate:
            cost = f'{float(distance) * float(rate):.2f}'
        elif distance and not rate:
            cost = 'Rate not set'
        else:
            cost = 'N/A'
        
        start_time = trip['start_time']
        end_time = trip['end_time']
        
        row = [
            trip['id'],
            trip['origin'] or '',
            trip['destination'] or '',
            start_time.strftime('%Y-%m-%d') if start_time else '',
            start_time.strftime('%H:%M') if start_time else '',
            end_time.strftime('%Y-%m-%d') if end_time else '',
            end_time.strftime('%H:%M') if end_time else '',
            start_odo or '',
            end_odo or '',
            distance if distance else '',
            trip['status'].title() if trip['status'] else '',
            trip['purpose'] or '',
        ]
        
        if include_driver:
            first = trip['driver__first_name'] or ''
            last = trip['driver__last_name'] or ''
            row.extend([f"{first} {last}".strip(), trip['driver__email'] or ''])
        if include_vehicle:
            rate_display = f'{float(rate):.2f}' if rate else 'Not set'
            row.extend([
                trip['vehicle__vehicle_type__name'] or '',
                trip['vehicle__license_plate'] or '',
                trip['vehicle__make'] or '',
                trip['vehicle__model'] or '',
                rate_display
            ])
        
        row.append(cost)
        
        if include_notes:
            row.append(trip['notes'] or '')
        
        writer.writerow(row)
    
    return response


def export_trips_excel(queryset, include_notes, include_driver, include_vehicle):
    """Export trips to Excel format"""
    # Check if xlsxwriter is available
    if not XLSX_AVAILABLE:
        # Fallback to CSV if xlsxwriter is not available
        messages.warning(
            None, 
            'Excel export is not available. The xlsxwriter package is not installed. Falling back to CSV format.'
        )
        return export_trips_csv(queryset, include_notes, include_driver, include_vehicle)
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'constant_memory': True})
    worksheet = workbook.add_worksheet('Manual Trips')
    
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4e73df',
        'font_color': 'white',
        'border': 1
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'valign': 'top'
    })
    
    date_format = workbook.add_format({
        'border': 1,
        'num_format': 'yyyy-mm-dd'
    })
    
    time_format = workbook.add_format({
        'border': 1,
        'num_format': 'hh:mm'
    })
    
    # Build headers
    headers = ['Trip ID', 'Origin', 'Destination', 'Start Date', 'Start Time', 'End Date', 'End Time', 
               'Start Odometer', 'End Odometer', 'Distance (km)', 'Status', 'Purpose']
    
    if include_driver:
        headers.extend(['Driver Name', 'Driver Email'])
    if include_vehicle:
        headers.extend(['Vehicle Type', 'Vehicle License Plate', 'Vehicle Make', 'Vehicle Model', 'Rate per KM (₹)'])
    
    headers.append('Cost (₹)')  # Always include cost column
    
    if include_notes:
        headers.append('Notes')
    
    # Define currency format
    currency_format = workbook.add_format({
        'border': 1,
        'num_format': '₹#,##0.00',
        'valign': 'top'
    })
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # Use .values() to avoid model instantiation - much faster
    fields = [
        'id', 'origin', 'destination', 'start_time', 'end_time',
        'start_odometer', 'end_odometer', 'status', 'purpose', 'notes',
        'driver__first_name', 'driver__last_name', 'driver__email',
        'vehicle__vehicle_type__name', 'vehicle__license_plate', 'vehicle__make', 'vehicle__model', 'vehicle__rate_per_km',
    ]
    
    for row_num, trip in enumerate(queryset.values(*fields).iterator(), 1):
        col = 0
        start_time = trip['start_time']
        end_time = trip['end_time']
        start_odo = trip['start_odometer']
        end_odo = trip['end_odometer']
        rate = trip['vehicle__rate_per_km']
        
        # Basic trip data
        worksheet.write(row_num, col, trip['id'], cell_format)
        col += 1
        worksheet.write(row_num, col, trip['origin'] or '', cell_format)
        col += 1
        worksheet.write(row_num, col, trip['destination'] or '', cell_format)
        col += 1
        worksheet.write(row_num, col, start_time.strftime('%Y-%m-%d') if start_time else '', cell_format)
        col += 1
        worksheet.write(row_num, col, start_time.strftime('%H:%M') if start_time else '', cell_format)
        col += 1
        worksheet.write(row_num, col, end_time.strftime('%Y-%m-%d') if end_time else '', cell_format)
        col += 1
        worksheet.write(row_num, col, end_time.strftime('%H:%M') if end_time else '', cell_format)
        col += 1
        worksheet.write(row_num, col, start_odo or '', cell_format)
        col += 1
        worksheet.write(row_num, col, end_odo or '', cell_format)
        col += 1
        
        # Calculate distance inline
        distance = max(0, end_odo - start_odo) if end_odo and start_odo else None
        worksheet.write(row_num, col, distance if distance else '', cell_format)
        col += 1
        
        worksheet.write(row_num, col, trip['status'].title() if trip['status'] else '', cell_format)
        col += 1
        worksheet.write(row_num, col, trip['purpose'] or '', cell_format)
        col += 1
        
        # Optional fields
        if include_driver:
            first = trip['driver__first_name'] or ''
            last = trip['driver__last_name'] or ''
            worksheet.write(row_num, col, f"{first} {last}".strip(), cell_format)
            col += 1
            worksheet.write(row_num, col, trip['driver__email'] or '', cell_format)
            col += 1
        if include_vehicle:
            worksheet.write(row_num, col, trip['vehicle__vehicle_type__name'] or '', cell_format)
            col += 1
            worksheet.write(row_num, col, trip['vehicle__license_plate'] or '', cell_format)
            col += 1
            worksheet.write(row_num, col, trip['vehicle__make'] or '', cell_format)
            col += 1
            worksheet.write(row_num, col, trip['vehicle__model'] or '', cell_format)
            col += 1
            if rate:
                worksheet.write(row_num, col, float(rate), currency_format)
            else:
                worksheet.write(row_num, col, 'Not set', cell_format)
            col += 1
        
        # Calculate and write cost
        if distance and rate:
            worksheet.write(row_num, col, float(distance) * float(rate), currency_format)
        elif distance and not rate:
            worksheet.write(row_num, col, 'Rate not set', cell_format)
        else:
            worksheet.write(row_num, col, 'N/A', cell_format)
        col += 1
        
        if include_notes:
            worksheet.write(row_num, col, trip['notes'] or '', cell_format)
    
    # Set fixed column widths (autofit is incompatible with constant_memory mode)
    for col_idx in range(len(headers)):
        worksheet.set_column(col_idx, col_idx, 18)
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=\"manual_trips_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx\"'
    response['X-Accel-Buffering'] = 'no'
    
    return response


def export_trips_pdf(queryset, include_notes, include_driver, include_vehicle):
    """Export trips to PDF format"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Title
    styles = getSampleStyleSheet()
    title = Paragraph("Manual Trips Report", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Summary
    summary_text = f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
    summary = Paragraph(summary_text, styles['Normal'])
    elements.append(summary)
    elements.append(Spacer(1, 12))
    
    # Prepare table data
    headers = ['ID', 'Route', 'Date', 'Status', 'Distance']
    if include_driver:
        headers.append('Driver')
    if include_vehicle:
        headers.append('Vehicle')
    headers.append('Cost (₹)')  # Always include cost
    
    data = [headers]
    
    # Use .values() to avoid model instantiation
    fields = [
        'id', 'origin', 'destination', 'start_time', 'start_odometer', 'end_odometer',
        'status', 'driver__first_name', 'driver__last_name',
        'vehicle__vehicle_type__name', 'vehicle__license_plate', 'vehicle__make', 'vehicle__model', 'vehicle__rate_per_km',
    ]
    
    for trip in queryset.values(*fields).iterator():
        start_odo = trip['start_odometer']
        end_odo = trip['end_odometer']
        distance = max(0, end_odo - start_odo) if end_odo and start_odo else None
        distance_text = f"{distance} km" if distance else 'N/A'
        
        rate = trip['vehicle__rate_per_km']
        if distance and rate:
            cost_text = f"₹{float(distance) * float(rate):,.2f}"
        elif distance and not rate:
            cost_text = 'Rate not set'
        else:
            cost_text = 'N/A'
        
        row = [
            str(trip['id']),
            f"{trip['origin'] or ''} → {trip['destination'] or ''}",
            trip['start_time'].strftime('%Y-%m-%d') if trip['start_time'] else 'N/A',
            trip['status'].title() if trip['status'] else '',
            distance_text
        ]
        
        if include_driver:
            first = trip['driver__first_name'] or ''
            last = trip['driver__last_name'] or ''
            row.append(f"{first} {last}".strip())
        if include_vehicle:
            vtype = trip['vehicle__vehicle_type__name'] or ''
            lp = trip['vehicle__license_plate'] or ''
            make = trip['vehicle__make'] or ''
            model = trip['vehicle__model'] or ''
            row.append(f"{vtype} - {lp}\n{make} {model}" if lp else '')
        
        row.append(cost_text)
        data.append(row)
    
    # Create table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=\"manual_trips_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf\"'
    response['X-Accel-Buffering'] = 'no'
    
    return response


@login_required
@require_http_methods(["GET"])
def export_trips(request):
    """Export trips from trip list in various formats"""
    
    # Check permissions - allow drivers to export their own trips, managers to export all
    if request.user.user_type not in ['admin', 'manager', 'vehicle_manager', 'driver']:
        return HttpResponse('Unauthorized', status=401)
    
    # Get export parameters
    export_format = request.GET.get('format', 'csv')
    include_notes = request.GET.get('include_notes', 'true') == 'true'
    include_driver = request.GET.get('include_driver', 'true') == 'true'
    include_vehicle = request.GET.get('include_vehicle', 'true') == 'true'
    
    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    search = request.GET.get('search')
    vehicle_id = request.GET.get('vehicle')
    vehicle_type_id = request.GET.get('vehicle_type')
    
    # Build queryset based on user permissions
    if request.user.user_type == 'driver':
        queryset = Trip.objects.filter(driver=request.user, is_deleted=False)
    elif request.user.user_type in ['admin', 'manager', 'vehicle_manager']:
        queryset = Trip.objects.filter(is_deleted=False)
    else:
        queryset = Trip.objects.none()
    
    # Apply search filter
    if search:
        queryset = queryset.filter(
            Q(vehicle__license_plate__icontains=search) |
            Q(vehicle__make__icontains=search) |
            Q(vehicle__model__icontains=search) |
            Q(driver__first_name__icontains=search) |
            Q(driver__last_name__icontains=search) |
            Q(origin__icontains=search) |
            Q(destination__icontains=search) |
            Q(purpose__icontains=search)
        )
    
    if vehicle_id and vehicle_id.isdigit():
        queryset = queryset.filter(vehicle_id=int(vehicle_id))
    
    if vehicle_type_id and vehicle_type_id.isdigit():
        queryset = queryset.filter(vehicle__vehicle_type_id=int(vehicle_type_id))
    
    if status:
        queryset = queryset.filter(status=status)
    
    # FIXED: Apply the same working date filtering logic
    if date_from and date_to:
        try:
            # Parse the dates
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            
            # Create timezone-aware datetime objects for the full day range
            from django.utils import timezone
            
            # Start of the from_date (00:00:00)
            date_from_start = timezone.make_aware(
                datetime.combine(date_from_obj, datetime.min.time())
            )
            # End of the to_date (23:59:59.999999)
            date_to_end = timezone.make_aware(
                datetime.combine(date_to_obj, datetime.max.time())
            )
            
            # Filter trips that started within this range
            queryset = queryset.filter(
                start_time__gte=date_from_start,
                start_time__lte=date_to_end
            )
            
        except ValueError:
            logger.warning(f"Invalid date format in export: date_from={date_from}, date_to={date_to}")
            
    elif date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_from_start = timezone.make_aware(
                datetime.combine(date_from_obj, datetime.min.time())
            )
            
            # Get trips that started on or after this date
            queryset = queryset.filter(start_time__gte=date_from_start)
            
        except ValueError:
            logger.warning(f"Invalid date_from in export: {date_from}")
            
    elif date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            date_to_end = timezone.make_aware(
                datetime.combine(date_to_obj, datetime.max.time())
            )
            
            # Get trips that started on or before this date
            queryset = queryset.filter(start_time__lte=date_to_end)
            
        except ValueError:
            logger.warning(f"Invalid date_to in export: {date_to}")
    
    # Order by start time
    queryset = queryset.select_related('vehicle', 'driver').order_by('-start_time')
    
    # Limit export to prevent server overload
    MAX_EXPORT_ROWS = 50000
    queryset = queryset[:MAX_EXPORT_ROWS]
    
    # Generate export based on format
    if export_format == 'csv':
        return export_trips_csv(queryset, include_notes, include_driver, include_vehicle)
    elif export_format == 'excel':
        return export_trips_excel(queryset, include_notes, include_driver, include_vehicle)
    elif export_format == 'pdf':
        return export_trips_pdf(queryset, include_notes, include_driver, include_vehicle)
    else:
        return HttpResponse('Invalid format', status=400)
    

class StaffTripsView(AdminRequiredMixin, ListView):
    """
    Admin-only view to monitor personal vehicle staff trips with GPS tracking
    Shows discrepancies between GPS and odometer readings
    """
    model = Trip
    template_name = 'trips/staff_trips.html'
    context_object_name = 'trips'
    paginate_by = 25
    
    def get_queryset(self):
        # Get trips by personal vehicle staff with GPS tracking enabled
        queryset = Trip.objects.filter(
            driver__user_type='personal_vehicle_staff',
            gps_tracking_enabled=True,
            status__in=['ongoing', 'completed']
        ).select_related('driver', 'vehicle', 'gps_session').order_by('-start_time')
        
        # Filter by status
        status_filter = self.request.GET.get('status_filter', 'all')
        if status_filter == 'ongoing':
            queryset = queryset.filter(status='ongoing')
        elif status_filter == 'completed':
            queryset = queryset.filter(status='completed')
        
        # Filter by review status
        review_filter = self.request.GET.get('review_filter', 'all')
        if review_filter == 'flagged':
            queryset = queryset.filter(gps_session__requires_review=True)
        elif review_filter == 'high_variance':
            queryset = queryset.filter(gps_session__variance_percentage__gt=15)
        elif review_filter == 'pending_review':
            queryset = queryset.filter(
                gps_session__requires_review=True,
                gps_session__approved__isnull=True
            )
        
        # Search by driver name or vehicle
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(driver__first_name__icontains=search) |
                Q(driver__last_name__icontains=search) |
                Q(vehicle__license_plate__icontains=search) |
                Q(origin__icontains=search) |
                Q(destination__icontains=search)
            )
        
        # Date range filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(start_time__date__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(start_time__date__lte=date_to_obj)
            except ValueError:
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate summary statistics - include all status for count
        all_staff_trips = Trip.objects.filter(
            driver__user_type='personal_vehicle_staff',
            gps_tracking_enabled=True,
            status__in=['ongoing', 'completed']
        )
        completed_trips = all_staff_trips.filter(status='completed')
        
        context['total_staff_trips'] = all_staff_trips.count()
        context['ongoing_trips'] = all_staff_trips.filter(status='ongoing').count()
        context['completed_trips'] = completed_trips.count()
        context['flagged_trips'] = completed_trips.filter(gps_session__requires_review=True).count()
        context['high_variance_trips'] = completed_trips.filter(gps_session__variance_percentage__gt=15).count()
        context['pending_review_trips'] = completed_trips.filter(
            gps_session__requires_review=True,
            gps_session__approved__isnull=True
        ).count()
        
        # Pass current filters
        context['status_filter'] = self.request.GET.get('status_filter', 'all')
        context['review_filter'] = self.request.GET.get('review_filter', 'all')
        context['search'] = self.request.GET.get('search', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        return context


class TripDetailMapView(LoginRequiredMixin, DetailView):
    """
    View to display a single trip with GPS route visualization on a map
    Shows route playback with animation controls
    """
    model = Trip
    template_name = 'trips/trip_detail_map.html'
    context_object_name = 'trip'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip = self.get_object()
        
        # Get GPS points for this trip
        gps_points = trip.gps_locations.all().order_by('timestamp')
        
        if gps_points.exists():
            # Convert to JSON format for JavaScript
            points_data = []
            cumulative_distance = 0
            prev_point = None
            
            for point in gps_points:
                # Calculate cumulative distance
                if prev_point:
                    from trips.gps_models import TripLocation
                    distance = TripLocation.calculate_distance(
                        prev_point.latitude, prev_point.longitude,
                        point.latitude, point.longitude
                    )
                    cumulative_distance += distance
                
                points_data.append({
                    'latitude': float(point.latitude),
                    'longitude': float(point.longitude),
                    'timestamp': point.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'speed': float(point.speed) if point.speed else 0,
                    'cumulative_distance': round(cumulative_distance, 2)
                })
                prev_point = point
            
            context['gps_points_json'] = json.dumps(points_data)
        else:
            context['gps_points_json'] = json.dumps([])
        
        return context


class LiveTrackingView(LoginRequiredMixin, TemplateView):
    """
    Real-time tracking dashboard showing all active trips on a map
    Updates vehicle positions dynamically
    """
    template_name = 'trips/live_tracking.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all ongoing trips with GPS tracking
        active_trips = Trip.objects.filter(
            status='ongoing',  # Changed from 'in_progress' to 'ongoing'
            gps_tracking_enabled=True
        ).select_related('driver', 'vehicle', 'gps_session').order_by('-start_time')
        
        context['active_trips'] = active_trips
        context['active_count'] = active_trips.count()
        
        return context


class LiveTrackingDataView(LoginRequiredMixin, View):
    """
    API endpoint for AJAX polling to get live vehicle positions
    Returns JSON with current positions of all active trips
    """
    def get(self, request):
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        
        all_trips = Trip.objects.all().count()
        all_ongoing = Trip.objects.filter(status='ongoing').count()
        gps_enabled = Trip.objects.filter(gps_tracking_enabled=True).count()
        
        logger.info(f"Live Tracking DEBUG - Total trips: {all_trips}, Ongoing: {all_ongoing}, GPS enabled (any status): {gps_enabled}")
        
        # Log all trips with their statuses
        all_trips_list = Trip.objects.all().order_by('-id')[:10].values('id', 'status', 'gps_tracking_enabled', 'driver__username')
        for t in all_trips_list:
            logger.info(f"  Trip {t['id']}: status={t['status']}, gps_enabled={t['gps_tracking_enabled']}, driver={t.get('driver__username', 'None')}")
        
        active_trips = Trip.objects.filter(
            status='ongoing',  # Changed from 'in_progress' to 'ongoing'
            gps_tracking_enabled=True
        ).select_related('driver', 'vehicle', 'gps_session')
        
        logger.info(f"Live Tracking - Active trips matching filter: {active_trips.count()}")
        
        vehicles_data = []
        for trip in active_trips:
            logger.info(f"Processing trip {trip.id}: {trip.vehicle}")
            try:
                # Get the most recent GPS point
                latest_point = trip.gps_locations.order_by('-timestamp').first()
                logger.info(f"  Latest GPS point: {latest_point}")
                
                # Calculate distance covered from gps_session if available
                distance_covered = 0
                if trip.gps_session and trip.gps_session.gps_distance:
                    distance_covered = float(trip.gps_session.gps_distance)
                
                # Get driver name safely
                driver_name = trip.driver.get_full_name() if hasattr(trip.driver, 'get_full_name') else str(trip.driver)
                logger.info(f"  Driver: {driver_name}")
                
                # If we have GPS data, use it; otherwise show trip with default location
                if latest_point:
                    vehicle_data = {
                        'trip_id': trip.id,
                        'driver': driver_name,
                        'vehicle': str(trip.vehicle),
                        'latitude': float(latest_point.latitude),
                        'longitude': float(latest_point.longitude),
                        'speed': float(latest_point.speed) if latest_point.speed else 0,
                        'timestamp': latest_point.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'route': f"{trip.origin} → {trip.destination}",
                        'distance_covered': distance_covered,
                        'has_gps': True
                    }
                    logger.info(f"  Added with GPS: lat={vehicle_data['latitude']}, lon={vehicle_data['longitude']}")
                    vehicles_data.append(vehicle_data)
                else:
                    # Show trip without GPS data (waiting for first location)
                    vehicle_data = {
                        'trip_id': trip.id,
                        'driver': driver_name,
                        'vehicle': str(trip.vehicle),
                        'latitude': 28.6139,  # Default to India center
                        'longitude': 77.2090,
                        'speed': 0,
                        'timestamp': trip.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'route': f"{trip.origin} → {trip.destination}",
                        'distance_covered': 0,
                        'has_gps': False
                    }
                    logger.info(f"  Added without GPS (default location)")
                    vehicles_data.append(vehicle_data)
            except Exception as e:
                logger.error(f"Error processing trip {trip.id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.info(f"Returning {len(vehicles_data)} vehicles")
        return JsonResponse({
            'vehicles': vehicles_data,
            'count': len(vehicles_data),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
