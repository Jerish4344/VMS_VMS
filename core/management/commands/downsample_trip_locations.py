"""Downsample raw GPS pings on older trips to keep `trips_triplocation` small.

Strategy: for each completed/cancelled trip whose end_time is older than
``--older-than-days``, walk its points in chronological order and KEEP a
point only if BOTH:
    - it is at least ``--interval-seconds`` after the previously kept point, OR
    - it is at least ``--interval-meters`` from the previously kept point.

The very first and very last point of every trip are always kept so the
route still renders cleanly. Everything else is deleted.

`GPSTrackingSession` totals (gps_distance, total_points, etc.) are NOT
recomputed — they were captured at trip end and remain authoritative.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Thin out old TripLocation rows down to one point per N seconds / M metres."

    def add_arguments(self, parser):
        parser.add_argument('--older-than-days', type=int, default=7,
                            help='Only downsample trips ended more than N days ago (default 7).')
        parser.add_argument('--interval-seconds', type=int, default=60,
                            help='Minimum time gap to keep a point (default 60).')
        parser.add_argument('--interval-meters', type=float, default=100.0,
                            help='Minimum distance gap to keep a point (default 100m).')
        parser.add_argument('--max-trips', type=int, default=0,
                            help='Process at most this many trips (0 = no limit).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be deleted without deleting.')

    def handle(self, *args, **opts):
        from trips.models import Trip
        from trips.gps_models import TripLocation

        cutoff = timezone.now() - timedelta(days=opts['older_than_days'])
        min_seconds = opts['interval_seconds']
        min_km = opts['interval_meters'] / 1000.0
        dry_run = opts['dry_run']

        trips_qs = Trip.objects.filter(
            status__in=['completed', 'cancelled'],
            end_time__lt=cutoff,
            gps_locations__isnull=False,
        ).distinct().only('id').order_by('id')

        if opts['max_trips']:
            trips_qs = trips_qs[:opts['max_trips']]

        total_trips = trips_qs.count()
        self.stdout.write(
            f"Scanning {total_trips} trips ended before {cutoff.date()} "
            f"(keep 1 point per {min_seconds}s OR {opts['interval_meters']:.0f}m)..."
        )

        total_kept = 0
        total_deleted = 0
        trips_touched = 0

        for trip in trips_qs.iterator(chunk_size=200):
            points = list(
                TripLocation.objects.filter(trip_id=trip.id)
                .order_by('timestamp')
                .values('id', 'latitude', 'longitude', 'timestamp')
            )
            if len(points) <= 2:
                total_kept += len(points)
                continue

            keep_ids = {points[0]['id'], points[-1]['id']}
            last = points[0]
            for p in points[1:-1]:
                gap_s = (p['timestamp'] - last['timestamp']).total_seconds()
                dist_km = TripLocation.calculate_distance(
                    last['latitude'], last['longitude'],
                    p['latitude'], p['longitude'],
                )
                if gap_s >= min_seconds or dist_km >= min_km:
                    keep_ids.add(p['id'])
                    last = p

            delete_ids = [p['id'] for p in points if p['id'] not in keep_ids]
            if not delete_ids:
                total_kept += len(points)
                continue

            kept = len(points) - len(delete_ids)
            total_kept += kept
            total_deleted += len(delete_ids)
            trips_touched += 1

            if not dry_run:
                # Delete in chunks of 1000 to avoid huge IN clauses.
                for i in range(0, len(delete_ids), 1000):
                    batch = delete_ids[i:i + 1000]
                    with transaction.atomic():
                        TripLocation.objects.filter(id__in=batch).delete()

            if trips_touched % 100 == 0:
                self.stdout.write(
                    f"  ...{trips_touched} trips processed, "
                    f"{total_deleted:,} pts {'would be ' if dry_run else ''}deleted, "
                    f"{total_kept:,} kept"
                )

        verb = 'Would delete' if dry_run else 'Deleted'
        self.stdout.write(self.style.SUCCESS(
            f"Done. Trips touched: {trips_touched}/{total_trips}. "
            f"{verb} {total_deleted:,} points; kept {total_kept:,}."
        ))
