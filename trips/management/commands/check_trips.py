# Create this file: trips/management/commands/check_trips.py

import os
from django.core.management.base import BaseCommand
from trips.models import Trip

class Command(BaseCommand):
    help = 'Check trip data for debugging'

    def handle(self, *args, **options):
        trips = Trip.objects.all().select_related('vehicle', 'driver')
        
        self.stdout.write(f"Total trips in database: {trips.count()}")
        self.stdout.write("=" * 50)
        
        status_counts = {}
        for trip in trips:
            status = trip.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            
            self.stdout.write(
                f"Trip {trip.id}: {trip.vehicle.license_plate} | "
                f"Driver: {trip.driver.get_full_name()} | "
                f"Status: '{trip.status}' | "
                f"Date: {trip.start_time.date()} | "
                f"Route: {trip.origin} → {trip.destination}"
            )
        
        self.stdout.write("=" * 50)
        self.stdout.write("Status Summary:")
        for status, count in status_counts.items():
            self.stdout.write(f"  {status}: {count}")
        
        # Check for any data issues
        self.stdout.write("=" * 50)
        self.stdout.write("Data Quality Check:")
        
        trips_without_end = trips.filter(status='completed', end_time__isnull=True)
        if trips_without_end.exists():
            self.stdout.write(f"⚠️  {trips_without_end.count()} completed trips without end_time")
        
        trips_without_odometer = trips.filter(status='completed', end_odometer__isnull=True)
        if trips_without_odometer.exists():
            self.stdout.write(f"⚠️  {trips_without_odometer.count()} completed trips without end_odometer")
        
        self.stdout.write("✅ Check complete!")