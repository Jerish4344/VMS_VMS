# Create this file: trips/management/commands/fix_vehicle_odometers.py

from django.core.management.base import BaseCommand
from django.db import transaction
from trips.models import Trip
from vehicles.models import Vehicle
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix vehicle odometer readings based on the most recent completed trip by date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without making actual changes'
        )
        
        parser.add_argument(
            '--vehicle-id',
            type=int,
            help='Fix odometer for a specific vehicle only'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        vehicle_id = options.get('vehicle_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        if vehicle_id:
            vehicles = Vehicle.objects.filter(id=vehicle_id)
            if not vehicles.exists():
                self.stdout.write(self.style.ERROR(f"Vehicle with ID {vehicle_id} not found"))
                return
        else:
            vehicles = Vehicle.objects.all()
        
        self.stdout.write(f"Processing {vehicles.count()} vehicles...")
        
        fixed_count = 0
        unchanged_count = 0
        
        for vehicle in vehicles:
            result = self.fix_vehicle_odometer(vehicle, dry_run)
            if result['changed']:
                fixed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Vehicle {vehicle.license_plate}: "
                        f"{result['old_odometer']} → {result['new_odometer']} km "
                        f"(based on trip {result['trip_id']} on {result['trip_date']})"
                    )
                )
            else:
                unchanged_count += 1
                if result['reason']:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Vehicle {vehicle.license_plate}: {result['reason']}"
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary: {fixed_count} vehicles fixed, {unchanged_count} unchanged"
            )
        )

    def fix_vehicle_odometer(self, vehicle, dry_run=False):
        """Fix odometer for a single vehicle based on most recent completed trip."""
        # Find the most recent completed trip for this vehicle by end_time
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
        
        # Check if change is needed
        if old_odometer == new_odometer:
            return {
                'changed': False,
                'reason': f'Odometer already correct ({old_odometer} km)'
            }
        
        if not dry_run:
            with transaction.atomic():
                vehicle.current_odometer = new_odometer
                vehicle.save()
        
        return {
            'changed': True,
            'old_odometer': old_odometer,
            'new_odometer': new_odometer,
            'trip_id': latest_trip.id,
            'trip_date': latest_trip.end_time.strftime('%Y-%m-%d %H:%M')
        }