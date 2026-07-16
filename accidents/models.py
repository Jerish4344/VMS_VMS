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
        indexes = [
            models.Index(fields=['date_time']),
            models.Index(fields=['vehicle', 'date_time']),
            models.Index(fields=['driver', 'date_time']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Accident involving {self.vehicle} on {self.date_time.date()}"
    
    def save(self, *args, **kwargs):
        """Override save to update vehicle status if needed."""
        # If this is a new accident, set vehicle to maintenance
        is_new = not self.pk
        was_resolved = None
        if not is_new:
            try:
                was_resolved = Accident.objects.get(pk=self.pk).status == 'resolved'
            except Accident.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if is_new and self.vehicle.status != 'retired':
            self.vehicle.status = 'maintenance'
            self.vehicle.save()
        elif was_resolved is False and self.status == 'resolved':
            # Recalculate *after* this accident's own new status is persisted,
            # so the "any unresolved accidents left?" check doesn't count this
            # accident's own stale pre-save status against itself.
            self.vehicle.recalculate_status()
            self.vehicle.save()
