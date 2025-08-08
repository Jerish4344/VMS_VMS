"""
Admin configuration for the *generators* app.

Each model gets a tailored admin class with sensible defaults:
• list_display – Essential, high-value fields for quick scanning
• list_filter  – High-level filters for narrowing down data
• search_fields – Common text fields useful for search
• inlines      – Operational logs embedded inside the Generator admin
"""

from django.contrib import admin

from . import models

# --------------------------------------------------------------------------- #
#  Inline definitions
# --------------------------------------------------------------------------- #


class UsageTrackingInline(admin.TabularInline):
    model = models.UsageTracking
    extra = 0
    fields = (
        "date",
        "start_time",
        "end_time",
        "total_hours_run",
        "reason_for_use",
    )
    readonly_fields = ("total_hours_run",)
    can_delete = False


class FuelEntryInline(admin.TabularInline):
    model = models.FuelEntry
    extra = 0
    fields = (
        "date_of_filling",
        "fuel_type",
        "litres_filled",
        "fuel_rate_per_litre",
        "total_fuel_cost",
    )
    readonly_fields = ("total_fuel_cost",)
    can_delete = False


class MaintenanceLogInline(admin.TabularInline):
    model = models.MaintenanceLog
    extra = 0
    fields = (
        "date_of_service",
        "service_type",
        "next_scheduled_maintenance",
        "service_provider",
        "amount",
    )
    can_delete = False


# --------------------------------------------------------------------------- #
#  Admin classes
# --------------------------------------------------------------------------- #


@admin.register(models.Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "manager_name", "contact_info")
    search_fields = ("name", "location", "manager_name", "contact_info")
    list_filter = ("location",)


@admin.register(models.Generator)
class GeneratorAdmin(admin.ModelAdmin):
    list_display = (
        "store",
        "make_and_model",
        "capacity_kva",
        "fuel_type",
        "serial_number",
    )
    list_filter = ("store", "fuel_type")
    search_fields = ("make_and_model", "serial_number")
    inlines = (UsageTrackingInline, FuelEntryInline, MaintenanceLogInline)
    list_select_related = ("store",)


@admin.register(models.UsageTracking)
class UsageTrackingAdmin(admin.ModelAdmin):
    list_display = (
        "generator",
        "date",
        "start_time",
        "end_time",
        "total_hours_run",
        "reason_for_use",
    )
    list_filter = ("date", "generator__store")
    search_fields = ("generator__make_and_model", "reason_for_use")
    list_select_related = ("generator",)


@admin.register(models.FuelEntry)
class FuelEntryAdmin(admin.ModelAdmin):
    list_display = (
        "date_of_filling",
        "store",
        "generator",
        "fuel_type",
        "litres_filled",
        "fuel_rate_per_litre",
        "total_fuel_cost",
        "invoice_number",
        "vendor_name",
        "filled_by",
    )
    list_filter = ("date_of_filling", "fuel_type", "store")
    search_fields = (
        "invoice_number",
        "vendor_name",
        "generator__make_and_model",
    )
    readonly_fields = ("total_fuel_cost",)
    list_select_related = ("store", "generator", "filled_by")


@admin.register(models.MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = (
        "generator",
        "date_of_service",
        "service_type",
        "next_scheduled_maintenance",
        "service_provider",
        "invoice_number",
        "amount",
    )
    list_filter = ("date_of_service", "service_provider")
    search_fields = ("service_type", "service_provider", "generator__make_and_model")
    list_select_related = ("generator",)

