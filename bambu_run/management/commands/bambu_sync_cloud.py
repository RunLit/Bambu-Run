"""
Management command: bambu_sync_cloud

Backfill BambuCloudTask records from the Bambu Cloud API and link them to
existing PrintJob records. Primarily useful for jobs created before this
feature existed, or for re-syncing if the collector was offline at job end.

Usage:
    python manage.py bambu_sync_cloud
    python manage.py bambu_sync_cloud --limit 100
    python manage.py bambu_sync_cloud --dry-run
"""

import logging
import os

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill BambuCloudTask records from Bambu Cloud API and link to PrintJob"

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=20,
            help='Number of recent cloud tasks to fetch (default: 20)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be synced without writing to DB'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']

        bambu_token = os.environ.get('BAMBU_TOKEN')
        bambu_username = os.environ.get('BAMBU_USERNAME')
        bambu_password = os.environ.get('BAMBU_PASSWORD')

        if not bambu_token and not all([bambu_username, bambu_password]):
            raise CommandError(
                "Either BAMBU_TOKEN or both BAMBU_USERNAME and BAMBU_PASSWORD must be set"
            )

        try:
            from bambulab import BambuClient
            from bambulab.auth import BambuAuthenticator
        except ImportError:
            raise CommandError("bambu-lab-cloud-api is not installed")

        if bambu_token:
            client = BambuClient(token=bambu_token)
        else:
            auth = BambuAuthenticator()
            token = auth.login(bambu_username, bambu_password)
            client = BambuClient(token=token)

        from bambu_run.bambu_cloud import get_tasks, upsert_cloud_task
        from bambu_run.models import PrintJob

        self.stdout.write(f"Fetching last {limit} tasks from Bambu Cloud...")
        try:
            response = get_tasks(client, limit=limit)
        except Exception as e:
            raise CommandError(f"Cloud API request failed: {e}")

        hits = response.get('hits', response.get('tasks', []))
        self.stdout.write(f"Got {len(hits)} tasks from cloud")

        created_count = updated_count = linked_count = 0

        for task_dict in hits:
            task_id = task_dict.get('id')
            design_title = task_dict.get('designTitle') or ''
            plate_title = task_dict.get('title') or ''
            display_name = design_title or plate_title or f"task-{task_id}"

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] Would upsert task {task_id}: {display_name!r}"
                )
                # Check if we'd link to a PrintJob
                job = PrintJob.objects.filter(cloud_task_id_raw=task_id).first()
                if job:
                    self.stdout.write(f"    → would link to PrintJob #{job.id}")
                continue

            try:
                cloud_task, created = upsert_cloud_task(task_dict)
                if created:
                    created_count += 1
                    self.stdout.write(f"  Created: {display_name!r} (task {task_id})")
                else:
                    updated_count += 1

                # Link to any matching PrintJob by cloud_task_id_raw
                linked = PrintJob.objects.filter(
                    cloud_task_id_raw=task_id, cloud_task__isnull=True
                ).update(cloud_task=cloud_task)
                if linked:
                    linked_count += linked
                    self.stdout.write(f"    Linked {linked} PrintJob(s) for task {task_id}")

                # Historical backfill: match by cloud start_time ± 2 min + device serial
                if cloud_task.cloud_start_time and cloud_task.device_serial:
                    from datetime import timedelta
                    from bambu_run.models import Printer
                    printer = Printer.objects.filter(
                        serial_number=cloud_task.device_serial
                    ).first()
                    if printer:
                        window_start = cloud_task.cloud_start_time - timedelta(minutes=5)
                        window_end = cloud_task.cloud_start_time + timedelta(minutes=5)
                        historical = PrintJob.objects.filter(
                            device=printer,
                            start_time__gte=window_start,
                            start_time__lte=window_end,
                            cloud_task__isnull=True,
                        ).update(cloud_task=cloud_task)
                        if historical:
                            linked_count += historical
                            self.stdout.write(
                                f"    Historically linked {historical} PrintJob(s) by time for task {task_id}"
                            )

            except Exception as e:
                self.stderr.write(f"  Error processing task {task_id}: {e}")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone: {created_count} created, {updated_count} updated, "
                    f"{linked_count} PrintJob(s) linked"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("\nDry run complete — no changes written"))
