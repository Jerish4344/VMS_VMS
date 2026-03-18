"""
Management command to archive old LocationHistory records.

Moves records older than --days (default 90) to keep the main table fast.
Deletes archived records to free disk space.

Usage:
    python manage.py archive_location_history              # dry-run (default)
    python manage.py archive_location_history --execute     # actually delete
    python manage.py archive_location_history --days 60     # custom threshold
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from geolocation.models import LocationHistory


class Command(BaseCommand):
    help = 'Archive (delete) LocationHistory records older than N days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete records older than this many days (default: 90)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10000,
            help='Number of records to delete per batch (default: 10000)',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Actually delete records. Without this flag, only shows what would be deleted.',
        )

    def handle(self, *args, **options):
        days = options['days']
        batch_size = options['batch_size']
        execute = options['execute']
        cutoff = timezone.now() - timedelta(days=days)

        total = LocationHistory.objects.filter(device_time__lt=cutoff).count()
        self.stdout.write(f"Found {total:,} LocationHistory records older than {days} days (before {cutoff.date()})")

        if not execute:
            self.stdout.write(self.style.WARNING(
                "Dry run — no records deleted. Use --execute to actually delete."
            ))
            return

        deleted_total = 0
        while True:
            # Delete in batches to avoid locking the table for too long
            ids = list(
                LocationHistory.objects
                .filter(device_time__lt=cutoff)
                .values_list('id', flat=True)[:batch_size]
            )
            if not ids:
                break
            count, _ = LocationHistory.objects.filter(id__in=ids).delete()
            deleted_total += count
            self.stdout.write(f"  Deleted batch: {count:,} (total so far: {deleted_total:,})")

        self.stdout.write(self.style.SUCCESS(f"Done. Deleted {deleted_total:,} records."))
