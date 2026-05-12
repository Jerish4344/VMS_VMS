"""Prune old notifications to keep tables small.

Defaults:
  - Delete READ notifications older than 30 days.
  - Delete ALL notifications older than 90 days.

Targets both `dashboard.Notification` and `sor.SORNotification`.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete old notifications (read >30d, all >90d)."

    def add_arguments(self, parser):
        parser.add_argument('--read-days', type=int, default=30,
                            help='Delete READ notifications older than N days (default 30).')
        parser.add_argument('--all-days', type=int, default=90,
                            help='Delete ALL notifications older than N days (default 90).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be deleted without deleting.')

    def handle(self, *args, **opts):
        from dashboard.models import Notification
        from sor.notification import SORNotification

        now = timezone.now()
        read_cutoff = now - timedelta(days=opts['read_days'])
        all_cutoff = now - timedelta(days=opts['all_days'])

        targets = [
            ('dashboard.Notification', Notification, 'timestamp', 'read'),
            ('sor.SORNotification', SORNotification, 'created_at', 'is_read'),
        ]

        for label, model, ts_field, read_field in targets:
            read_qs = model.objects.filter(**{
                f'{ts_field}__lt': read_cutoff,
                read_field: True,
            })
            all_qs = model.objects.filter(**{f'{ts_field}__lt': all_cutoff})

            read_count = read_qs.count()
            all_count = all_qs.count()

            if opts['dry_run']:
                self.stdout.write(f"[dry-run] {label}: would delete {read_count} read (>{opts['read_days']}d) "
                                  f"+ {all_count} total (>{opts['all_days']}d)")
                continue

            r1, _ = read_qs.delete()
            r2, _ = all_qs.delete()
            self.stdout.write(self.style.SUCCESS(
                f"{label}: deleted {r1} read + {r2} aged"
            ))
