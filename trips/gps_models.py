"""
GPS Tracking Models for Trip Location Tracking
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
import math


class TripLocation(models.Model):
    """
    Stores GPS coordinates collected during a trip for route verification
    """
    trip = models.ForeignKey('Trip', on_delete=models.CASCADE, related_name='gps_locations')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="GPS Latitude")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, help_text="GPS Longitude")
    accuracy = models.FloatField(help_text="GPS accuracy in meters")
    speed = models.FloatField(null=True, blank=True, help_text="Speed in km/h")
    altitude = models.FloatField(null=True, blank=True, help_text="Altitude in meters")
    heading = models.FloatField(null=True, blank=True, help_text="Direction in degrees")
    timestamp = models.DateTimeField(default=timezone.now)
    battery_level = models.IntegerField(null=True, blank=True, help_text="Battery percentage at this point")
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['trip', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Location for Trip #{self.trip_id} at {self.timestamp.strftime('%H:%M:%S')}"
    
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """
        Calculate distance between two GPS coordinates using Haversine formula
        Returns distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(float(lat1))
        lon1_rad = math.radians(float(lon1))
        lat2_rad = math.radians(float(lat2))
        lon2_rad = math.radians(float(lon2))
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        radius = 6371
        
        return c * radius


class GPSTrackingSession(models.Model):
    """
    Represents a GPS tracking session for a trip
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('interrupted', 'Interrupted'),
        ('battery_died', 'Battery Died'),
    ]
    
    trip = models.OneToOneField('Trip', on_delete=models.CASCADE, related_name='gps_session')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # GPS Statistics
    total_points = models.IntegerField(default=0, help_text="Total GPS points collected")
    valid_points = models.IntegerField(default=0, help_text="Points with good accuracy")
    gaps_detected = models.IntegerField(default=0, help_text="Number of signal loss gaps")
    longest_gap_seconds = models.IntegerField(default=0, help_text="Longest gap without GPS")
    
    # Distance Calculations
    gps_distance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                      help_text="Total distance from GPS (km)")
    odometer_distance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                           help_text="Distance from odometer (km)")
    variance_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                             help_text="Percentage difference")
    
    # Validation
    requires_review = models.BooleanField(default=False, help_text="Needs admin review")
    review_reason = models.TextField(blank=True, help_text="Reason for review requirement")
    reviewed_by = models.ForeignKey('accounts.CustomUser', null=True, blank=True, 
                                   on_delete=models.SET_NULL, related_name='gps_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    approved = models.BooleanField(null=True, blank=True, help_text="Admin approval decision")
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"GPS Session for Trip #{self.trip_id} - {self.status}"
    
    def calculate_gps_distance(self):
        """
        Calculate total distance from all GPS points in this session
        """
        locations = self.trip.gps_locations.order_by('timestamp')
        
        if locations.count() < 2:
            return Decimal('0.00')
        
        total_distance = Decimal('0.00')
        prev_location = None
        
        for location in locations:
            if prev_location:
                distance = TripLocation.calculate_distance(
                    prev_location.latitude, prev_location.longitude,
                    location.latitude, location.longitude
                )
                total_distance += Decimal(str(distance))
            prev_location = location
        
        return round(total_distance, 2)
    
    def validate_trip(self):
        """
        Validate GPS data against odometer reading and flag for review if needed
        """
        if not self.gps_distance or not self.odometer_distance:
            return
        
        # Calculate variance
        if self.odometer_distance > 0:
            variance = abs(self.gps_distance - self.odometer_distance) / self.odometer_distance * 100
            self.variance_percentage = round(Decimal(str(variance)), 2)
        else:
            self.variance_percentage = Decimal('0.00')
        
        # Flag for review based on variance
        reasons = []
        
        if self.variance_percentage > 15:
            self.requires_review = True
            reasons.append(f"High variance: {self.variance_percentage}% difference between GPS and odometer")
        
        if self.total_points < 10:
            self.requires_review = True
            reasons.append(f"Insufficient GPS data: Only {self.total_points} points collected")
        
        if self.gaps_detected > 5:
            self.requires_review = True
            reasons.append(f"Multiple GPS signal losses: {self.gaps_detected} gaps detected")
        
        if self.longest_gap_seconds > 300:  # 5 minutes
            self.requires_review = True
            reasons.append(f"Long GPS gap: {self.longest_gap_seconds // 60} minutes without signal")
        
        if reasons:
            self.review_reason = "\n".join(reasons)
        
        self.save()
