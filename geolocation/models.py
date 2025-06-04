from django.db import models
from trips.models import Trip

class LocationLog(models.Model):
    """GPS location data point for a trip."""
    
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='locations'
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    altitude = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True
    )
    speed = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Speed in km/h"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['trip', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Location for {self.trip} at {self.timestamp}"
    
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
                "trip_id": self.trip.id,
                "timestamp": self.timestamp.isoformat(),
                "speed": float(self.speed) if self.speed else None,
                "altitude": float(self.altitude) if self.altitude else None
            }
        }