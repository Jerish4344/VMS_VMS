from django.db import models
from vehicles.models import Vehicle
from accounts.models import CustomUser

class MaintenanceType(models.Model):
    name = models.CharField(max_length=100)  # Oil Change, Tire Rotation, Brake Service, etc.
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class MaintenanceProvider(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    def __str__(self):
        return self.name

class Maintenance(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_type = models.ForeignKey(MaintenanceType, on_delete=models.CASCADE)
    provider = models.ForeignKey(MaintenanceProvider, on_delete=models.SET_NULL, null=True, blank=True)
    reported_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reported_maintenance')
    date_reported = models.DateField()
    description = models.TextField()
    odometer_reading = models.PositiveIntegerField(help_text="Odometer reading at maintenance in km")
    status = models.CharField(
        max_length=20,
        choices=(
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ),
        default='scheduled'
    )
    scheduled_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    invoice_image = models.ImageField(upload_to='maintenance_invoices/', null=True, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.maintenance_type.name} for {self.vehicle} on {self.date_reported}"