# Create this file: trips/management/commands/process_manual_trips.py

import os
import csv
import logging
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from trips.models import Trip
from vehicles.models import Vehicle
from accounts.models import CustomUser

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process manual trip data from CSV files and import into the system'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing trip data'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without making actual changes'
        )
        
        parser.add_argument(
            '--skip-errors',
            action='store_true',
            help='Skip rows with errors and continue processing'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of trips to process in each batch'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        skip_errors = options['skip_errors']
        batch_size = options['batch_size']
        
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file "{csv_file}" does not exist.')
        
        self.stdout.write(f"Processing manual trips from: {csv_file}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))
        
        try:
            result = self.process_csv_file(csv_file, dry_run, skip_errors, batch_size)
            
            self.stdout.write(self.style.SUCCESS(
                f"Processing complete! Created: {result['created']}, "
                f"Errors: {result['errors']}, Skipped: {result['skipped']}"
            ))
            
            if result['error_details']:
                self.stdout.write(self.style.ERROR("\nErrors encountered:"))
                for error in result['error_details']:
                    self.stdout.write(f"  - {error}")
                    
        except Exception as e:
            logger.error(f"Failed to process CSV file: {str(e)}")
            raise CommandError(f"Failed to process CSV file: {str(e)}")

    def process_csv_file(self, csv_file, dry_run=False, skip_errors=True, batch_size=100):
        """Process CSV file and create trips."""
        created_count = 0
        error_count = 0
        skipped_count = 0
        errors = []
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            # Detect CSV dialect
            sample = file.read(1024)
            file.seek(0)
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
            
            csv_reader = csv.DictReader(file, dialect=dialect)
            
            # Validate headers
            required_headers = {
                'Driver Email', 'Vehicle License Plate', 'Origin', 'Destination',
                'Start Date', 'Start Time', 'Start Odometer', 'Purpose'
            }
            
            headers = set(csv_reader.fieldnames)
            missing_headers = required_headers - headers
            
            if missing_headers:
                raise CommandError(f"Missing required headers: {', '.join(missing_headers)}")
            
            self.stdout.write(f"Found {len(headers)} columns in CSV file")
            self.stdout.write(f"Required headers: {', '.join(required_headers)}")
            
            trips_batch = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    trip_data = self.process_row(row, row_num)
                    if trip_data:
                        trips_batch.append(trip_data)
                        
                        # Process batch when it reaches batch_size
                        if len(trips_batch) >= batch_size:
                            batch_result = self.save_trips_batch(trips_batch, dry_run)
                            created_count += batch_result['created']
                            error_count += batch_result['errors']
                            errors.extend(batch_result['error_details'])
                            trips_batch = []
                            
                except Exception as e:
                    error_count += 1
                    error_msg = f"Row {row_num}: {str(e)}"
                    errors.append(error_msg)
                    
                    if skip_errors:
                        self.stdout.write(self.style.WARNING(f"Skipping row {row_num}: {str(e)}"))
                        skipped_count += 1
                        continue
                    else:
                        raise CommandError(error_msg)
            
            # Process remaining trips in batch
            if trips_batch:
                batch_result = self.save_trips_batch(trips_batch, dry_run)
                created_count += batch_result['created']
                error_count += batch_result['errors']
                errors.extend(batch_result['error_details'])
        
        return {
            'created': created_count,
            'errors': error_count,
            'skipped': skipped_count,
            'error_details': errors
        }

    def process_row(self, row, row_num):
        """Process a single CSV row and return trip data."""
        # Clean row data
        cleaned_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
        
        # Get driver by email
        driver_email = cleaned_row.get('Driver Email', '').strip().lower()
        if not driver_email:
            raise ValueError("Driver email is required")
        
        try:
            driver = CustomUser.objects.get(email__iexact=driver_email, user_type='driver')
        except CustomUser.DoesNotExist:
            raise ValueError(f"Driver with email {driver_email} not found")
        
        # Get vehicle by license plate
        license_plate = cleaned_row.get('Vehicle License Plate', '').strip().upper()
        if not license_plate:
            raise ValueError("Vehicle license plate is required")
        
        try:
            vehicle = Vehicle.objects.get(license_plate__iexact=license_plate)
        except Vehicle.DoesNotExist:
            raise ValueError(f"Vehicle with license plate {license_plate} not found")
        
        # Parse dates and times
        start_date = cleaned_row.get('Start Date', '').strip()
        start_time = cleaned_row.get('Start Time', '').strip()
        end_date = cleaned_row.get('End Date', '').strip()
        end_time = cleaned_row.get('End Time', '').strip()
        
        # Combine date and time
        start_datetime = self.parse_datetime(start_date, start_time)
        end_datetime = self.parse_datetime(end_date, end_time) if end_date and end_time else None
        
        # Get other fields
        origin = cleaned_row.get('Origin', '').strip()
        destination = cleaned_row.get('Destination', '').strip()
        start_odometer = self.parse_integer(cleaned_row.get('Start Odometer', ''))
        end_odometer = self.parse_integer(cleaned_row.get('End Odometer', '')) if cleaned_row.get('End Odometer') else None
        purpose = cleaned_row.get('Purpose', '').strip()
        notes = cleaned_row.get('Notes', '').strip()
        
        # Validate required fields
        if not all([origin, destination, purpose]):
            raise ValueError("Origin, destination, and purpose are required")
        
        if start_odometer is None:
            raise ValueError("Start odometer is required")
        
        # Validate odometer readings
        if end_odometer and end_odometer <= start_odometer:
            raise ValueError(f"End odometer ({end_odometer}) must be greater than start odometer ({start_odometer})")
        
        # Validate dates
        if end_datetime and end_datetime <= start_datetime:
            raise ValueError("End time must be after start time")
        
        # Determine status
        status = 'completed' if end_datetime and end_odometer else 'ongoing'
        
        return {
            'vehicle': vehicle,
            'driver': driver,
            'start_time': start_datetime,
            'end_time': end_datetime,
            'start_odometer': start_odometer,
            'end_odometer': end_odometer,
            'origin': origin,
            'destination': destination,
            'purpose': purpose,
            'notes': notes,
            'status': status,
            'row_num': row_num
        }

    def save_trips_batch(self, trips_batch, dry_run=False):
        """Save a batch of trips to the database."""
        created_count = 0
        error_count = 0
        errors = []
        
        if dry_run:
            self.stdout.write(f"DRY RUN: Would create {len(trips_batch)} trips")
            return {
                'created': len(trips_batch),
                'errors': 0,
                'error_details': []
            }
        
        for trip_data in trips_batch:
            try:
                with transaction.atomic():
                    # Create trip
                    trip = Trip.objects.create(
                        vehicle=trip_data['vehicle'],
                        driver=trip_data['driver'],
                        start_time=trip_data['start_time'],
                        end_time=trip_data['end_time'],
                        start_odometer=trip_data['start_odometer'],
                        end_odometer=trip_data['end_odometer'],
                        origin=trip_data['origin'],
                        destination=trip_data['destination'],
                        purpose=trip_data['purpose'],
                        notes=trip_data['notes'],
                        status=trip_data['status']
                    )
                    
                    # Update vehicle odometer if trip is completed
                    if trip.status == 'completed' and trip.end_odometer:
                        vehicle = trip.vehicle
                        if not vehicle.current_odometer or trip.end_odometer > vehicle.current_odometer:
                            vehicle.current_odometer = trip.end_odometer
                            vehicle.save()
                    
                    created_count += 1
                    
                    if created_count % 50 == 0:
                        self.stdout.write(f"Processed {created_count} trips...")
                        
            except Exception as e:
                error_count += 1
                error_msg = f"Row {trip_data['row_num']}: Failed to save trip - {str(e)}"
                errors.append(error_msg)
        
        return {
            'created': created_count,
            'errors': error_count,
            'error_details': errors
        }

    def parse_datetime(self, date_str, time_str):
        """Parse date and time strings into datetime object."""
        if not date_str:
            raise ValueError("Date is required")
        
        # Try different date formats
        date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']
        
        for date_format in date_formats:
            try:
                if time_str:
                    # Combine date and time
                    datetime_str = f"{date_str} {time_str}"
                    return timezone.make_aware(datetime.strptime(datetime_str, f"{date_format} %H:%M"))
                else:
                    # Date only
                    date_obj = datetime.strptime(date_str, date_format).date()
                    return timezone.make_aware(datetime.combine(date_obj, datetime.now().time()))
            except ValueError:
                continue
        
        raise ValueError(f"Invalid date format: {date_str}")

    def parse_integer(self, value):
        """Parse integer value from string."""
        if not value:
            return None
        
        try:
            # Remove any non-digit characters except decimal point
            cleaned_value = ''.join(c for c in str(value) if c.isdigit() or c == '.')
            return int(float(cleaned_value)) if cleaned_value else None
        except (ValueError, TypeError):
            raise ValueError(f"Invalid integer value: {value}")


# Additional utility command for data validation
class ValidateTripsCommand(BaseCommand):
    """Command to validate existing trip data."""
    help = 'Validate existing trip data for inconsistencies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Automatically fix issues where possible'
        )

    def handle(self, *args, **options):
        fix_issues = options['fix_issues']
        
        self.stdout.write("Validating trip data...")
        
        issues = []
        fixes_applied = 0
        
        # Check for trips without end times but with completed status
        invalid_completed = Trip.objects.filter(status='completed', end_time__isnull=True)
        if invalid_completed.exists():
            issue = f"Found {invalid_completed.count()} completed trips without end time"
            issues.append(issue)
            self.stdout.write(self.style.WARNING(issue))
            
            if fix_issues:
                for trip in invalid_completed:
                    if trip.start_time:
                        # Set end time to 1 hour after start time as estimate
                        trip.end_time = trip.start_time + timezone.timedelta(hours=1)
                        trip.save()
                        fixes_applied += 1
        
        # Check for invalid odometer readings
        invalid_odometer = Trip.objects.filter(
            end_odometer__isnull=False,
            start_odometer__isnull=False
        ).extra(where=["end_odometer <= start_odometer"])
        
        if invalid_odometer.exists():
            issue = f"Found {invalid_odometer.count()} trips with invalid odometer readings"
            issues.append(issue)
            self.stdout.write(self.style.ERROR(issue))
        
        # Check for vehicles with null current_odometer
        null_odometer_vehicles = Vehicle.objects.filter(current_odometer__isnull=True)
        if null_odometer_vehicles.exists():
            issue = f"Found {null_odometer_vehicles.count()} vehicles with null current_odometer"
            issues.append(issue)
            self.stdout.write(self.style.WARNING(issue))
            
            if fix_issues:
                for vehicle in null_odometer_vehicles:
                    # Set to 0 as default
                    vehicle.current_odometer = 0
                    vehicle.save()
                    fixes_applied += 1
        
        if not issues:
            self.stdout.write(self.style.SUCCESS("No data validation issues found!"))
        else:
            self.stdout.write(f"\nFound {len(issues)} issues")
            if fix_issues:
                self.stdout.write(self.style.SUCCESS(f"Applied {fixes_applied} fixes"))
        
        return issues