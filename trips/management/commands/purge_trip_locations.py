"""
Management command to delete old TripLocation records for completed trips.

Usage:
    python manage.py purge_trip_locations            # delete records older than 90 days
    python manage.py purge_trip_locations --days 30  # custom retention window
    python manage.py purge_trip_locations --dry-run  # preview without deleting
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = "Purge GPS location points older than N days for completed/cancelled trips."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=f"Retain records this many days back (default: {DEFAULT_RETENTION_DAYS})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print how many records would be deleted without actually deleting.",
        )

    def handle(self, *args, **options):
        from trips.gps_models import TripLocation

        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(days=days)

        qs = TripLocation.objects.filter(
            timestamp__lt=cutoff,
            trip__status__in=["completed", "cancelled"],
        )

        count = qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] Would delete {count:,} TripLocation records older than {days} days."
                )
            )
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No records to purge."))
            return

        deleted, _ = qs.delete()
        msg = f"Purged {deleted:,} TripLocation records older than {days} days."
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)
