from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='trips.Trip')
def sync_sor_distance(sender, instance, **kwargs):
    """Keep the linked SOR entry's distance_km in sync with the trip."""
    from sor.models import SOR

    try:
        sor = SOR.objects.get(trip=instance)
    except SOR.DoesNotExist:
        return

    if instance.end_odometer and instance.start_odometer:
        new_distance = instance.end_odometer - instance.start_odometer
    else:
        new_distance = None

    if sor.distance_km != new_distance:
        sor.distance_km = new_distance
        sor.save(update_fields=['distance_km'])
