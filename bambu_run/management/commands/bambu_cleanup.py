"""
Management command to clean up old FilamentSnapshot records.

Usage:
    python manage.py bambu_cleanup --days 90 --dry-run
    python manage.py bambu_cleanup --days 180
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bambu_run.models import FilamentSnapshot, PrinterMetrics

logger = logging.getLogger("bambu_run.cleanup")


class Command(BaseCommand):
    help = "Clean up old FilamentSnapshot records to save database space"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=90,
            help="Delete snapshots older than X days (default: 90)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--keep-print-jobs", action="store_true",
            help="Keep snapshots linked to print jobs even if old",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        keep_print_jobs = options["keep_print_jobs"]

        cutoff_date = timezone.now() - timedelta(days=days)

        self.stdout.write(f"Cleaning up FilamentSnapshots older than {days} days")
        self.stdout.write(f"Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")

        old_snapshots = FilamentSnapshot.objects.filter(
            printer_metric__timestamp__lt=cutoff_date
        )

        if keep_print_jobs:
            old_snapshots = old_snapshots.exclude(
                printer_metric__started_jobs__isnull=False
            ).exclude(
                printer_metric__ended_jobs__isnull=False
            )

        count = old_snapshots.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No snapshots to delete."))
            return

        space_mb = (count * 391) / (1024 * 1024)

        self.stdout.write(f"\nSnapshots to delete: {count:,}")
        self.stdout.write(f"Estimated space saved: {space_mb:.2f} MB")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - Nothing deleted"))

            sample = old_snapshots[:10]
            self.stdout.write("\nSample of snapshots to delete:")
            for snap in sample:
                self.stdout.write(
                    f"  - {snap.printer_metric.timestamp} | "
                    f"Tray {snap.tray_id} | {snap.type or 'Empty'} | "
                    f"{snap.remain_percent}%"
                )
            if count > 10:
                self.stdout.write(f"  ... and {count - 10:,} more")
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nThis will permanently delete {count:,} snapshot records!"
                )
            )
            confirm = input("Type 'DELETE' to confirm: ")

            if confirm != "DELETE":
                self.stdout.write(self.style.ERROR("Cancelled."))
                return

            batch_size = 1000
            deleted_total = 0

            with transaction.atomic():
                while True:
                    batch_ids = list(
                        old_snapshots.values_list('id', flat=True)[:batch_size]
                    )
                    if not batch_ids:
                        break

                    deleted = FilamentSnapshot.objects.filter(id__in=batch_ids).delete()
                    deleted_count = deleted[0]
                    deleted_total += deleted_count

                    self.stdout.write(
                        f"Deleted {deleted_total:,} / {count:,} snapshots...",
                        ending='\r'
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully deleted {deleted_total:,} snapshots "
                    f"({space_mb:.2f} MB freed)"
                )
            )

            self.stdout.write("\nChecking for orphaned PrinterMetrics...")
            orphaned_metrics = PrinterMetrics.objects.filter(
                timestamp__lt=cutoff_date,
                filament_snapshots__isnull=True
            )

            metrics_count = orphaned_metrics.count()
            if metrics_count > 0:
                metrics_space_mb = (metrics_count * 1500) / (1024 * 1024)
                self.stdout.write(
                    f"Found {metrics_count:,} orphaned PrinterMetrics "
                    f"({metrics_space_mb:.2f} MB)"
                )

                if input("Delete these too? (y/N): ").lower() == 'y':
                    orphaned_metrics.delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Deleted {metrics_count:,} orphaned metrics"
                        )
                    )
