from django.db import models

from django.conf import settings
from vehicles.models import Vehicle
from django.contrib.auth import get_user_model

User = get_user_model()

class SOR(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('driver_accepted', 'Driver Accepted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    goods_value = models.DecimalField(max_digits=12, decimal_places=2)
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    driver = models.ForeignKey(User, on_delete=models.PROTECT, limit_choices_to={'user_type': 'driver'})
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
        if self.distance_km and self.vehicle and self.vehicle.rate_per_km:
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

    def __str__(self):
        return f"SOR #{self.id} - {self.vehicle} ({self.from_location} → {self.to_location})"
