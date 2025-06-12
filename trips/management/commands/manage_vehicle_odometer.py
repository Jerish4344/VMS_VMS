# Create this file: trips/management/commands/manage_vehicle_odometers.py

from django.core.management.base import BaseCommand
from django.db import transaction
from trips.models import Trip
from vehicles.models import Vehicle
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Manage vehicle odometer readings with various update strategies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strategy',
            type=str,
            choices=['latest_by_date', 'highest_reading', 'manual_set'],
            default='latest_by_date',
            help='Strategy for updating odometer: latest_by_date (most recent trip), highest_reading (highest odometer), manual_set (set specific value)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without making actual changes'
        )
        
        parser.add_argument(
            '--vehicle-id',
            type=int,
            help='Update odometer for a specific vehicle only'
        )
        
        parser.add_argument(
            '--odometer-value',
            type=int,
            help='Manually set odometer to this value (use with --strategy=manual_set)'
        )

    def handle(self, *args, **options):
        strategy = options['strategy']
        dry_run = options['dry_run']
        vehicle_id = options.get('vehicle_id')
        odometer_value = options.get('odometer_value')
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        if strategy == 'manual_set' and not odometer_value:
            self.stdout.write(self.style.ERROR("--odometer-value is required when using --strategy=manual_set"))
            return
        
        if vehicle_id:
            vehicles = Vehicle.objects.filter(id=vehicle_id)
            if not vehicles.exists():
                self.stdout.write(self.style.ERROR(f"Vehicle with ID {vehicle_id} not found"))
                return
        else:
            vehicles = Vehicle.objects.all()
        
        self.stdout.write(f"Processing {vehicles.count()} vehicles using strategy: {strategy}")
        
        updated_count = 0
        unchanged_count = 0
        
        for vehicle in vehicles:
            if strategy == 'latest_by_date':
                result = self.update_by_latest_date(vehicle, dry_run)
            elif strategy == 'highest_reading':
                result = self.update_by_highest_reading(vehicle, dry_run)
            elif strategy == 'manual_set':
                result = self.manual_set_odometer(vehicle, odometer_value, dry_run)
            
            if result['changed']:
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Vehicle {vehicle.license_plate}: "
                        f"{result['old_odometer']} → {result['new_odometer']} km "
                        f"({result['reason']})"
                    )
                )
            else:
                unchanged_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Vehicle {vehicle.license_plate}: {result['reason']}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary: {updated_count} vehicles updated, {unchanged_count} unchanged"
            )
        )

    def update_by_latest_date(self, vehicle, dry_run=False):
        """Update odometer based on the most recent completed trip by date."""
        latest_trip = Trip.objects.filter(
            vehicle=vehicle,
            status='completed',
            end_time__isnull=False,
            end_odometer__isnull=False
        ).order_by('-end_time').first()
        
        if not latest_trip:
            return {
                'changed': False,
                'reason': 'No completed trips with valid end_time and end_odometer'
            }
        
        old_odometer = vehicle.current_odometer
        new_odometer = latest_trip.end_odometer
        
        if old_odometer == new_odometer:
            return {
                'changed': False,
                'reason': f'Already set to latest trip odometer: {old_odometer} km'
            }
        
        if not dry_run:
            with transaction.atomic():
                vehicle.current_odometer = new_odometer
                vehicle.save()
        
        return {
            'changed': True,
            'old_odometer': old_odometer,
            'new_odometer': new_odometer,
            'reason': f'Updated to latest trip on {latest_trip.end_time.strftime("%Y-%m-%d %H:%M")}'
        }

    def update_by_highest_reading(self, vehicle, dry_run=False):
        """Update odometer to the highest reading from all completed trips."""
        highest_trip = Trip.objects.filter(
            vehicle=vehicle,
            status='completed',
            end_odometer__isnull=False
        ).order_by('-end_odometer').first()
        
        if not highest_trip:
            return {
                'changed': False,
                'reason': 'No completed trips with valid end_odometer'
            }
        
        old_odometer = vehicle.current_odometer
        new_odometer = highest_trip.end_odometer
        
        if old_odometer == new_odometer:
            return {
                'changed': False,
                'reason': f'Already set to highest reading: {old_odometer} km'
            }
        
        if not dry_run:
            with transaction.atomic():
                vehicle.current_odometer = new_odometer
                vehicle.save()
        
        return {
            'changed': True,
            'old_odometer': old_odometer,
            'new_odometer': new_odometer,
            'reason': f'Updated to highest reading from trip on {highest_trip.end_time.strftime("%Y-%m-%d %H:%M") if highest_trip.end_time else "unknown date"}'
        }

    def manual_set_odometer(self, vehicle, odometer_value, dry_run=False):
        """Manually set odometer to a specific value."""
        old_odometer = vehicle.current_odometer
        new_odometer = odometer_value
        
        if old_odometer == new_odometer:
            return {
                'changed': False,
                'reason': f'Already set to {old_odometer} km'
            }
        
        if not dry_run:
            with transaction.atomic():
                vehicle.current_odometer = new_odometer
                vehicle.save()
        
        return {
            'changed': True,
            'old_odometer': old_odometer,
            'new_odometer': new_odometer,
            'reason': 'Manually set'
        }