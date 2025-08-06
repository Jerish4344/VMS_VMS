from django.db import models
from django.utils import timezone
from vehicles.models import Vehicle

class AiroTrackDevice(models.Model):
    """
    Represents a tracking device from AiroTrack associated with a vehicle.
    """
    device_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    vehicle = models.OneToOneField(
        Vehicle, 
        on_delete=models.CASCADE, 
        related_name='airotrack_device',
        null=True,
        blank=True
    )
    
    STATUS_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('inactive', 'Inactive'),
        ('unknown', 'Unknown'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    last_update = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name or self.device_id} ({self.get_status_display()})"
    
    def is_online(self):
        """Check if device is currently online."""
        return self.status == 'online'
    
    def update_status(self, new_status):
        """Update device status and last_update timestamp."""
        self.status = new_status
        self.last_update = timezone.now()
        self.save()

class VehicleLocation(models.Model):
    """
    Represents the current real-time location of a vehicle from AiroTrack API.
    Only one record per vehicle, updated in real-time.
    """
    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='current_location'
    )
    device = models.ForeignKey(
        AiroTrackDevice,
        on_delete=models.CASCADE,
        related_name='current_location'
    )
    
    # Location data
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    altitude = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Speed in km/h")
    course = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Direction in degrees")
    
    # Timestamps
    device_time = models.DateTimeField(help_text="Time reported by the device")
    server_time = models.DateTimeField(help_text="Time received by the server")
    fix_time = models.DateTimeField(null=True, blank=True, help_text="GPS fix time")
    
    # Status information
    valid = models.BooleanField(default=True, help_text="Whether the GPS data is valid")
    address = models.TextField(blank=True, null=True, help_text="Reverse geocoded address if available")
    
    # Vehicle status
    battery_level = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Battery level in percentage")
    signal_strength = models.IntegerField(null=True, blank=True, help_text="Signal strength in dBm")
    ignition = models.BooleanField(default=False, help_text="Whether the ignition is on")
    
    # Additional data
    raw_data = models.JSONField(null=True, blank=True, help_text="Raw data from AiroTrack API")
    
    def __str__(self):
        return f"Location of {self.vehicle} at {self.device_time}"
    
    def coordinates(self):
        """Return coordinates as a tuple."""
        return (float(self.latitude), float(self.longitude))
    
    def to_geojson(self):
        """Convert to GeoJSON format."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(self.longitude), float(self.latitude)]
            },
            "properties": {
                "vehicle_id": self.vehicle.id,
                "device_time": self.device_time.isoformat(),
                "speed": float(self.speed) if self.speed else None,
                "course": float(self.course) if self.course else None,
                "ignition": self.ignition,
                "valid": self.valid
            }
        }

class LocationHistory(models.Model):
    """
    Stores historical location data for vehicles.
    New records are created periodically to maintain history.
    """
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='location_history'
    )
    device = models.ForeignKey(
        AiroTrackDevice,
        on_delete=models.CASCADE,
        related_name='location_history'
    )
    
    # Location data
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    altitude = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    course = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Timestamps
    device_time = models.DateTimeField()
    server_time = models.DateTimeField(auto_now_add=True)
    
    # Status information
    valid = models.BooleanField(default=True)
    address = models.TextField(blank=True, null=True)
    
    # Vehicle status
    ignition = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-device_time']
        indexes = [
            models.Index(fields=['vehicle', 'device_time']),
            models.Index(fields=['device', 'device_time']),
        ]
        verbose_name_plural = "Location histories"
    
    def __str__(self):
        return f"History: {self.vehicle} at {self.device_time}"
    
    def coordinates(self):
        """Return coordinates as a tuple."""
        return (float(self.latitude), float(self.longitude))
