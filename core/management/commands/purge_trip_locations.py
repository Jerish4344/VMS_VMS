"""Delete raw GPS pings (`TripLocation`) older than N days for completed trips.

The session statistics on `GPSTrackingSession` (total distance, points, gaps)
are preserved; only the raw point cloud is removed.

Default retention: 90 days. Deletes in chunks to avoid lock contention.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete raw TripLocation rows older than N days for completed trips."

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90,
                            help='Retention window in days (default 90).')
        parser.add_argument('--chunk', type=int, default=5000,
                            help='Delete batch size (default 5000).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report counts without deleting.')

    def handle(self, *args, **opts):
        from trips.gps_models import TripLocation

        cutoff = timezone.now() - timedelta(days=opts['days'])
        qs = TripLocation.objects.filter(
            timestamp__lt=cutoff,
            trip__status__in=['completed', 'cancelled'],
        )

        total = qs.count()
        self.stdout.write(f"Eligible TripLocation rows older than {opts['days']}d: {total}")

        if opts['dry_run'] or total == 0:
            return

        deleted = 0
        chunk = opts['chunk']
        while True:
            ids = list(qs.values_list('id', flat=True)[:chunk])
            if not ids:
                break
            with transaction.atomic():
                d, _ = TripLocation.objects.filter(id__in=ids).delete()
            deleted += d
            self.stdout.write(f"  deleted {deleted}/{total} ...")

        self.stdout.write(self.style.SUCCESS(f"Done. Deleted {deleted} TripLocation rows."))
