from django.forms import ValidationError
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from accounts.models import CustomUser
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin, DriverRequiredMixin
from .models import Trip
from vehicles.models import Vehicle
from .forms import TripForm, EndTripForm, ManualTripForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
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
    Allows: drivers, admins, managers, and vehicle_managers
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Allow these user types to drive vehicles
        allowed_user_types = ['driver', 'admin', 'manager', 'vehicle_manager']
        
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
            queryset = Trip.objects.filter(driver=self.request.user)
        elif self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']:
            queryset = Trip.objects.all()
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
            
        # Apply status filter
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        # IMPROVED date filtering logic
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from and date_to:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                # Convert dates to timezone-aware datetime objects
                # Start of day for date_from
                date_from_start = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
                # End of day for date_to
                date_to_end = timezone.make_aware(
                    datetime.combine(date_to_obj, datetime.max.time())
                )
                
                # Filter for trips that were active during this period
                # A trip is active during a period if:
                # 1. It started before or during the period AND
                # 2. It ended after the period started (or hasn't ended yet)
                
                queryset = queryset.filter(
                    Q(start_time__lte=date_to_end) & 
                    (Q(end_time__gte=date_from_start) | Q(end_time__isnull=True))
                )
                
            except ValueError:
                logger.warning(f"Invalid date format: date_from={date_from}, date_to={date_to}")
                
        elif date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_from_start = timezone.make_aware(
                    datetime.combine(date_from_obj, datetime.min.time())
                )
                
                # Get trips that were active on or after this date
                queryset = queryset.filter(
                    Q(end_time__gte=date_from_start) | Q(end_time__isnull=True)
                )
                
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
        
        # Get all trips for separation (without pagination)
        all_trips = self.get_queryset()
        
        # Separate trips by status
        ongoing_trips = []
        completed_trips = []
        cancelled_trips = []
        
        for trip in all_trips:
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
        
        # Add counts
        context['ongoing_count'] = len(ongoing_trips)
        context['completed_count'] = len(completed_trips)
        context['cancelled_count'] = len(cancelled_trips)
        
        # Add vehicles for filter
        if self.request.user.user_type == 'driver':
            context['vehicles'] = Vehicle.objects.filter(
                Q(assigned_driver=self.request.user) | 
                Q(trips__driver=self.request.user)
            ).distinct()
        else:
            context['vehicles'] = Vehicle.objects.all()
        
        # Add search parameters for maintaining filters in pagination
        search_params = {}
        if self.request.GET.get('search'):
            search_params['search'] = self.request.GET.get('search')
        if self.request.GET.get('vehicle'):
            search_params['vehicle'] = self.request.GET.get('vehicle')
        if self.request.GET.get('status'):
            search_params['status'] = self.request.GET.get('status')
        if self.request.GET.get('date_from'):
            search_params['date_from'] = self.request.GET.get('date_from')
        if self.request.GET.get('date_to'):
            search_params['date_to'] = self.request.GET.get('date_to')
        
        context['search_params'] = search_params
        
        # Add user permissions context
        context['can_start_trip'] = self.request.user.user_type in ['driver', 'admin', 'manager', 'vehicle_manager']
        
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
    
class TripTrackingView(LoginRequiredMixin, CanDriveVehicleMixin, TemplateView):
    """
    View for users to track their active trip with geolocation.
    This provides a real-time tracking interface with maps.
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
        
        # Add available vehicles to the context
        available_vehicles = Vehicle.objects.filter(status='available').select_related('vehicle_type')
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
        
        # Update vehicle status to 'in_use'
        vehicle = form.instance.vehicle
        vehicle.status = 'in_use'
        vehicle.save()
        
        # Success message with user role indication
        if current_driver == self.request.user:
            messages.success(
                self.request, 
                f'Trip started successfully from {form.instance.origin} to {form.instance.destination}!'
            )
        else:
            messages.success(
                self.request, 
                f'Trip started successfully for {current_driver.get_full_name()} from {form.instance.origin} to {form.instance.destination}!'
            )
        
        return super().form_valid(form)
    
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
    template_name = 'trips/end_trip_form.html'
    fields = ['end_odometer', 'notes']
    
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
        end_odometer = form.cleaned_data.get('end_odometer')
        
        # Validate end_odometer
        if not end_odometer or end_odometer <= trip.start_odometer:
            messages.error(
                self.request, 
                f'End odometer ({end_odometer}) must be greater than start odometer ({trip.start_odometer}).'
            )
            return self.form_invalid(form)
        
        try:
            # Use the model's end_trip method
            trip.end_trip(end_odometer=end_odometer, notes=form.cleaned_data.get('notes'))
            
            # Success message with role indication
            user_role = self.request.user.get_user_type_display()
            ended_by = "you" if trip.driver == self.request.user else f"{user_role}"
            
            messages.success(
                self.request, 
                f'Trip ended successfully by {ended_by}! Distance: {trip.distance_traveled()} km'
            )
            
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
    success_url = reverse_lazy('manual_trip_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all vehicles for selection
        context['vehicles'] = Vehicle.objects.all().select_related('vehicle_type')
        
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


# class BulkTripUploadView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
#     """
#     View for uploading multiple trips from CSV or Excel files.
#     """
#     template_name = 'trips/bulk_trip_upload.html'
    
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
        
#         # Get all vehicles and drivers for validation
#         context['vehicles'] = Vehicle.objects.all()
#         from accounts.models import CustomUser
#         context['drivers'] = CustomUser.objects.filter(user_type='driver')
        
#         # Sample CSV format
#         context['sample_csv_headers'] = [
#             'Driver Email', 'Vehicle License Plate', 'Origin', 'Destination',
#             'Start Date', 'Start Time', 'End Date', 'End Time',
#             'Start Odometer', 'End Odometer', 'Purpose', 'Notes'
#         ]
        
#         return context
    
#     def post(self, request, *args, **kwargs):
#         if 'file' not in request.FILES:
#             messages.error(request, 'Please select a file to upload.')
#             return redirect('bulk_trip_upload')
        
#         uploaded_file = request.FILES['file']
        
#         # Validate file type
#         if not uploaded_file.name.endswith(('.csv', '.xlsx', '.xls')):
#             messages.error(request, 'Please upload a CSV or Excel file.')
#             return redirect('bulk_trip_upload')
        
#         try:
#             # Process the file
#             if uploaded_file.name.endswith('.csv'):
#                 result = self.process_csv_file(uploaded_file)
#             else:
#                 result = self.process_excel_file(uploaded_file)
            
#             if result['success']:
#                 messages.success(
#                     request,
#                     f'Successfully processed {result["created"]} trips. '
#                     f'{result["errors"]} errors encountered.'
#                 )
#             else:
#                 messages.error(request, f'Upload failed: {result["message"]}')
                
#         except Exception as e:
#             messages.error(request, f'Error processing file: {str(e)}')
        
#         return redirect('bulk_trip_upload')
    
#     def process_csv_file(self, file):
#         """Process CSV file and create trips."""
#         import csv
#         import io
        
#         # Read the CSV file
#         file_content = file.read().decode('utf-8')
#         csv_reader = csv.DictReader(io.StringIO(file_content))
        
#         return self.process_trip_data(csv_reader)
    
#     def process_excel_file(self, file):
#         """Process Excel file and create trips."""
#         import pandas as pd
        
#         # Read the Excel file
#         df = pd.read_excel(file)
        
#         # Convert to dict format similar to CSV
#         trip_data = df.to_dict('records')
        
#         return self.process_trip_data(trip_data)
    
#     def process_trip_data(self, trip_data):
#         """Process trip data and create Trip objects."""
#         from accounts.models import CustomUser
#         created_count = 0
#         error_count = 0
#         errors = []
        
#         for row_num, row in enumerate(trip_data, start=2):
#             try:
#                 with transaction.atomic():
#                     # Get driver by email
#                     driver_email = row.get('Driver Email', '').strip()
#                     if not driver_email:
#                         raise ValueError("Driver email is required")
                    
#                     try:
#                         driver = CustomUser.objects.get(email=driver_email, user_type='driver')
#                     except CustomUser.DoesNotExist:
#                         raise ValueError(f"Driver with email {driver_email} not found")
                    
#                     # Get vehicle by license plate
#                     license_plate = row.get('Vehicle License Plate', '').strip()
#                     if not license_plate:
#                         raise ValueError("Vehicle license plate is required")
                    
#                     try:
#                         vehicle = Vehicle.objects.get(license_plate=license_plate)
#                     except Vehicle.DoesNotExist:
#                         raise ValueError(f"Vehicle with license plate {license_plate} not found")
                    
#                     # Parse dates and times
#                     start_date = row.get('Start Date', '').strip()
#                     start_time = row.get('Start Time', '').strip()
#                     end_date = row.get('End Date', '').strip()
#                     end_time = row.get('End Time', '').strip()
                    
#                     # Combine date and time
#                     start_datetime = self.parse_datetime(start_date, start_time)
#                     end_datetime = self.parse_datetime(end_date, end_time) if end_date and end_time else None
                    
#                     # Get other fields
#                     origin = row.get('Origin', '').strip()
#                     destination = row.get('Destination', '').strip()
#                     start_odometer = int(row.get('Start Odometer', 0))
#                     end_odometer = int(row.get('End Odometer', 0)) if row.get('End Odometer') else None
#                     purpose = row.get('Purpose', '').strip()
#                     notes = row.get('Notes', '').strip()
                    
#                     # Validate required fields
#                     if not all([origin, destination, purpose]):
#                         raise ValueError("Origin, destination, and purpose are required")
                    
#                     # Determine status
#                     status = 'completed' if end_datetime and end_odometer else 'ongoing'
                    
#                     # Create trip
#                     trip = Trip.objects.create(
#                         vehicle=vehicle,
#                         driver=driver,
#                         start_time=start_datetime,
#                         end_time=end_datetime,
#                         start_odometer=start_odometer,
#                         end_odometer=end_odometer,
#                         origin=origin,
#                         destination=destination,
#                         purpose=purpose,
#                         notes=notes,
#                         status=status
#                     )
                    
#                     # Update vehicle odometer if needed
#                     if status == 'completed' and end_odometer:
#                         if not vehicle.current_odometer or end_odometer > vehicle.current_odometer:
#                             vehicle.current_odometer = end_odometer
#                             vehicle.save()
                    
#                     created_count += 1
                    
#             except Exception as e:
#                 error_count += 1
#                 errors.append(f"Row {row_num}: {str(e)}")
        
#         return {
#             'success': True,
#             'created': created_count,
#             'errors': error_count,
#             'error_details': errors
#         }
    
#     def parse_datetime(self, date_str, time_str):
#         """Parse date and time strings into datetime object."""
#         from dateutil import parser
        
#         if not date_str:
#             raise ValueError("Date is required")
        
#         # Try to parse date
#         try:
#             date_obj = parser.parse(date_str).date()
#         except:
#             raise ValueError(f"Invalid date format: {date_str}")
        
#         # Parse time if provided
#         if time_str:
#             try:
#                 time_obj = parser.parse(time_str).time()
#             except:
#                 raise ValueError(f"Invalid time format: {time_str}")
#         else:
#             time_obj = datetime.now().time()
        
#         # Combine date and time
#         return timezone.make_aware(datetime.combine(date_obj, time_obj))


# Update your ManualTripListView in views.py

logger = logging.getLogger(__name__)

class ManualTripListView(LoginRequiredMixin, VehicleManagerRequiredMixin, ListView):
    model = Trip
    template_name = 'trips/manual_trip_list.html'
    context_object_name = 'trips'
    paginate_by = 20

    def get_queryset(self):
        queryset = Trip.objects.all().select_related('vehicle', 'driver').order_by('-start_time')

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
        context['all_vehicles'] = Vehicle.objects.all().order_by('license_plate')

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



# class TripSheetTemplateView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
#     """
#     View to generate and download trip sheet templates for drivers.
#     """
#     template_name = 'trips/trip_sheet_template.html'
    
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
        
#         # Get all vehicles and drivers for reference
#         context['vehicles'] = Vehicle.objects.all().order_by('license_plate')
#         from accounts.models import CustomUser
#         context['drivers'] = CustomUser.objects.filter(
#             user_type='driver'
#         ).order_by('first_name', 'last_name')
        
#         return context


# def get_vehicle_details_api(request, vehicle_id):
#     """
#     API endpoint to get vehicle details for AJAX requests.
#     """
#     if not request.user.is_authenticated:
#         return JsonResponse({'error': 'Authentication required'}, status=401)
    
#     try:
#         vehicle = Vehicle.objects.get(id=vehicle_id)
#         return JsonResponse({
#             'id': vehicle.id,
#             'license_plate': vehicle.license_plate,
#             'make': vehicle.make,
#             'model': vehicle.model,
#             'current_odometer': vehicle.current_odometer,
#             'fuel_type': vehicle.fuel_type,
#             'status': vehicle.status,
#             'vehicle_type': vehicle.vehicle_type.name if vehicle.vehicle_type else '',
#         })
#     except Vehicle.DoesNotExist:
#         return JsonResponse({'error': 'Vehicle not found'}, status=404)


# def get_driver_details_api(request, driver_id):
#     """
#     API endpoint to get driver details for AJAX requests.
#     """
#     if not request.user.is_authenticated:
#         return JsonResponse({'error': 'Authentication required'}, status=401)
    
#     try:
#         from accounts.models import CustomUser
#         driver = CustomUser.objects.get(id=driver_id, user_type='driver')
#         return JsonResponse({
#             'id': driver.id,
#             'full_name': driver.get_full_name(),
#             'email': driver.email,
#             'license_number': getattr(driver, 'license_number', ''),
#             'license_expiry': str(getattr(driver, 'license_expiry', '')) if getattr(driver, 'license_expiry', '') else '',
#         })
#     except:
#         return JsonResponse({'error': 'Driver not found'}, status=404)

from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def trip_edit(request, pk):
    """Edit a trip - handles both manual and auto-tracked trips"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Check permissions - only managers/admins and the driver can edit trips
    if (request.user.user_type not in ['admin', 'manager', 'vehicle_manager'] and 
        request.user != trip.driver):
        messages.error(request, "You don't have permission to edit this trip.")
        return redirect('trip_detail', pk=trip.pk)
    
    if request.method == 'POST':
        driver_id = request.POST.get('driver')
        vehicle_id = request.POST.get('vehicle')
        
        if driver_id and vehicle_id:
            try:
                driver = User.objects.get(id=driver_id)
                vehicle = Vehicle.objects.get(id=vehicle_id)
                
                # Update trip fields
                trip.driver = driver
                trip.vehicle = vehicle
                trip.origin = request.POST.get('origin', trip.origin)
                trip.destination = request.POST.get('destination', trip.destination)
                trip.purpose = request.POST.get('purpose', trip.purpose)
                trip.notes = request.POST.get('notes', trip.notes)
                trip.status = request.POST.get('status', trip.status)
                
                # Handle datetime fields
                start_time = request.POST.get('start_time')
                if start_time:
                    from django.utils.dateparse import parse_datetime
                    trip.start_time = parse_datetime(start_time)
                
                end_time = request.POST.get('end_time')
                if end_time:
                    trip.end_time = parse_datetime(end_time)
                
                # Handle odometer fields
                start_odometer = request.POST.get('start_odometer')
                if start_odometer:
                    trip.start_odometer = int(start_odometer)
                
                end_odometer = request.POST.get('end_odometer')
                if end_odometer:
                    trip.end_odometer = int(end_odometer)
                
                trip.save()
                messages.success(request, 'Trip updated successfully!')
                return redirect('trip_detail', pk=trip.pk)
                
            except Exception as e:
                messages.error(request, f'Error updating trip: {str(e)}')
        else:
            messages.error(request, 'Driver and Vehicle are required.')
    
    # Get all users (adjust this based on how you identify drivers in your system)
    drivers = User.objects.all()
    
    # Get all vehicles (since your Vehicle model doesn't have is_active field)
    # You can filter by status if needed, like: Vehicle.objects.filter(status='active')
    vehicles = Vehicle.objects.all()
    
    # If you want to filter vehicles by status, uncomment one of these:
    # vehicles = Vehicle.objects.filter(status='active')  # if your status values are lowercase
    # vehicles = Vehicle.objects.filter(status='Active')  # if your status values are capitalized
    # vehicles = Vehicle.objects.filter(status='available')  # if you use 'available' instead
    
    context = {
        'trip': trip,
        'drivers': drivers,
        'vehicles': vehicles
    }
    
    return render(request, 'trips/trip_edit.html', context)

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
    
    # Get vehicles with proper filtering based on your status field
    # Check what status values you have in your database first
    vehicles = Vehicle.objects.all()
    
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
    
    if request.method == 'DELETE' or request.method == 'POST':
        trip.delete()
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'status': 'success'})
        messages.success(request, 'Trip deleted successfully!')
        return redirect('trip_list')
    
    return JsonResponse({'status': 'error'})

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
    
    # Build queryset
    queryset = Trip.objects.all().select_related('vehicle', 'driver').order_by('-start_time')
    
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
        if search:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search) |
                Q(driver__first_name__icontains=search) |
                Q(driver__last_name__icontains=search) |
                Q(origin__icontains=search) |
                Q(destination__icontains=search)
            )
    
    # Log the query count for debugging
    logger.info(f"Manual export query returned {queryset.count()} trips for date range {date_from} to {date_to}")
    
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
    """Export trips to CSV format"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename=\"manual_trips_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv\"'
    
    writer = csv.writer(response)
    
    # Build headers
    headers = ['Trip ID', 'Origin', 'Destination', 'Start Date', 'Start Time', 'End Date', 'End Time', 
               'Start Odometer', 'End Odometer', 'Distance (km)', 'Status', 'Purpose']
    
    if include_driver:
        headers.extend(['Driver Name', 'Driver Email'])
    if include_vehicle:
        headers.extend(['Vehicle License Plate', 'Vehicle Make', 'Vehicle Model'])
    if include_notes:
        headers.append('Notes')
    
    writer.writerow(headers)
    
    # Write data rows
    for trip in queryset:
        row = [
            trip.id,
            trip.origin,
            trip.destination,
            trip.start_time.date().strftime('%Y-%m-%d') if trip.start_time else '',
            trip.start_time.time().strftime('%H:%M') if trip.start_time else '',
            trip.end_time.date().strftime('%Y-%m-%d') if trip.end_time else '',
            trip.end_time.time().strftime('%H:%M') if trip.end_time else '',
            trip.start_odometer,
            trip.end_odometer or '',
            trip.distance_traveled() if trip.end_odometer and trip.start_odometer else '',
            trip.status.title(),
            trip.purpose,
        ]
        
        if include_driver:
            row.extend([trip.driver.get_full_name(), trip.driver.email])
        if include_vehicle:
            row.extend([trip.vehicle.license_plate, trip.vehicle.make, trip.vehicle.model])
        if include_notes:
            row.append(trip.notes or '')
        
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
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
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
        headers.extend(['Vehicle License Plate', 'Vehicle Make', 'Vehicle Model'])
    if include_notes:
        headers.append('Notes')
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # Write data
    for row_num, trip in enumerate(queryset, 1):
        col = 0
        
        # Basic trip data
        worksheet.write(row_num, col, trip.id, cell_format)
        col += 1
        worksheet.write(row_num, col, trip.origin, cell_format)
        col += 1
        worksheet.write(row_num, col, trip.destination, cell_format)
        col += 1
        worksheet.write(row_num, col, trip.start_time.date() if trip.start_time else '', date_format)
        col += 1
        worksheet.write(row_num, col, trip.start_time.time() if trip.start_time else '', time_format)
        col += 1
        worksheet.write(row_num, col, trip.end_time.date() if trip.end_time else '', date_format)
        col += 1
        worksheet.write(row_num, col, trip.end_time.time() if trip.end_time else '', time_format)
        col += 1
        worksheet.write(row_num, col, trip.start_odometer, cell_format)
        col += 1
        worksheet.write(row_num, col, trip.end_odometer or '', cell_format)
        col += 1
        worksheet.write(row_num, col, trip.distance_traveled() if trip.end_odometer and trip.start_odometer else '', cell_format)
        col += 1
        worksheet.write(row_num, col, trip.status.title(), cell_format)
        col += 1
        worksheet.write(row_num, col, trip.purpose, cell_format)
        col += 1
        
        # Optional fields
        if include_driver:
            worksheet.write(row_num, col, trip.driver.get_full_name(), cell_format)
            col += 1
            worksheet.write(row_num, col, trip.driver.email, cell_format)
            col += 1
        if include_vehicle:
            worksheet.write(row_num, col, trip.vehicle.license_plate, cell_format)
            col += 1
            worksheet.write(row_num, col, trip.vehicle.make, cell_format)
            col += 1
            worksheet.write(row_num, col, trip.vehicle.model, cell_format)
            col += 1
        if include_notes:
            worksheet.write(row_num, col, trip.notes or '', cell_format)
    
    # Auto-adjust column widths
    worksheet.autofit()
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=\"manual_trips_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx\"'
    
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
    summary_text += f"Total trips: {queryset.count()}<br/>"
    summary = Paragraph(summary_text, styles['Normal'])
    elements.append(summary)
    elements.append(Spacer(1, 12))
    
    # Prepare table data
    headers = ['ID', 'Route', 'Date', 'Status', 'Distance']
    if include_driver:
        headers.append('Driver')
    if include_vehicle:
        headers.append('Vehicle')
    
    data = [headers]
    
    for trip in queryset:
        row = [
            str(trip.id),
            f"{trip.origin} → {trip.destination}",
            trip.start_time.strftime('%Y-%m-%d') if trip.start_time else 'N/A',
            trip.status.title(),
            f"{trip.distance_traveled()} km" if trip.end_odometer and trip.start_odometer else 'N/A'
        ]
        
        if include_driver:
            row.append(trip.driver.get_full_name())
        if include_vehicle:
            row.append(f"{trip.vehicle.license_plate}\n{trip.vehicle.make} {trip.vehicle.model}")
        
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
    
    # Build queryset based on user permissions
    if request.user.user_type == 'driver':
        queryset = Trip.objects.filter(driver=request.user)
    elif request.user.user_type in ['admin', 'manager', 'vehicle_manager']:
        queryset = Trip.objects.all()
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
    
    if status:
        queryset = queryset.filter(status=status)
    
    # FIXED: Apply proper date filtering that matches active trips
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
            logger.warning(f"Invalid date format in export: date_from={date_from}, date_to={date_to}")
            
    elif date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_from_start = timezone.make_aware(
                datetime.combine(date_from_obj, datetime.min.time())
            )
            
            # Get trips that were active on or after this date
            queryset = queryset.filter(
                Q(end_time__gte=date_from_start) | Q(end_time__isnull=True)
            )
            
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
    
    # Log the query count for debugging
    logger.info(f"Export query returned {queryset.count()} trips for date range {date_from} to {date_to}")
    
    # Generate export based on format
    if export_format == 'csv':
        return export_trips_csv(queryset, include_notes, include_driver, include_vehicle)
    elif export_format == 'excel':
        return export_trips_excel(queryset, include_notes, include_driver, include_vehicle)
    elif export_format == 'pdf':
        return export_trips_pdf(queryset, include_notes, include_driver, include_vehicle)
    else:
        return HttpResponse('Invalid format', status=400)