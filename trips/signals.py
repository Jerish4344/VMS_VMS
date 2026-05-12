from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='trips.Trip')
def sync_sor_distance(sender, instance, **kwargs):
    """Keep the linked SOR entry's distance_km in sync with the trip.

    Only applies to legacy single-SOR trips. Trips that belong to an SOR
    bundle have multiple SORs sharing the same trip, and each SOR tracks
    its own per-leg distance from its own odometer readings — so we skip
    the auto-sync in that case to avoid overwriting per-SOR distances
    (and to avoid MultipleObjectsReturned).
    """
    from sor.models import SOR

    sors = SOR.objects.filter(trip=instance)
    if sors.count() != 1:
        return
    sor = sors.first()

    if instance.end_odometer and instance.start_odometer:
        new_distance = instance.end_odometer - instance.start_odometer
    else:
        new_distance = None

    if sor.distance_km != new_distance:
        sor.distance_km = new_distance
        sor.save(update_fields=['distance_km'])
