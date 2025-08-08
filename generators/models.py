"""
Models for the Generator module.

These cover:
1. Store information (where the generator is located/managed)
2. Generator master data
3. Usage tracking (daily / weekly running hours)
4. Fuel entry log
5. Maintenance log
"""

from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

# --------------------------------------------------------------------------- #
#  Common / shared choices & helpers
# --------------------------------------------------------------------------- #


class FuelType(models.TextChoices):
    DIESEL = "diesel", "Diesel"
    PETROL = "petrol", "Petrol"
    GAS = "gas", "Gas"
    OTHER = "other", "Other"


# --------------------------------------------------------------------------- #
#  Master Data
# --------------------------------------------------------------------------- #


class Store(models.Model):
    """
    Physical location where generators are kept/operated.
    """

    name = models.CharField(max_length=255, unique=True, help_text="Store name or code")
    location = models.CharField(max_length=255)
    manager_name = models.CharField(max_length=255, blank=True, null=True)
    contact_info = models.CharField(max_length=255, help_text="Phone / Email", blank=True, null=True)

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"
        ordering = ("name",)

    def __str__(self) -> str:  # noqa: D401
        return self.name


class Generator(models.Model):
    """
    Master data for each generator.
    """

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="generators")
    make_and_model = models.CharField(max_length=255)
    capacity_kva = models.PositiveIntegerField(help_text="Capacity in kVA")
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, default=FuelType.DIESEL)
    serial_number = models.CharField(max_length=100, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "Generator"
        verbose_name_plural = "Generators"
        ordering = ("store", "make_and_model")

    def __str__(self) -> str:  # noqa: D401
        return f"{self.make_and_model} ({self.capacity_kva} kVA)"


# --------------------------------------------------------------------------- #
#  Operational Logs
# --------------------------------------------------------------------------- #


class UsageTracking(models.Model):
    """
    Daily / weekly running log for a generator.
    """

    generator = models.ForeignKey(Generator, on_delete=models.CASCADE, related_name="usage_logs")
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField()
    total_hours_run = models.DecimalField(max_digits=5, decimal_places=2)
    reason_for_use = models.CharField(max_length=255)
    observations = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Usage Tracking"
        verbose_name_plural = "Usage Tracking"
        ordering = ("-date", "-start_time")

    def __str__(self) -> str:  # noqa: D401
        return f"{self.generator} - {self.date}"


class FuelEntry(models.Model):
    """
    Fuel top-up / refill log for generators.
    """

    date_of_filling = models.DateField(default=timezone.now)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="fuel_entries")
    generator = models.ForeignKey(Generator, on_delete=models.CASCADE, related_name="fuel_entries")
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, default=FuelType.DIESEL)
    litres_filled = models.DecimalField(max_digits=10, decimal_places=2)
    fuel_rate_per_litre = models.DecimalField(max_digits=10, decimal_places=2)
    total_fuel_cost = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    vendor_name = models.CharField(max_length=255, blank=True, null=True)
    filled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generator_fuel_entries",
    )
    comments = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Fuel Entry"
        verbose_name_plural = "Fuel Entries"
        ordering = ("-date_of_filling",)

    def save(self, *args, **kwargs):  # noqa: D401
        """
        Auto-calculate total cost before saving.
        """
        if self.litres_filled and self.fuel_rate_per_litre:
            self.total_fuel_cost = (self.litres_filled * self.fuel_rate_per_litre).quantize(
                Decimal("0.01")
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # noqa: D401
        return f"{self.generator} - {self.date_of_filling}"


class MaintenanceLog(models.Model):
    """
    Service / maintenance history for a generator.
    """

    generator = models.ForeignKey(Generator, on_delete=models.CASCADE, related_name="maintenance_logs")
    date_of_service = models.DateField(default=timezone.now)
    service_type = models.CharField(max_length=255, help_text="Type of service carried out")
    next_scheduled_maintenance = models.DateField(blank=True, null=True)
    service_provider = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        verbose_name = "Maintenance Log"
        verbose_name_plural = "Maintenance Logs"
        ordering = ("-date_of_service",)

    def __str__(self) -> str:  # noqa: D401
        return f"{self.generator} - {self.date_of_service}"

