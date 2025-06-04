from django.db import models
from django.utils import timezone

class VehicleType(models.Model):
    """
    Different types of vehicles in the fleet (Car, Van, Truck, etc.).
    """
    
    CATEGORY_CHOICES = (
        ('personal', 'Personal Vehicle'),
        ('commercial', 'Commercial Vehicle'),
        ('electric', 'Electric Vehicle'),
    )
    
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='personal',
        help_text="Category determines which fields are required"
    )
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def vehicle_count(self):
        """Count vehicles of this type."""
        return self.vehicle_set.count()
    
    def is_commercial(self):
        """Check if this is a commercial vehicle type."""
        return self.category == 'commercial'
    
    def is_electric(self):
        """Check if this is an electric vehicle type."""
        return self.category == 'electric'

class Vehicle(models.Model):
    """
    Represents a vehicle in the fleet with all its details.
    """
    
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    )
    
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    license_plate = models.CharField(max_length=20, unique=True)
    vin = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Vehicle Identification Number"
    )

    # Updated field lengths to accommodate longer data
    owner_name = models.CharField(max_length=150, blank=True)
    rc_valid_till = models.DateField(null=True, blank=True, verbose_name="RC Valid Till")
    insurance_expiry_date = models.DateField(null=True, blank=True)
    fitness_expiry = models.DateField(null=True, blank=True)
    permit_expiry = models.DateField(null=True, blank=True)
    pollution_cert_expiry = models.DateField(null=True, blank=True, verbose_name="Pollution Certificate Expiry")
    
    GPS_CHOICES = (
        ('yes', 'Yes'),
        ('no', 'No'),
    )
    gps_fitted = models.CharField(max_length=3, choices=GPS_CHOICES, default='no')
    gps_name = models.CharField(max_length=100, blank=True)
    
    # Updated field lengths for driver information
    driver_contact = models.CharField(max_length=100, blank=True)
    assigned_driver = models.CharField(max_length=150, blank=True)
    
    # Updated field lengths for purpose and usage
    purpose_of_vehicle = models.CharField(max_length=200, blank=True)
    
    OWNERSHIP_CHOICES = (
        ('yes', 'Yes'),
        ('no', 'No'),
    )
    company_owned = models.CharField(max_length=3, choices=OWNERSHIP_CHOICES, default='yes')
    
    USAGE_TYPE_CHOICES = (
        ('personal', 'Personal'),
        ('staff', 'Staff'),
        ('other', 'Other'),
    )
    usage_type = models.CharField(max_length=20, choices=USAGE_TYPE_CHOICES, default='staff')
    used_by = models.CharField(max_length=150, blank=True)
    
    # Capacity fields - seating for all, load for commercial
    seating_capacity = models.PositiveIntegerField(default=1)
    load_capacity_kg = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Load capacity in KG (for commercial vehicles)",
        verbose_name="Load Capacity (KG)"
    )
    
    # Fuel/Energy fields - conditional based on vehicle type
    fuel_type = models.CharField(max_length=50, blank=True)
    fuel_capacity = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True,
        blank=True,
        help_text="Fuel tank capacity in liters"
    )
    average_mileage = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Average mileage in km/L (for fuel vehicles)"
    )
    
    # Electric vehicle specific fields
    battery_capacity_kwh = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Battery capacity in kWh (for electric vehicles)",
        verbose_name="Battery Capacity (kWh)"
    )
    charging_type = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Type of charging port (Type 2, CCS, CHAdeMO, etc.)"
    )
    range_per_charge = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Estimated range per full charge in km",
        verbose_name="Range per Charge (km)"
    )
    charging_time_hours = models.DecimalField(
        max_digits=4, 
        decimal_places=1, 
        null=True, 
        blank=True,
        help_text="Time to fully charge in hours",
        verbose_name="Charging Time (hours)"
    )

    color = models.CharField(max_length=50)
    current_odometer = models.PositiveIntegerField(
        default=0, 
        help_text="Current odometer reading in km"
    )
    acquisition_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to='vehicles/', null=True, blank=True)
    
    class Meta:
        ordering = ['license_plate']
    
    def __str__(self):
        return f"{self.make} {self.model} ({self.license_plate})"
    
    def is_available(self):
        """Check if vehicle is available for assignment."""
        return self.status == 'available'
    
    def is_in_use(self):
        """Check if vehicle is currently in use."""
        return self.status == 'in_use'
    
    def is_under_maintenance(self):
        """Check if vehicle is under maintenance."""
        return self.status == 'maintenance'
    
    def is_retired(self):
        """Check if vehicle is retired."""
        return self.status == 'retired'
    
    def is_commercial(self):
        """Check if this is a commercial vehicle."""
        return self.vehicle_type.is_commercial()
    
    def is_electric(self):
        """Check if this is an electric vehicle."""
        return self.vehicle_type.is_electric()
    
    def get_capacity_display(self):
        """Get appropriate capacity display based on vehicle type."""
        if self.is_commercial() and self.load_capacity_kg:
            return f"{self.load_capacity_kg} kg"
        return f"{self.seating_capacity} seats"
    
    def get_fuel_energy_display(self):
        """Get appropriate fuel/energy display based on vehicle type."""
        if self.is_electric():
            if self.battery_capacity_kwh:
                return f"{self.battery_capacity_kwh} kWh"
            return "Electric"
        else:
            if self.fuel_capacity:
                return f"{self.fuel_capacity}L {self.fuel_type}"
            return self.fuel_type or "Unknown"
    
    def get_efficiency_display(self):
        """Get efficiency display - mileage for fuel, range for electric."""
        if self.is_electric():
            if self.range_per_charge:
                return f"{self.range_per_charge} km/charge"
            return "N/A"
        else:
            if self.average_mileage:
                return f"{self.average_mileage} km/L"
            return "N/A"
    
    def get_active_trip(self):
        """Get the active trip for this vehicle, if any."""
        return self.trips.filter(status='ongoing').first()
    
    def has_active_trip(self):
        """Check if vehicle has an active trip."""
        return self.trips.filter(status='ongoing').exists()
    
    def get_current_driver(self):
        """Get the current driver of the vehicle, if any."""
        active_trip = self.get_active_trip()
        if active_trip:
            return active_trip.driver
        return None
    
    def get_total_distance(self):
        """Calculate total distance traveled by this vehicle."""
        from django.db.models import Sum, F
        
        total = self.trips.filter(
            status='completed'
        ).aggregate(
            total=Sum(F('end_odometer') - F('start_odometer'))
        )
        
        return total['total'] or 0
    
    def get_total_fuel_consumption(self):
        """Calculate total fuel consumption for this vehicle."""
        from django.db.models import Sum
        
        total = self.fuel_transactions.aggregate(Sum('quantity'))
        return total['quantity__sum'] or 0
    
    def get_fuel_efficiency(self):
        """Calculate fuel efficiency (km/L) for this vehicle."""
        if self.is_electric():
            return None  # Not applicable for electric vehicles
        
        total_distance = self.get_total_distance()
        total_fuel = self.get_total_fuel_consumption()
        
        if total_fuel > 0:
            return total_distance / total_fuel
        return 0
    
    def get_upcoming_maintenance(self):
        """Get upcoming scheduled maintenance."""
        return self.maintenance_records.filter(
            status='scheduled',
            scheduled_date__gte=timezone.now().date()
        ).order_by('scheduled_date')
    
    def get_document_status(self):
        """Check if all required documents are valid."""
        from documents.models import Document, DocumentType
        
        required_types = DocumentType.objects.filter(required=True)
        for doc_type in required_types:
            # Check if there's a valid document of this type
            today = timezone.now().date()
            valid_doc = self.documents.filter(
                document_type=doc_type,
                expiry_date__gt=today
            ).exists()
            
            if not valid_doc:
                return False
        
        return True
    
    def clean(self):
        """Validate model fields based on vehicle type."""
        from django.core.exceptions import ValidationError
        
        errors = {}
        
        if self.vehicle_type:
            vehicle_type_name = self.vehicle_type.name.upper()
            
            # Commercial vehicles should have load capacity
            is_commercial = any(word in vehicle_type_name for word in ['TRUCK', 'VAN', 'PICKUP', 'COMMERCIAL', 'LORRY'])
            if is_commercial and not self.load_capacity_kg:
                errors['load_capacity_kg'] = 'Load capacity is required for commercial vehicles.'
            
            # Electric vehicles should have battery info
            is_electric = any(word in vehicle_type_name for word in ['ELECTRIC', 'EV', 'HYBRID'])
            if is_electric:
                if not self.battery_capacity_kwh:
                    errors['battery_capacity_kwh'] = 'Battery capacity is required for electric vehicles.'
                if not self.range_per_charge:
                    errors['range_per_charge'] = 'Range per charge is required for electric vehicles.'
            # Remove the fuel requirement validation for now to allow saving
        
        if errors:
            raise ValidationError(errors)