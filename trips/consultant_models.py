from django.db import models
from django.utils import timezone
from vehicles.models import Vehicle
from django.conf import settings
from django.core.validators import MinValueValidator

class ConsultantRate(models.Model):
    """
    Model to store rate information for consultant drivers.
    Each consultant driver can have different rates for different vehicles.
    """
    
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultant_rates',
        help_text="The consultant driver"
    )
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='consultant_rates',
        help_text="The vehicle assigned to the consultant"
    )
    
    rate_per_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Rate per kilometer in Rs (e.g., 16.00)"
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Whether this rate is currently active"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this consultant rate"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['driver', 'vehicle', 'status']
        ordering = ['-updated_at']
        verbose_name = "Consultant Rate"
        verbose_name_plural = "Consultant Rates"
    
    def __str__(self):
        return f"{self.driver.get_full_name()} - {self.vehicle} - ₹{self.rate_per_km}/km"
    
    def is_active(self):
        """Check if this rate is active."""
        return self.status == 'active'
    
    def calculate_payment(self, distance_km):
        """
        Calculate payment for a given distance.
        
        Args:
            distance_km: Distance traveled in kilometers
            
        Returns:
            Calculated payment amount
        """
        if distance_km <= 0:
            return 0
        return float(self.rate_per_km) * distance_km
    
    @classmethod
    def get_active_rate(cls, driver, vehicle):
        """
        Get the active rate for a driver-vehicle combination.
        
        Args:
            driver: The driver (CustomUser instance)
            vehicle: The vehicle (Vehicle instance)
            
        Returns:
            ConsultantRate instance or None if no active rate exists
        """
        try:
            return cls.objects.get(
                driver=driver,
                vehicle=vehicle,
                status='active'
            )
        except cls.DoesNotExist:
            return None
