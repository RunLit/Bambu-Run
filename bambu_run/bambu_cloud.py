"""
Thin wrapper around the Bambu Cloud HTTP API using verified endpoints only.

Uses BambuClient as the transport (auth headers, base URL) but bypasses
the package's named methods, which contain guessed/unverified endpoints.

All functions take a BambuClient instance as first argument.
"""

import logging
from datetime import timezone as dt_timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verified HTTP wrappers
# ---------------------------------------------------------------------------

def get_tasks(client, limit=20, offset=0):
    """Fetch recent cloud tasks. Returns the raw response dict."""
    return client.get('v1/user-service/my/tasks', params={'limit': limit, 'offset': offset})


def get_profile(client):
    """Fetch the authenticated user's profile."""
    return client.get('v1/user-service/my/profile')


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def _parse_cloud_dt(value):
    """Parse an ISO-8601 string like '2026-03-28T12:38:29Z' to aware datetime."""
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone
    dt = parse_datetime(value)
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt


def upsert_cloud_task(task_dict):
    """
    Parse one task dict from the cloud API and upsert into BambuCloudTask.

    Returns the (BambuCloudTask instance, created bool) tuple.
    """
    from .models import BambuCloudTask

    task_id = task_dict.get('id')
    if not task_id:
        raise ValueError("task_dict has no 'id' field")

    defaults = {
        'design_id': task_dict.get('designId') or None,
        'design_title': task_dict.get('designTitle') or '',
        'plate_title': task_dict.get('title') or '',
        'model_id': task_dict.get('modelId') or '',
        'profile_id': task_dict.get('profileId') or None,
        'plate_index': task_dict.get('plateIndex'),
        'device_serial': task_dict.get('deviceId') or '',
        'cover_url': task_dict.get('cover') or '',
        'weight_grams': task_dict.get('weight'),
        'length_mm': task_dict.get('length'),
        'cost_time_seconds': task_dict.get('costTime'),
        'cloud_status': task_dict.get('status'),
        'bed_type': task_dict.get('bedType') or '',
        'use_ams': bool(task_dict.get('useAms', True)),
        'print_mode': task_dict.get('mode') or '',
        'ams_detail_mapping': task_dict.get('amsDetailMapping') or [],
        'cloud_start_time': _parse_cloud_dt(task_dict.get('startTime')),
        'cloud_end_time': _parse_cloud_dt(task_dict.get('endTime')),
        'raw_data': task_dict,
    }

    return BambuCloudTask.objects.update_or_create(task_id=task_id, defaults=defaults)


def fetch_and_upsert_task(client, print_job):
    """
    Called by bambu_collector at print finalization.

    Fetches recent tasks from cloud, finds the one matching print_job.cloud_task_id_raw,
    upserts BambuCloudTask, and wires up the FK on print_job.

    Non-fatal: all errors are logged as warnings only.
    """
    if not print_job.cloud_task_id_raw:
        logger.debug(f"Job #{print_job.id} has no cloud_task_id_raw — skipping cloud sync")
        return

    try:
        response = get_tasks(client, limit=20)
        hits = response.get('hits', response.get('tasks', []))
    except Exception as e:
        logger.warning(f"Cloud tasks fetch failed for job #{print_job.id}: {e}")
        return

    target = next((t for t in hits if t.get('id') == print_job.cloud_task_id_raw), None)
    if not target:
        logger.warning(
            f"Job #{print_job.id}: cloud task {print_job.cloud_task_id_raw} "
            f"not found in last {len(hits)} tasks from API"
        )
        return

    try:
        cloud_task, created = upsert_cloud_task(target)
        print_job.cloud_task = cloud_task
        print_job.save(update_fields=['cloud_task'])
        action = 'created' if created else 'updated'
        logger.info(
            f"Job #{print_job.id}: cloud task {print_job.cloud_task_id_raw} {action} "
            f"— design_title={cloud_task.design_title!r}"
        )
    except Exception as e:
        logger.warning(f"Cloud task upsert failed for job #{print_job.id}: {e}")
