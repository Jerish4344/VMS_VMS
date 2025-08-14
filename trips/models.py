from django.db import models
from django.utils import timezone
from vehicles.models import Vehicle
from django.conf import settings
from django.core.exceptions import ValidationError
from django.apps import apps  # Lazy model lookup to avoid circular imports

# Lazy reference to ConsultantRate to prevent circular-import issues.
# Will be resolved the first time it's actually needed.
ConsultantRate = None

class Trip(models.Model):
    def delete(self, using=None, keep_parents=False, user=None):
        """
        Override delete to perform a soft delete. Pass user to record who deleted.
        """
        self.soft_delete(user)
    """Record of a vehicle trip."""
    
    STATUS_CHOICES = (
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    ENTRY_TYPE_CHOICES = (
        ('real_time', 'Real-time'),
        ('manual', 'Manual Entry'),
    )
    
    vehicle = models.ForeignKey(
        Vehicle, 
        on_delete=models.CASCADE,
        related_name='trips'
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trips'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    start_odometer = models.PositiveIntegerField(help_text="Odometer reading at trip start in km")
    end_odometer = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Odometer reading at trip end in km"
    )
    
    # Location fields
    origin = models.CharField(
        max_length=255,
        help_text="Starting location/address"
    )
    destination = models.CharField(
        max_length=255,
        blank=True,  # Allow blank for start trip
        null=True,   # Allow null for start trip
        help_text="Destination location/address (added when ending trip)"
    )
    
    purpose = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ongoing'
    )
    
    # Add entry type to distinguish between real-time and manual entries
    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPE_CHOICES,
        default='real_time',
        help_text="How this trip was entered into the system"
    )
    
    # Add timestamps for audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Mark trip as deleted instead of removing from DB")
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='deleted_trips',
        help_text="User who deleted this trip"
    )
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the trip was deleted")
    def soft_delete(self, user):
        """
        Soft delete the trip, recording who deleted and when.
        """
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_by = user
            self.deleted_at = timezone.now()
            self.save()
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        destination = self.destination or "TBD"
        return f"{self.vehicle} driven by {self.driver.get_full_name()} from {self.origin} to {destination} on {self.start_time.date()}"
    
    def clean(self):
        """Validate trip data."""
        super().clean()
        
        # Validate end_odometer if provided
        if self.end_odometer is not None:
            if self.end_odometer <= self.start_odometer:
                raise ValidationError({
                    'end_odometer': f'End odometer ({self.end_odometer}) must be greater than start odometer ({self.start_odometer})'
                })
        
        # Validate destination is required when trip is completed
        if self.status == 'completed' and not self.destination:
            raise ValidationError({
                'destination': 'Destination is required when completing a trip'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to update related vehicle status and odometer.
        Handle manual entries differently from real-time trips.
        """
        # Store the original status to detect changes
        original_status = None
        is_new_trip = not self.pk
        
        if self.pk:
            try:
                original_trip = Trip.objects.get(pk=self.pk)
                original_status = original_trip.status
            except Trip.DoesNotExist:
                pass
        
        # For a new trip
        if is_new_trip:
            # Real-time trips: update vehicle status immediately
            if self.entry_type == 'real_time' and self.status == 'ongoing':
                self.vehicle.status = 'in_use'
                # Ensure vehicle's current_odometer is not None
                if self.vehicle.current_odometer is None:
                    self.vehicle.current_odometer = self.start_odometer
                self.vehicle.save()
            
            # Manual entries: don't change vehicle status unless specified
            elif self.entry_type == 'manual':
                # For manual entries, only update vehicle odometer if this is the latest trip
                # and it's completed with a higher odometer reading
                if (self.status == 'completed' and self.end_odometer and 
                    (not self.vehicle.current_odometer or self.end_odometer > self.vehicle.current_odometer)):
                    # Check if this is indeed the latest trip by odometer reading
                    latest_trip = Trip.objects.filter(
                        vehicle=self.vehicle,
                        end_odometer__isnull=False
                    ).exclude(pk=self.pk).order_by('-end_odometer').first()
                    
                    if not latest_trip or self.end_odometer >= latest_trip.end_odometer:
                        self.vehicle.current_odometer = self.end_odometer
                        self.vehicle.save()
        else:
            # For existing trip - check if status changed to completed or cancelled
            if (original_status == 'ongoing' and 
                self.status in ['completed', 'cancelled']):
                
                # Real-time trips: update vehicle status back to available
                if self.entry_type == 'real_time':
                    self.vehicle.status = 'available'
                    
                    # Update vehicle odometer if completed with valid end_odometer
                    if self.status == 'completed' and self.end_odometer:
                        if self.end_odometer > 0:
                            self.vehicle.current_odometer = self.end_odometer
                        else:
                            # Fallback: use start_odometer if end_odometer is invalid
                            self.vehicle.current_odometer = self.start_odometer
                    elif self.status == 'cancelled':
                        # For cancelled trips, keep the original odometer or use start_odometer
                        if self.vehicle.current_odometer is None:
                            self.vehicle.current_odometer = self.start_odometer
                    
                    # Ensure current_odometer is never None before saving vehicle
                    if self.vehicle.current_odometer is None:
                        self.vehicle.current_odometer = self.start_odometer
                    
                    self.vehicle.save()
                
                # Manual entries: only update odometer if this is the highest reading
                elif self.entry_type == 'manual' and self.status == 'completed' and self.end_odometer:
                    if (not self.vehicle.current_odometer or 
                        self.end_odometer > self.vehicle.current_odometer):
                        # Verify this is the latest completed trip
                        latest_trip = Trip.objects.filter(
                            vehicle=self.vehicle,
                            end_odometer__isnull=False,
                            status='completed'
                        ).exclude(pk=self.pk).order_by('-end_odometer').first()
                        
                        if not latest_trip or self.end_odometer >= latest_trip.end_odometer:
                            self.vehicle.current_odometer = self.end_odometer
                            self.vehicle.save()
        
        # Set end_time when trip is completed (if not already set)
        if self.status == 'completed' and not self.end_time:
            self.end_time = timezone.now()
        
        super().save(*args, **kwargs)
    
    def distance_traveled(self):
        """Calculate distance traveled during the trip."""
        if self.end_odometer is not None and self.start_odometer is not None:
            return max(0, self.end_odometer - self.start_odometer)
        return 0
    
    def trip_cost(self):
        """Calculate the cost of this trip based on vehicle's rate per km."""
        distance = self.distance_traveled()
        if self.vehicle.rate_per_km and distance > 0:
            return float(self.vehicle.rate_per_km) * distance
        return 0
    
    def get_duration_timedelta(self):
        """Calculate trip duration as a timedelta object."""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        elif self.start_time and self.status == 'ongoing':
            # For ongoing trips, calculate duration from start_time to now
            return timezone.now() - self.start_time
        return None
    
    def duration(self):
        """Return trip duration as a formatted string 'Xh Ym' or 'Ym' or 'Xs'."""
        delta = self.get_duration_timedelta()
        if delta:
            total_seconds = int(delta.total_seconds())
            days = total_seconds // (24 * 3600)
            hours = (total_seconds // 3600) % 24
            minutes = (total_seconds // 60) % 60
            seconds = total_seconds % 60

            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if not parts and seconds > 0:
                parts.append(f"{seconds}s")
            
            if not parts and total_seconds == 0:
                return "0m"
            
            return " ".join(parts) if parts else None
        return None
    
    def is_active(self):
        """Check if trip is currently active."""
        return self.status == 'ongoing'
    
    def can_be_ended_by(self, user):
        """Check if user can end this trip."""
        # Only the driver or admin/manager can end the trip
        return (
            user == self.driver or 
            hasattr(user, 'user_type') and user.user_type in ['admin', 'manager', 'vehicle_manager']
        )
    
    def get_route_summary(self):
        """Get a formatted route summary."""
        destination = self.destination or "TBD"
        return f"{self.origin} → {destination}"
    
    def end_trip(self, destination, end_odometer, notes=None):
        """
        Safely end a trip with proper validation.
        """
        if self.status != 'ongoing':
            raise ValidationError("Can only end ongoing trips")
        
        if not destination or len(destination.strip()) < 3:
            raise ValidationError("Destination is required to end the trip")
        
        if not end_odometer or end_odometer <= self.start_odometer:
            raise ValidationError(f"End odometer ({end_odometer}) must be greater than start odometer ({self.start_odometer})")
        
        self.destination = destination.strip()
        self.end_odometer = end_odometer
        self.end_time = timezone.now()
        self.status = 'completed'
        
        if notes:
            self.notes = notes
        
        # The save method will handle vehicle updates
        self.save()
    
    def cancel_trip(self, reason=None):
        """
        Cancel an ongoing trip.
        """
        if self.status != 'ongoing':
            raise ValidationError("Can only cancel ongoing trips")
        
        self.status = 'cancelled'
        self.end_time = timezone.now()
        
        if reason:
            self.notes = f"Trip cancelled: {reason}" + (f"\n{self.notes}" if self.notes else "")
        
        # The save method will handle vehicle status update
        self.save()

    # ------------------------------------------------------------------
    #  Consultant driver payment helpers
    # ------------------------------------------------------------------

    def get_consultant_rate(self):
        """
        Lazily fetch the ConsultantRate model and then return the active rate
        object for the current driver/vehicle combination (if any).
        """
        global ConsultantRate
        if ConsultantRate is None:
            # Resolve the model only once; afterwards it's cached in the module.
            ConsultantRate = apps.get_model('trips', 'ConsultantRate')
        return ConsultantRate.get_active_rate(self.driver, self.vehicle)

    def consultant_payment(self):
        """
        Calculate the consultant driver's payment for this trip
        based on the active rate and the distance travelled.
        Returns a float amount in Rupees. If no active rate exists
        for this driver-vehicle pair, returns 0.
        """
        rate_obj = self.get_consultant_rate()
        if not rate_obj:
            return 0
        return rate_obj.calculate_payment(self.distance_traveled())
