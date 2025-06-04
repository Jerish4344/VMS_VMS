# accidents/models.py

from django.db import models
from vehicles.models import Vehicle
from django.conf import settings

class AccidentImage(models.Model):
    """Images related to vehicle accidents."""
    accident = models.ForeignKey('Accident', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='accident_images/')
    caption = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return self.caption or f"Image for accident #{self.accident_id}"

class Accident(models.Model):
    """Record of a vehicle accident."""
    
    STATUS_CHOICES = (
        ('reported', 'Reported'),
        ('under_investigation', 'Under Investigation'),
        ('repair_scheduled', 'Repair Scheduled'),
        ('repair_in_progress', 'Repair In Progress'),
        ('resolved', 'Resolved'),
    )
    
    vehicle = models.ForeignKey(
        Vehicle, 
        on_delete=models.CASCADE,
        related_name='accidents'
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='accidents'
    )
    date_time = models.DateTimeField()
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=50, 
        decimal_places=20,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=50, 
        decimal_places=20,
        null=True,
        blank=True
    )
    description = models.TextField()
    damage_description = models.TextField()
    third_party_involved = models.BooleanField(default=False)
    police_report_number = models.CharField(max_length=100, blank=True)
    injuries = models.BooleanField(default=False)
    injuries_description = models.TextField(blank=True)
    estimated_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True
    )
    actual_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True
    )
    insurance_claim_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='reported'
    )
    resolution_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date_time']
    
    def __str__(self):
        return f"Accident involving {self.vehicle} on {self.date_time.date()}"
    
    def save(self, *args, **kwargs):
        """Override save to update vehicle status if needed."""
        # If this is a new accident, set vehicle to maintenance
        if not self.pk and self.vehicle.status == 'in_use':
            self.vehicle.status = 'maintenance'
            self.vehicle.save()
            
        # If status is changing to resolved, update vehicle status
        elif self.pk:
            try:
                old_accident = Accident.objects.get(pk=self.pk)
                if old_accident.status != 'resolved' and self.status == 'resolved':
                    # If there are no other unresolved accidents, set vehicle to available
                    other_accidents = Accident.objects.filter(
                        vehicle=self.vehicle,
                        status__in=['reported', 'under_investigation', 'repair_scheduled', 'repair_in_progress']
                    ).exclude(pk=self.pk).count()
                    
                    if other_accidents == 0:
                        self.vehicle.status = 'available'
                        self.vehicle.save()
            except Accident.DoesNotExist:
                pass
                
        super().save(*args, **kwargs)
