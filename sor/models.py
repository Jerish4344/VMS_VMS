from django.db import models

from django.conf import settings
from vehicles.models import Vehicle
from django.contrib.auth import get_user_model

User = get_user_model()

class SOR(models.Model):
    SOURCE_TYPE_CHOICES = [
        ('company', 'Company Vehicle'),
        ('outsourced_manual', 'Outsourced Manual Entry'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('driver_accepted', 'Driver Accepted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default='company')
    goods_value = models.DecimalField(max_digits=12, decimal_places=2)
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, null=True, blank=True)
    driver = models.ForeignKey(User, on_delete=models.PROTECT, limit_choices_to={'user_type': 'driver'}, null=True, blank=True)
    outsourced_vehicle_text = models.CharField(max_length=255, null=True, blank=True)
    outsourced_driver_text = models.CharField(max_length=255, null=True, blank=True)
    vendor_name = models.CharField(max_length=255, null=True, blank=True)
    start_odometer = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    end_odometer = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    outsourced_rate_per_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, default=25, help_text='Rate per KM for outsourced vehicle')
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    trip = models.ForeignKey('trips.Trip', on_delete=models.SET_NULL, null=True, blank=True, related_name='sor_entry')
    number_of_crates = models.IntegerField(null=True, blank=True, help_text="Optional: Number of crates")
    number_of_sac = models.IntegerField(null=True, blank=True, help_text="Optional: Number of sac")
    description = models.TextField(null=True, blank=True, help_text="Optional: Describe contents of crates or sac")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_sors')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def transport_cost(self):
        if self.distance_km:
            if self.source_type == 'outsourced_manual' and self.outsourced_rate_per_km:
                return self.distance_km * self.outsourced_rate_per_km
            elif self.vehicle and self.vehicle.rate_per_km:
                return self.distance_km * self.vehicle.rate_per_km
        return None

    def transport_cost_percentage(self):
        cost = self.transport_cost()
        if cost is not None and self.goods_value:
            try:
                return (cost / self.goods_value) * 100
            except (ZeroDivisionError, TypeError):
                return None
        return None

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['driver', 'status']),
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        vehicle_label = self.vehicle or self.outsourced_vehicle_text or 'Manual'
        return f"SOR #{self.id} - {vehicle_label} ({self.from_location} → {self.to_location})"
