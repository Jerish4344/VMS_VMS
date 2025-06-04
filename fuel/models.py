# fuel/models.py
from django.db import models
from vehicles.models import Vehicle
from django.conf import settings

class FuelStation(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Add station type to differentiate fuel stations from charging stations
    STATION_TYPE_CHOICES = [
        ('fuel', 'Fuel Station'),
        ('charging', 'Charging Station'),
        ('both', 'Fuel & Charging Station'),
    ]
    station_type = models.CharField(
        max_length=20,
        choices=STATION_TYPE_CHOICES,
        default='fuel'
    )
    
    def __str__(self):
        return self.name

class FuelTransaction(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='fuel_transactions')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fuel_station = models.ForeignKey(FuelStation, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    
    # For regular fuel vehicles
    fuel_type = models.CharField(max_length=50, blank=True)
    quantity = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Fuel quantity in liters (for fuel vehicles)"
    )
    cost_per_liter = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True,
        blank=True
    )
    
    # For electric vehicles
    energy_consumed = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Energy consumed in kWh (for electric vehicles)"
    )
    cost_per_kwh = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per kWh (for electric vehicles)"
    )
    charging_duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Charging duration in minutes (for electric vehicles)"
    )
    
    # Common fields
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    odometer_reading = models.PositiveIntegerField(help_text="Current odometer reading in km")
    receipt_image = models.ImageField(upload_to='fuel_receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        if self.is_electric_transaction():
            return f"Charging for {self.vehicle} on {self.date}"
        else:
            return f"Fuel for {self.vehicle} on {self.date}"
    
    def is_electric_transaction(self):
        """Check if this is an electric vehicle transaction."""
        return (self.vehicle.is_electric() if hasattr(self.vehicle, 'is_electric') 
                else self.fuel_type == 'Electric')
    
    def get_quantity_display(self):
        """Get appropriate quantity display based on vehicle type."""
        if self.is_electric_transaction():
            return f"{self.energy_consumed} kWh" if self.energy_consumed else "N/A"
        else:
            return f"{self.quantity} L" if self.quantity else "N/A"
    
    def get_unit_cost_display(self):
        """Get appropriate unit cost display based on vehicle type."""
        if self.is_electric_transaction():
            return f"₹{self.cost_per_kwh}/kWh" if self.cost_per_kwh else "N/A"
        else:
            return f"₹{self.cost_per_liter}/L" if self.cost_per_liter else "N/A"
    
    def save(self, *args, **kwargs):
        # Auto-calculate total cost if not provided
        if not self.total_cost or self.total_cost <= 0:
            if self.is_electric_transaction():
                if self.energy_consumed and self.cost_per_kwh:
                    self.total_cost = self.energy_consumed * self.cost_per_kwh
            else:
                if self.quantity and self.cost_per_liter:
                    self.total_cost = self.quantity * self.cost_per_liter
        
        # Ensure fuel_type is set for electric vehicles
        if self.is_electric_transaction() and not self.fuel_type:
            self.fuel_type = 'Electric'
        
        super().save(*args, **kwargs)
