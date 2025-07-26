from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, F, ExpressionWrapper, FloatField, Q
from django.utils import timezone
from django.http import HttpResponse
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin
from trips.models import Trip
from trips.consultant_models import ConsultantRate
from accounts.models import CustomUser
from vehicles.models import Vehicle
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import csv
from datetime import datetime, timedelta
import io

# Conditional import of xlsxwriter
try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

from .views import ReportBaseView

class ConsultantReportView(ReportBaseView):
    """
    View for generating reports on consultant drivers and their payments.
    """
    template_name = 'reports/consultant_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = self.get_date_range_filters()
        
        # Convert to datetime objects
        try:
            start_date_obj = datetime.fromisoformat(start_date).date()
            end_date_obj = datetime.fromisoformat(end_date).date()
        except ValueError:
            start_date_obj = timezone.now().date() - timedelta(days=30)
            end_date_obj = timezone.now().date()
            start_date = start_date_obj.isoformat()
            end_date = end_date_obj.isoformat()
        
        # Create timezone-aware datetime objects for filtering
        start_datetime = timezone.make_aware(
            datetime.combine(start_date_obj, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date_obj, datetime.max.time())
        )
        
        # Get all consultant rates that are active
        active_consultant_rates = ConsultantRate.objects.filter(
            status='active'
        ).select_related('driver', 'vehicle')
        
        # Get all drivers who have consultant rates
        consultant_drivers = CustomUser.objects.filter(
            consultant_rates__status='active'
        ).distinct()
        
        # Filter by driver if specified
        driver_id = self.request.GET.get('driver')
        if driver_id:
            consultant_drivers = consultant_drivers.filter(id=driver_id)
            active_consultant_rates = active_consultant_rates.filter(driver_id=driver_id)
        
        # Filter by vehicle if specified
        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id:
            active_consultant_rates = active_consultant_rates.filter(vehicle_id=vehicle_id)
        
        # Get all completed trips for these drivers within date range
        trips = Trip.objects.filter(
            driver__in=consultant_drivers,
            status='completed',
            start_time__gte=start_datetime,
            end_time__lte=end_datetime
        ).select_related('driver', 'vehicle')
        
        # Create a lookup dictionary for consultant rates
        rate_lookup = {}
        for rate in active_consultant_rates:
            key = f"{rate.driver_id}_{rate.vehicle_id}"
            rate_lookup[key] = rate
        
        # Process trip data and calculate payments
        consultant_report = []
        
        for trip in trips:
            # Check if this driver-vehicle combination has a consultant rate
            rate_key = f"{trip.driver_id}_{trip.vehicle_id}"
            consultant_rate = rate_lookup.get(rate_key)
            
            if consultant_rate:
                distance = trip.distance_traveled()
                payment = consultant_rate.calculate_payment(distance)
                
                consultant_report.append({
                    'trip_id': trip.id,
                    'driver_id': trip.driver.id,
                    'driver_name': trip.driver.get_full_name(),
                    'vehicle_id': trip.vehicle.id,
                    'vehicle': f"{trip.vehicle.license_plate} ({trip.vehicle.make} {trip.vehicle.model})",
                    'start_time': trip.start_time,
                    'end_time': trip.end_time,
                    'origin': trip.origin,
                    'destination': trip.destination,
                    'distance': distance,
                    'rate_per_km': float(consultant_rate.rate_per_km),
                    'payment': payment,
                    'duration': trip.duration(),
                    'purpose': trip.purpose,
                    'notes': trip.notes
                })
        
        # Sort by date (most recent first)
        consultant_report.sort(key=lambda x: x['end_time'], reverse=True)
        
        # Calculate summary statistics
        total_trips = len(consultant_report)
        total_distance = sum(trip['distance'] for trip in consultant_report)
        total_payment = sum(trip['payment'] for trip in consultant_report)
        
        # Group by driver for driver summary
        driver_summary = {}
        for trip in consultant_report:
            driver_id = trip['driver_id']
            if driver_id not in driver_summary:
                driver_summary[driver_id] = {
                    'driver_name': trip['driver_name'],
                    'trip_count': 0,
                    'total_distance': 0,
                    'total_payment': 0
                }
            
            driver_summary[driver_id]['trip_count'] += 1
            driver_summary[driver_id]['total_distance'] += trip['distance']
            driver_summary[driver_id]['total_payment'] += trip['payment']
        
        # Convert to list and sort by total payment
        driver_summary_list = list(driver_summary.values())
        driver_summary_list.sort(key=lambda x: x['total_payment'], reverse=True)
        
        # Group by vehicle for vehicle summary
        vehicle_summary = {}
        for trip in consultant_report:
            vehicle_id = trip['vehicle_id']
            if vehicle_id not in vehicle_summary:
                vehicle_summary[vehicle_id] = {
                    'vehicle': trip['vehicle'],
                    'trip_count': 0,
                    'total_distance': 0,
                    'total_payment': 0
                }
            
            vehicle_summary[vehicle_id]['trip_count'] += 1
            vehicle_summary[vehicle_id]['total_distance'] += trip['distance']
            vehicle_summary[vehicle_id]['total_payment'] += trip['payment']
        
        # Convert to list and sort by total payment
        vehicle_summary_list = list(vehicle_summary.values())
        vehicle_summary_list.sort(key=lambda x: x['total_payment'], reverse=True)
        
        # Pagination
        page = self.request.GET.get('page', 1)
        page_size = int(self.request.GET.get('page_size', 20))
        
        # Validate page_size
        if page_size not in [10, 20, 50, 100]:
            page_size = 20
        
        paginator = Paginator(consultant_report, page_size)
        
        try:
            consultant_report_page = paginator.page(page)
        except PageNotAnInteger:
            consultant_report_page = paginator.page(1)
        except EmptyPage:
            consultant_report_page = paginator.page(paginator.num_pages)
        
        context.update({
            'consultant_report': consultant_report,
            'consultant_report_page': consultant_report_page,
            'paginator': paginator,
            'total_trips': total_trips,
            'total_distance': total_distance,
            'total_payment': total_payment,
            'driver_summary': driver_summary_list,
            'vehicle_summary': vehicle_summary_list,
            'start_date': start_date,
            'end_date': end_date,
            'consultant_drivers': consultant_drivers,
            'vehicles': Vehicle.objects.filter(consultant_rates__status='active').distinct(),
            'page_size': page_size,
            'selected_driver': driver_id,
            'selected_vehicle': vehicle_id
        })
        
        return context
    
    def get_export_data(self, context):
        """Prepare data for export"""
        headers = [
            'Driver Name', 'Vehicle', 'Start Time', 'End Time', 
            'Origin', 'Destination', 'Distance (km)', 'Rate (₹/km)',
            'Payment (₹)', 'Duration', 'Purpose', 'Notes'
        ]
        
        filename = f"consultant_report_{context['start_date']}_to_{context['end_date']}"
        
        # Use all data, not just the current page
        export_data = []
        for trip in context['consultant_report']:
            export_data.append({
                'driver_name': trip['driver_name'],
                'vehicle': trip['vehicle'],
                'start_time': trip['start_time'].strftime('%Y-%m-%d %H:%M') if trip['start_time'] else '',
                'end_time': trip['end_time'].strftime('%Y-%m-%d %H:%M') if trip['end_time'] else '',
                'origin': trip['origin'],
                'destination': trip['destination'],
                'distance_(km)': trip['distance'],
                'rate_(₹/km)': trip['rate_per_km'],
                'payment_(₹)': trip['payment'],
                'duration': trip['duration'] or '',
                'purpose': trip['purpose'],
                'notes': trip['notes']
            })
        
        return export_data, filename, headers
