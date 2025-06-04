# reports/views.py
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, FloatField, Q
from django.db.models.functions import TruncMonth, TruncYear, Coalesce
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin
from vehicles.models import Vehicle, VehicleType
from trips.models import Trip
from maintenance.models import Maintenance
from fuel.models import FuelTransaction
from accidents.models import Accident
from accounts.models import CustomUser
import csv
from datetime import datetime, timedelta
import io

# Conditional import of xlsxwriter
try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

class ReportBaseView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Base class for all report views with common functionality."""
    
    def get(self, request, *args, **kwargs):
        # Check if export is requested
        if 'export' in request.GET:
            context = self.get_context_data(**kwargs)
            export_format = request.GET.get('export')
            
            if hasattr(self, 'get_export_data'):
                data, filename, headers = self.get_export_data(context)
                
                if export_format == 'excel':
                    return self.export_as_excel(data, filename, headers)
                elif export_format == 'csv':
                    return self.export_as_csv(data, filename, headers)
        
        return super().get(request, *args, **kwargs)
    
    def get_date_range_filters(self):
        """Get date range filters from the request."""
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not start_date:
            start_date = (timezone.now().date() - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = timezone.now().date().isoformat()
            
        return start_date, end_date
    
    def export_as_csv(self, data, filename, headers):
        """Export data as CSV file."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(headers)
        
        for row in data:
            writer.writerow([row.get(header.lower().replace(' ', '_'), '') for header in headers])
            
        return response
    
    def export_as_excel(self, data, filename, headers):
        """Export data as Excel file."""
        # Check if xlsxwriter is available
        if not XLSX_AVAILABLE:
            # Fallback to CSV if xlsxwriter is not available
            return self.export_as_csv(data, filename, headers)
            
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet()
        
        # Add headers
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header)
            
        # Add data
        for row_num, row in enumerate(data, 1):
            for col_num, header in enumerate(headers):
                field_name = header.lower().replace(' ', '_')
                value = row.get(field_name, '')
                worksheet.write(row_num, col_num, value)
        
        workbook.close()
        buffer.seek(0)
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response


class VehicleReportView(ReportBaseView):
    template_name = 'reports/vehicle_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = self.get_date_range_filters()
        
        # Convert to datetime objects with timezone awareness
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
        
        # Filter by vehicle type
        vehicle_type = self.request.GET.get('vehicle_type')
        
        vehicles = Vehicle.objects.all()
        if vehicle_type:
            vehicles = vehicles.filter(vehicle_type_id=vehicle_type)
        
        # Get ALL trips with timezone-aware filtering
        all_trips = Trip.objects.filter(
            start_time__gte=start_datetime,
            start_time__lte=end_datetime,
            start_odometer__isnull=False,
        ).select_related('vehicle')
        
        # Calculate trip data for each vehicle
        vehicle_trip_data = {}
        for trip in all_trips:
            vehicle_id = trip.vehicle.id
            
            if vehicle_id not in vehicle_trip_data:
                vehicle_trip_data[vehicle_id] = {
                    'trip_count': 0,
                    'completed_trip_count': 0,
                    'ongoing_trip_count': 0,
                    'total_distance': 0,
                    'distances': []
                }
            
            # Count all trips
            vehicle_trip_data[vehicle_id]['trip_count'] += 1
            
            # Count by status
            if trip.status == 'completed':
                vehicle_trip_data[vehicle_id]['completed_trip_count'] += 1
            elif trip.status == 'ongoing':
                vehicle_trip_data[vehicle_id]['ongoing_trip_count'] += 1
            
            # Calculate distance - Fixed logic for distance calculation
            if trip.start_odometer is not None:
                try:
                    start_odo = float(trip.start_odometer)
                    
                    # For completed trips with end odometer
                    if trip.end_odometer is not None and trip.status == 'completed':
                        end_odo = float(trip.end_odometer)
                        distance = end_odo - start_odo
                        
                        if distance >= 0:  # Allow zero distance trips
                            vehicle_trip_data[vehicle_id]['total_distance'] += distance
                            vehicle_trip_data[vehicle_id]['distances'].append(distance)
                    
                except (ValueError, TypeError) as e:
                    pass
        
        # Get fuel data with timezone-aware filtering
        fuel_transactions = FuelTransaction.objects.filter(
            date__gte=start_date_obj,
            date__lte=end_date_obj
        ).select_related('vehicle')
        
        fuel_data_dict = {}
        for transaction in fuel_transactions:
            vehicle_id = transaction.vehicle.id
            if vehicle_id not in fuel_data_dict:
                fuel_data_dict[vehicle_id] = {
                    'fuel_count': 0,
                    'total_fuel': 0,
                    'total_energy': 0,
                    'total_fuel_cost': 0
                }
            
            fuel_data_dict[vehicle_id]['fuel_count'] += 1
            fuel_data_dict[vehicle_id]['total_fuel'] += float(transaction.quantity or 0)
            fuel_data_dict[vehicle_id]['total_energy'] += float(transaction.energy_consumed or 0)
            fuel_data_dict[vehicle_id]['total_fuel_cost'] += float(transaction.total_cost or 0)
        
        # Get maintenance data with timezone-aware filtering
        maintenance_records = Maintenance.objects.filter(
            date_reported__gte=start_date_obj,
            date_reported__lte=end_date_obj
        ).select_related('vehicle')
        
        maintenance_data_dict = {}
        for record in maintenance_records:
            vehicle_id = record.vehicle.id
            if vehicle_id not in maintenance_data_dict:
                maintenance_data_dict[vehicle_id] = {
                    'maintenance_count': 0,
                    'total_maintenance_cost': 0
                }
            
            maintenance_data_dict[vehicle_id]['maintenance_count'] += 1
            maintenance_data_dict[vehicle_id]['total_maintenance_cost'] += float(record.cost or 0)
        
        # Get accident data with timezone-aware filtering
        accident_records = Accident.objects.filter(
            date_time__gte=start_datetime,
            date_time__lte=end_datetime
        ).select_related('vehicle')
        
        accident_data_dict = {}
        for accident in accident_records:
            vehicle_id = accident.vehicle.id
            if vehicle_id not in accident_data_dict:
                accident_data_dict[vehicle_id] = {'accident_count': 0}
            accident_data_dict[vehicle_id]['accident_count'] += 1
        
        # Combine data for all vehicles
        vehicle_report = []
        
        for vehicle in vehicles:
            vehicle_id = vehicle.id
            
            trip_info = vehicle_trip_data.get(vehicle_id, {
                'trip_count': 0,
                'completed_trip_count': 0,
                'ongoing_trip_count': 0,
                'total_distance': 0,
                'distances': []
            })
            
            fuel_info = fuel_data_dict.get(vehicle_id, {
                'fuel_count': 0,
                'total_fuel': 0,
                'total_energy': 0,
                'total_fuel_cost': 0
            })
            
            maintenance_info = maintenance_data_dict.get(vehicle_id, {
                'maintenance_count': 0,
                'total_maintenance_cost': 0
            })
            
            accident_info = accident_data_dict.get(vehicle_id, {
                'accident_count': 0
            })
            
            # Calculate averages
            distances = trip_info.get('distances', [])
            avg_distance = sum(distances) / len(distances) if distances else 0
            
            # Calculate fuel efficiency
            fuel_efficiency = 0
            energy_efficiency = 0
            total_distance = trip_info.get('total_distance', 0)
            total_fuel = fuel_info.get('total_fuel', 0)
            total_energy = fuel_info.get('total_energy', 0)
            
            if total_distance > 0:
                if total_fuel > 0:
                    fuel_efficiency = total_distance / total_fuel
                if total_energy > 0:
                    energy_efficiency = total_distance / total_energy
            
            # Calculate cost per kilometer
            cost_per_km = 0
            total_cost = fuel_info.get('total_fuel_cost', 0) + maintenance_info.get('total_maintenance_cost', 0)
            if total_distance > 0 and total_cost > 0:
                cost_per_km = total_cost / total_distance
            
            is_electric = total_energy > 0 and total_fuel == 0
            
            vehicle_data = {
                'id': vehicle_id,
                'license_plate': vehicle.license_plate,
                'make': vehicle.make,
                'model': vehicle.model,
                'vehicle_type': vehicle.vehicle_type.name if vehicle.vehicle_type else '',
                'status': vehicle.status,
                'trip_count': trip_info.get('trip_count', 0),
                'completed_trip_count': trip_info.get('completed_trip_count', 0),
                'ongoing_trip_count': trip_info.get('ongoing_trip_count', 0),
                'total_distance': round(total_distance, 1) if total_distance else 0,
                'avg_distance': round(avg_distance, 1) if avg_distance else 0,
                'fuel_count': fuel_info.get('fuel_count', 0),
                'total_fuel': round(total_fuel, 2) if total_fuel else 0,
                'total_energy': round(total_energy, 2) if total_energy else 0,
                'total_fuel_cost': round(fuel_info.get('total_fuel_cost', 0), 2),
                'maintenance_count': maintenance_info.get('maintenance_count', 0),
                'total_maintenance_cost': round(maintenance_info.get('total_maintenance_cost', 0), 2),
                'accident_count': accident_info.get('accident_count', 0),
                'fuel_efficiency': round(fuel_efficiency, 2) if fuel_efficiency else 0,
                'energy_efficiency': round(energy_efficiency, 2) if energy_efficiency else 0,
                'cost_per_km': round(cost_per_km, 2) if cost_per_km else 0,
                'is_electric': is_electric
            }
            
            vehicle_report.append(vehicle_data)
        
        # Sort by trip count for better display
        vehicle_report.sort(key=lambda x: x['trip_count'], reverse=True)
        
        # FIXED: Get unique vehicle types properly
        # Instead of using the problematic query, get vehicle types from VehicleType model
        from vehicles.models import VehicleType
        vehicle_types = VehicleType.objects.all().values('id', 'name').order_by('name')
        
        context['vehicle_report'] = vehicle_report
        context['start_date'] = start_date
        context['end_date'] = end_date
        # FIXED: Use the proper vehicle types data
        context['vehicle_types'] = [
            {'vehicle_type__id': vt['id'], 'vehicle_type__name': vt['name']} 
            for vt in vehicle_types
        ]
        
        # Add debug info to context
        context['debug_info'] = {
            'total_trips_found': all_trips.count(),
            'vehicles_with_trips': len([v for v in vehicle_report if v['trip_count'] > 0]),
            'date_range': f"{start_date} to {end_date}",
            'timezone': str(timezone.get_current_timezone()),
            'filter_range': f"{start_datetime} to {end_datetime}"
        }
        
        return context
        
    def get_export_data(self, context):
        """Prepare data for export"""
        headers = [
            'License Plate', 'Make', 'Model', 'Vehicle Type', 'Status',
            'Trip Count', 'Completed Trips', 'Ongoing Trips', 'Total Distance (km)', 'Avg Trip Distance (km)',
            'Fuel Transactions', 'Total Fuel (L)', 'Total Energy (kWh)', 'Total Fuel Cost',
            'Maintenance Count', 'Total Maintenance Cost',
            'Accident Count', 'Fuel Efficiency (km/L)', 'Energy Efficiency (km/kWh)', 'Cost per km'
        ]
        
        filename = f"vehicle_report_{context['start_date']}_to_{context['end_date']}"
        
        return context['vehicle_report'], filename, headers


class DriverReportView(ReportBaseView):
    template_name = 'reports/driver_report.html'
    
    def get_date_range_filters(self):
        """Get date range filters from the request."""
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Default to last 90 days instead of 30 days to catch more data
        if not start_date:
            start_date = (timezone.now().date() - timedelta(days=90)).isoformat()
        if not end_date:
            end_date = timezone.now().date().isoformat()
            
        return start_date, end_date
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = self.get_date_range_filters()
        
        # Convert to datetime objects
        try:
            start_date_obj = datetime.fromisoformat(start_date).date()
            end_date_obj = datetime.fromisoformat(end_date).date()
        except ValueError:
            start_date_obj = timezone.now().date() - timedelta(days=90)
            end_date_obj = timezone.now().date()
            start_date = start_date_obj.isoformat()
            end_date = end_date_obj.isoformat()
        
        drivers = CustomUser.objects.filter(user_type='driver')
        
        # Get completed trips with drivers
        completed_trips = Trip.objects.filter(
            start_time__date__gte=start_date_obj,
            start_time__date__lte=end_date_obj,
            driver__isnull=False,
            end_time__isnull=False
        ).select_related('driver')
        
        # If no completed trips found, try with different status values
        if completed_trips.count() == 0:
            completed_trips = Trip.objects.filter(
                start_time__date__gte=start_date_obj,
                start_time__date__lte=end_date_obj,
                driver__isnull=False,
                end_time__isnull=False
            ).select_related('driver')
        
        # Calculate trip data manually
        driver_trip_data = {}
        
        for trip in completed_trips:
            driver_id = trip.driver.id
            
            if driver_id not in driver_trip_data:
                driver_trip_data[driver_id] = {
                    'trip_count': 0,
                    'total_distance': 0,
                    'distances': []
                }
            
            driver_trip_data[driver_id]['trip_count'] += 1
            
            if trip.start_odometer is not None and trip.end_odometer is not None:
                try:
                    start_odo = float(trip.start_odometer)
                    end_odo = float(trip.end_odometer)
                    distance = end_odo - start_odo
                    
                    if distance > 0:
                        driver_trip_data[driver_id]['total_distance'] += distance
                        driver_trip_data[driver_id]['distances'].append(distance)
                except (ValueError, TypeError):
                    pass
        
        # Calculate averages and create trip lookup
        trip_lookup = {}
        for driver_id, data in driver_trip_data.items():
            distances = data['distances']
            avg_distance = sum(distances) / len(distances) if distances else 0
            
            trip_lookup[driver_id] = {
                'trip_count': data['trip_count'],
                'total_distance': data['total_distance'],
                'avg_distance': avg_distance
            }
        
        # Get fuel data
        fuel_transactions = FuelTransaction.objects.filter(
            date__gte=start_date_obj,
            date__lte=end_date_obj,
            driver__isnull=False
        ).select_related('driver')
        
        fuel_data_dict = {}
        for transaction in fuel_transactions:
            driver_id = transaction.driver.id
            if driver_id not in fuel_data_dict:
                fuel_data_dict[driver_id] = {
                    'fuel_count': 0,
                    'total_fuel': 0,
                    'total_fuel_cost': 0
                }
            
            fuel_data_dict[driver_id]['fuel_count'] += 1
            fuel_data_dict[driver_id]['total_fuel'] += float(transaction.quantity or 0)
            fuel_data_dict[driver_id]['total_fuel_cost'] += float(transaction.total_cost or 0)
        
        fuel_lookup = {k: v for k, v in fuel_data_dict.items()}
        
        # Get accident data
        accident_transactions = Accident.objects.filter(
            date_time__date__gte=start_date_obj,
            date_time__date__lte=end_date_obj,
            driver__isnull=False
        ).select_related('driver')
        
        accident_data_dict = {}
        for accident in accident_transactions:
            driver_id = accident.driver.id
            if driver_id not in accident_data_dict:
                accident_data_dict[driver_id] = {'accident_count': 0}
            accident_data_dict[driver_id]['accident_count'] += 1
        
        accident_lookup = {k: v for k, v in accident_data_dict.items()}
        
        # Combine all data for report
        driver_report = []
        
        for driver in drivers:
            driver_id = driver.id
            
            trip_info = trip_lookup.get(driver_id, {
                'trip_count': 0,
                'total_distance': 0,
                'avg_distance': 0
            })
            
            fuel_info = fuel_lookup.get(driver_id, {
                'fuel_count': 0,
                'total_fuel': 0,
                'total_fuel_cost': 0
            })
            
            accident_info = accident_lookup.get(driver_id, {
                'accident_count': 0
            })
            
            trip_count = trip_info.get('trip_count') or 0
            total_distance = trip_info.get('total_distance') or 0
            avg_distance = trip_info.get('avg_distance') or 0
            
            accident_count = accident_info.get('accident_count') or 0
            accidents_per_1000km = (accident_count * 1000 / total_distance) if total_distance > 0 else 0
            
            driver_data = {
                'id': driver_id,
                'name': driver.get_full_name(),
                'username': driver.username,
                'license_number': driver.license_number or '',
                'license_expiry': driver.license_expiry,
                'trip_count': trip_count,
                'total_distance': round(total_distance, 1) if total_distance else 0,
                'avg_distance': round(avg_distance, 1) if avg_distance else 0,
                'total_hours': 0,
                'avg_speed': 0,
                'fuel_count': fuel_info.get('fuel_count') or 0,
                'total_fuel': fuel_info.get('total_fuel') or 0,
                'total_fuel_cost': fuel_info.get('total_fuel_cost') or 0,
                'accident_count': accident_count,
                'accidents_per_1000km': round(accidents_per_1000km, 2)
            }
            
            driver_report.append(driver_data)
        
        # Calculate totals for summary
        total_trips = sum(driver.get('trip_count', 0) for driver in driver_report)
        total_distance = sum(driver.get('total_distance', 0) for driver in driver_report)
        total_accidents = sum(driver.get('accident_count', 0) for driver in driver_report)
        
        context.update({
            'driver_report': driver_report,
            'start_date': start_date,
            'end_date': end_date,
            'total_trips': total_trips,
            'total_distance': round(total_distance, 1),
            'total_accidents': total_accidents,
            'total_hours': 0,
            'now': timezone.now()
        })
        
        return context
    
    def get_export_data(self, context):
        """Prepare data for export"""
        headers = [
            'Name', 'Username', 'License Number', 'License Expiry',
            'Trip Count', 'Total Distance (km)', 'Avg Trip Distance (km)',
            'Total Hours', 'Avg Speed (km/h)',
            'Fuel Transactions', 'Total Fuel (L)', 'Total Fuel Cost',
            'Accident Count', 'Accidents per 1000 km'
        ]
        
        filename = f"driver_report_{context['start_date']}_to_{context['end_date']}"
        
        return context['driver_report'], filename, headers


class MaintenanceReportView(ReportBaseView):
    template_name = 'reports/maintenance_report.html'
    
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
        
        # Get maintenance data
        maintenance_records = Maintenance.objects.filter(
            date_reported__gte=start_date_obj,
            date_reported__lte=end_date_obj
        ).select_related('vehicle', 'maintenance_type', 'provider', 'reported_by')
        
        # Apply filters
        maintenance_type = self.request.GET.get('maintenance_type')
        if maintenance_type:
            maintenance_records = maintenance_records.filter(maintenance_type_id=maintenance_type)
        
        status = self.request.GET.get('status')
        if status:
            maintenance_records = maintenance_records.filter(status=status)
        
        # Calculate summary data manually
        total_count = maintenance_records.count()
        total_cost = 0
        status_counts = {}
        type_costs = {}
        type_counts = {}
        
        for record in maintenance_records:
            if record.cost:
                total_cost += float(record.cost)
            
            status = record.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            
            type_name = record.maintenance_type.name if record.maintenance_type else 'Unknown'
            if type_name not in type_counts:
                type_counts[type_name] = 0
                type_costs[type_name] = 0
            
            type_counts[type_name] += 1
            if record.cost:
                type_costs[type_name] += float(record.cost)
        
        # Create status breakdown list
        status_breakdown = []
        for status, count in status_counts.items():
            status_breakdown.append({'status': status, 'count': count})
        
        # Create type breakdown list
        type_breakdown = []
        for type_name in type_counts.keys():
            type_breakdown.append({
                'maintenance_type__name': type_name,
                'count': type_counts[type_name],
                'total_cost': type_costs[type_name]
            })
        
        # Calculate monthly data manually
        monthly_data = []
        monthly_counts = {}
        monthly_costs = {}
        
        for record in maintenance_records:
            month_key = record.date_reported.strftime('%Y-%m')
            
            if month_key not in monthly_counts:
                monthly_counts[month_key] = 0
                monthly_costs[month_key] = 0
            
            monthly_counts[month_key] += 1
            if record.cost:
                monthly_costs[month_key] += float(record.cost)
        
        for month_key in sorted(monthly_counts.keys()):
            month_obj = datetime.strptime(month_key, '%Y-%m').date()
            monthly_data.append({
                'month': month_obj,
                'count': monthly_counts[month_key],
                'total_cost': monthly_costs[month_key]
            })
        
        # Create vehicle breakdown
        vehicle_breakdown = []
        vehicle_counts = {}
        vehicle_costs = {}
        
        for record in maintenance_records:
            vehicle_key = f"{record.vehicle.license_plate} ({record.vehicle.make} {record.vehicle.model})"
            
            if vehicle_key not in vehicle_counts:
                vehicle_counts[vehicle_key] = 0
                vehicle_costs[vehicle_key] = 0
            
            vehicle_counts[vehicle_key] += 1
            if record.cost:
                vehicle_costs[vehicle_key] += float(record.cost)
        
        for vehicle_key in vehicle_counts.keys():
            parts = vehicle_key.split(' (')
            license_plate = parts[0]
            make_model = parts[1].rstrip(')')
            make, model = make_model.split(' ', 1) if ' ' in make_model else (make_model, '')
            
            vehicle_breakdown.append({
                'vehicle__license_plate': license_plate,
                'vehicle__make': make,
                'vehicle__model': model,
                'count': vehicle_counts[vehicle_key],
                'total_cost': vehicle_costs[vehicle_key]
            })
        
        vehicle_breakdown.sort(key=lambda x: x['count'], reverse=True)
        
        summary = {
            'total_count': total_count,
            'total_cost': total_cost,
            'status_breakdown': status_breakdown,
            'type_breakdown': type_breakdown,
            'vehicle_breakdown': vehicle_breakdown
        }
        
        # Prepare detailed report data
        maintenance_report = []
        for record in maintenance_records.order_by('-date_reported'):
            maintenance_report.append({
                'id': record.id,
                'vehicle': f"{record.vehicle.license_plate} ({record.vehicle.make} {record.vehicle.model})",
                'maintenance_type': record.maintenance_type.name if record.maintenance_type else 'Unknown',
                'provider': record.provider.name if record.provider else 'N/A',
                'date_reported': record.date_reported,
                'odometer_reading': record.odometer_reading,
                'status': record.status,
                'scheduled_date': record.scheduled_date,
                'completion_date': record.completion_date,
                'cost': record.cost or 0,
                'reported_by': record.reported_by.get_full_name() if record.reported_by else 'N/A'
            })
        
        # Get filter options
        maintenance_types = []
        for record in maintenance_records:
            if record.maintenance_type:
                type_info = {
                    'maintenance_type__id': record.maintenance_type.id,
                    'maintenance_type__name': record.maintenance_type.name
                }
                if type_info not in maintenance_types:
                    maintenance_types.append(type_info)
        
        status_choices = {
            'scheduled': 'Scheduled',
            'in_progress': 'In Progress',
            'completed': 'Completed',
            'cancelled': 'Cancelled'
        }
        
        context.update({
            'maintenance_report': maintenance_report,
            'summary': summary,
            'monthly_data': monthly_data,
            'start_date': start_date,
            'end_date': end_date,
            'maintenance_types': maintenance_types,
            'statuses': status_choices
        })
        
        return context
    
    def get_export_data(self, context):
        """Prepare data for export"""
        headers = [
            'Vehicle', 'Maintenance Type', 'Provider', 'Date Reported', 
            'Odometer Reading', 'Status', 'Scheduled Date', 'Completion Date', 
            'Cost (₹)', 'Reported By'
        ]
        
        export_data = []
        for record in context['maintenance_report']:
            export_data.append({
                'vehicle': record['vehicle'],
                'maintenance_type': record['maintenance_type'],
                'provider': record['provider'],
                'date_reported': record['date_reported'].strftime('%Y-%m-%d') if record['date_reported'] else '',
                'odometer_reading': record['odometer_reading'] or '',
                'status': record['status'].title() if record.get('status') else '',
                'scheduled_date': record['scheduled_date'].strftime('%Y-%m-%d') if record['scheduled_date'] else '',
                'completion_date': record['completion_date'].strftime('%Y-%m-%d') if record['completion_date'] else '',
                'cost_(₹)': record['cost'] or 0,
                'reported_by': record['reported_by']
            })
        
        filename = f"maintenance_report_{context['start_date']}_to_{context['end_date']}"
        
        return export_data, filename, headers


class FuelReportView(ReportBaseView):
    template_name = 'reports/fuel_report.html'
    
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
        
        # Get all fuel/energy transactions
        fuel_transactions = FuelTransaction.objects.filter(
            date__gte=start_date_obj,
            date__lte=end_date_obj
        ).select_related('vehicle', 'driver', 'fuel_station')
        
        # Filter by vehicle
        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id:
            fuel_transactions = fuel_transactions.filter(vehicle_id=vehicle_id)
        
        # Filter by fuel type
        fuel_type = self.request.GET.get('fuel_type')
        if fuel_type:
            fuel_transactions = fuel_transactions.filter(fuel_type=fuel_type)
        
        # Separate fuel and electric transactions
        fuel_only_transactions = fuel_transactions.exclude(fuel_type='Electric')
        electric_transactions = fuel_transactions.filter(fuel_type='Electric')
        
        # Summary data for fuel transactions
        fuel_summary = {
            'total_count': fuel_only_transactions.count(),
            'total_quantity': fuel_only_transactions.aggregate(Sum('quantity'))['quantity__sum'] or 0,
            'total_cost': fuel_only_transactions.aggregate(Sum('total_cost'))['total_cost__sum'] or 0,
            'avg_cost_per_liter': fuel_only_transactions.aggregate(
                avg=Avg('cost_per_liter')
            )['avg'] or 0,
        }
        
        # Summary data for electric transactions
        electric_summary = {
            'total_count': electric_transactions.count(),
            'total_energy': electric_transactions.aggregate(Sum('energy_consumed'))['energy_consumed__sum'] or 0,
            'total_cost': electric_transactions.aggregate(Sum('total_cost'))['total_cost__sum'] or 0,
            'avg_cost_per_kwh': electric_transactions.aggregate(
                avg=Avg('cost_per_kwh')
            )['avg'] or 0,
            'avg_charging_duration': electric_transactions.aggregate(
                avg=Avg('charging_duration_minutes')
            )['avg'] or 0,
        }
        
        # Combined summary
        summary = {
            'total_count': fuel_transactions.count(),
            'total_quantity': fuel_summary['total_quantity'],
            'total_energy': electric_summary['total_energy'],
            'total_cost': fuel_summary['total_cost'] + electric_summary['total_cost'],
            'avg_cost_per_liter': fuel_summary['avg_cost_per_liter'],
            'avg_cost_per_kwh': electric_summary['avg_cost_per_kwh'],
            'fuel_transaction_count': fuel_summary['total_count'],
            'electric_transaction_count': electric_summary['total_count'],
            'fuel_cost': fuel_summary['total_cost'],
            'electric_cost': electric_summary['total_cost'],
            'avg_charging_duration': electric_summary['avg_charging_duration'],
            
            # Fuel type breakdown
            'fuel_type_breakdown': fuel_transactions.values('fuel_type').annotate(
                count=Count('id'),
                total_quantity=Sum('quantity'),
                total_energy=Sum('energy_consumed'),
                total_cost=Sum('total_cost'),
                avg_cost_per_liter=Avg('cost_per_liter'),
                avg_cost_per_kwh=Avg('cost_per_kwh'),
                avg_charging_duration=Avg('charging_duration_minutes')
            ),
            
            # Station breakdown
            'station_breakdown': fuel_transactions.values('fuel_station__name').annotate(
                count=Count('id'),
                total_quantity=Sum('quantity'),
                total_energy=Sum('energy_consumed'),
                total_cost=Sum('total_cost'),
                avg_cost_per_liter=Avg('cost_per_liter'),
                avg_cost_per_kwh=Avg('cost_per_kwh')
            ),
            
            # Vehicle breakdown
            'vehicle_breakdown': fuel_transactions.values(
                'vehicle__id', 'vehicle__license_plate', 'vehicle__make', 'vehicle__model'
            ).annotate(
                count=Count('id'),
                total_quantity=Sum('quantity'),
                total_energy=Sum('energy_consumed'),
                total_cost=Sum('total_cost'),
                fuel_transactions=Count('id', filter=Q(fuel_type__isnull=False) & ~Q(fuel_type='Electric')),
                electric_transactions=Count('id', filter=Q(fuel_type='Electric'))
            ).order_by('-total_cost')
        }
        
        # Monthly breakdown
        monthly_data = fuel_transactions.annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity'),
            total_energy=Sum('energy_consumed'),
            total_cost=Sum('total_cost'),
            avg_cost_per_liter=Avg('cost_per_liter'),
            avg_cost_per_kwh=Avg('cost_per_kwh'),
            fuel_count=Count('id', filter=~Q(fuel_type='Electric')),
            electric_count=Count('id', filter=Q(fuel_type='Electric'))
        ).order_by('month')
        
        # Calculate efficiency for each vehicle
        trips_in_period = Trip.objects.filter(
            start_time__date__gte=start_date_obj,
            end_time__date__lte=end_date_obj,
            status='completed'
        ).values('vehicle').annotate(
            total_distance=Sum(F('end_odometer') - F('start_odometer'))
        )
        
        # Create a lookup for trip distances
        trip_distances = {item['vehicle']: item['total_distance'] for item in trips_in_period}
        
        # Calculate efficiency for each vehicle
        vehicle_efficiency = []
        for vehicle in summary['vehicle_breakdown']:
            vehicle_id = vehicle['vehicle__id']
            distance = trip_distances.get(vehicle_id, 0)
            fuel_quantity = vehicle['total_quantity'] or 0
            energy_consumed = vehicle['total_energy'] or 0
            
            vehicle_data = {
                'vehicle': f"{vehicle['vehicle__license_plate']} ({vehicle['vehicle__make']} {vehicle['vehicle__model']})",
                'distance': distance,
                'fuel': fuel_quantity,
                'energy': energy_consumed,
                'fuel_transactions': vehicle['fuel_transactions'],
                'electric_transactions': vehicle['electric_transactions'],
                'total_cost': vehicle['total_cost']
            }
            
            # Calculate fuel efficiency if applicable
            if fuel_quantity > 0 and distance > 0:
                vehicle_data['fuel_efficiency'] = round(distance / fuel_quantity, 2)
            else:
                vehicle_data['fuel_efficiency'] = 0
            
            # Calculate energy efficiency if applicable
            if energy_consumed > 0 and distance > 0:
                vehicle_data['energy_efficiency'] = round(distance / energy_consumed, 2)
            else:
                vehicle_data['energy_efficiency'] = 0
            
            # Determine vehicle type based on transactions
            if vehicle['electric_transactions'] > 0 and vehicle['fuel_transactions'] > 0:
                vehicle_data['vehicle_type'] = 'Hybrid'
            elif vehicle['electric_transactions'] > 0:
                vehicle_data['vehicle_type'] = 'Electric'
            else:
                vehicle_data['vehicle_type'] = 'Fuel'
            
            vehicle_efficiency.append(vehicle_data)
        
        # Prepare data for detailed report
        fuel_report = []
        for transaction in fuel_transactions:
            fuel_report.append({
                'id': transaction.id,
                'date': transaction.date,
                'vehicle': f"{transaction.vehicle.license_plate} ({transaction.vehicle.make} {transaction.vehicle.model})",
                'driver': transaction.driver.get_full_name() if transaction.driver else 'N/A',
                'fuel_station': transaction.fuel_station.name if transaction.fuel_station else 'N/A',
                'fuel_type': transaction.fuel_type,
                'quantity': transaction.quantity,
                'energy_consumed': transaction.energy_consumed,
                'cost_per_liter': transaction.cost_per_liter,
                'cost_per_kwh': transaction.cost_per_kwh,
                'charging_duration_minutes': transaction.charging_duration_minutes,
                'total_cost': transaction.total_cost,
                'odometer_reading': transaction.odometer_reading,
                'is_electric': transaction.fuel_type == 'Electric'
            })
        
        # Station type analysis
        station_type_analysis = {}
        if fuel_transactions.exists():
            stations_with_data = fuel_transactions.values('fuel_station__station_type', 'fuel_station__name').annotate(
                transaction_count=Count('id'),
                fuel_transactions=Count('id', filter=~Q(fuel_type='Electric')),
                electric_transactions=Count('id', filter=Q(fuel_type='Electric')),
                total_revenue=Sum('total_cost')
            )
            
            for station in stations_with_data:
                station_type = station['fuel_station__station_type'] or 'fuel'
                if station_type not in station_type_analysis:
                    station_type_analysis[station_type] = {
                        'count': 0,
                        'transactions': 0,
                        'fuel_transactions': 0,
                        'electric_transactions': 0,
                        'revenue': 0
                    }
                
                station_type_analysis[station_type]['count'] += 1
                station_type_analysis[station_type]['transactions'] += station['transaction_count']
                station_type_analysis[station_type]['fuel_transactions'] += station['fuel_transactions']
                station_type_analysis[station_type]['electric_transactions'] += station['electric_transactions']
                station_type_analysis[station_type]['revenue'] += station['total_revenue'] or 0
        
        context['fuel_report'] = fuel_report
        context['summary'] = summary
        context['monthly_data'] = monthly_data
        context['vehicle_efficiency'] = vehicle_efficiency
        context['station_type_analysis'] = station_type_analysis
        context['start_date'] = start_date
        context['end_date'] = end_date
        context['vehicles'] = Vehicle.objects.all()
        context['fuel_types'] = FuelTransaction.objects.values_list('fuel_type', flat=True).distinct()
        
        return context
    
    def get_export_data(self, context):
        """Prepare data for export"""
        headers = [
            'Date', 'Vehicle', 'Driver', 'Fuel Station', 'Fuel Type',
            'Quantity (L)', 'Energy (kWh)', 'Cost per Liter', 'Cost per kWh',
            'Charging Duration (min)', 'Total Cost', 'Odometer Reading', 'Type'
        ]
        
        # Transform data for export
        export_data = []
        for transaction in context['fuel_report']:
            export_data.append({
                'date': transaction['date'].strftime('%Y-%m-%d') if transaction['date'] else '',
                'vehicle': transaction['vehicle'],
                'driver': transaction['driver'],
                'fuel_station': transaction['fuel_station'],
                'fuel_type': transaction['fuel_type'] or '',
                'quantity_(l)': transaction['quantity'] or 0,
                'energy_(kwh)': transaction['energy_consumed'] or 0,
                'cost_per_liter': transaction['cost_per_liter'] or 0,
                'cost_per_kwh': transaction['cost_per_kwh'] or 0,
                'charging_duration_(min)': transaction['charging_duration_minutes'] or 0,
                'total_cost': transaction['total_cost'] or 0,
                'odometer_reading': transaction['odometer_reading'] or 0,
                'type': 'Electric' if transaction['is_electric'] else 'Fuel'
            })
        
        filename = f"fuel_energy_report_{context['start_date']}_to_{context['end_date']}"
        
        return export_data, filename, headers
