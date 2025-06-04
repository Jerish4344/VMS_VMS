from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from trips.models import Trip
from vehicles.models import Vehicle
import datetime
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically end trips that have been ongoing for too long'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours after which to auto-end a trip'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without making actual changes'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        # Calculate the cutoff time
        cutoff_time = timezone.now() - datetime.timedelta(hours=hours)
        
        # Get ongoing trips that started before the cutoff time
        stale_trips = Trip.objects.filter(
            status='ongoing',
            start_time__lt=cutoff_time
        ).select_related('vehicle', 'driver')
        
        self.stdout.write(f"Found {stale_trips.count()} ongoing trips that started more than {hours} hours ago")
        
        if stale_trips.count() == 0:
            return
        
        # Process each stale trip
        for trip in stale_trips:
            # Log the trip details
            self.stdout.write(f"Processing trip #{trip.id}: Vehicle {trip.vehicle.license_plate}, "
                             f"Driver {trip.driver.get_full_name()}, Start time: {trip.start_time}")
            
            if not dry_run:
                try:
                    # Mark the trip as completed
                    trip.status = 'completed'
                    trip.end_time = timezone.now()
                    
                    # Set a reasonable end odometer reading if none exists
                    if not trip.end_odometer:
                        # If the vehicle has a higher current odometer, use that
                        if trip.vehicle.current_odometer > trip.start_odometer:
                            trip.end_odometer = trip.vehicle.current_odometer
                        else:
                            # Otherwise, estimate based on average trip distance
                            avg_distance = 50  # Default average distance in km
                            
                            # Try to calculate a better average from past trips
                            past_trips = Trip.objects.filter(
                                vehicle=trip.vehicle,
                                status='completed'
                            ).exclude(id=trip.id)[:10]
                            
                            if past_trips.exists():
                                distances = []
                                for past_trip in past_trips:
                                    if past_trip.end_odometer and past_trip.start_odometer:
                                        distances.append(past_trip.end_odometer - past_trip.start_odometer)
                                
                                if distances:
                                    avg_distance = sum(distances) / len(distances)
                            
                            trip.end_odometer = trip.start_odometer + int(avg_distance)
                    
                    # Update the trip
                    trip.save()
                    
                    # Update the vehicle status to available
                    vehicle = trip.vehicle
                    vehicle.status = 'available'
                    vehicle.current_odometer = trip.end_odometer
                    vehicle.save()
                    
                    self.stdout.write(self.style.SUCCESS(f"Auto-ended trip #{trip.id}"))
                    
                    # Create a notification about this auto-ended trip
                    from dashboard.models import Notification
                    
                    # Notify the driver
                    Notification.objects.create(
                        user=trip.driver,
                        text=f"Your trip with {trip.vehicle.license_plate} was automatically ended due to inactivity",
                        link=f'/trips/{trip.id}/',
                        icon='clock',
                        level='warning'
                    )
                    
                    # Notify managers
                    from accounts.models import CustomUser
                    managers = CustomUser.objects.filter(user_type__in=['admin', 'manager', 'vehicle_manager'])
                    
                    for manager in managers:
                        Notification.objects.create(
                            user=manager,
                            text=f"Trip by {trip.driver.get_full_name()} with {trip.vehicle.license_plate} was auto-ended",
                            link=f'/trips/{trip.id}/',
                            icon='exclamation-triangle',
                            level='warning'
                        )
                    
                except Exception as e:
                    logger.error(f"Failed to auto-end trip #{trip.id}: {str(e)}")
                    self.stdout.write(self.style.ERROR(f"Failed to auto-end trip #{trip.id}: {str(e)}"))
            else:
                self.stdout.write(f"[DRY RUN] Would auto-end trip #{trip.id}")
        
        self.stdout.write(self.style.SUCCESS(f"Successfully processed {stale_trips.count()} stale trips"))