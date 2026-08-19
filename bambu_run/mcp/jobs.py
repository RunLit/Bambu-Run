"""list_print_jobs, get_print_job, get_print_statistics -- the
read_print_history capability tools."""
from __future__ import annotations

import statistics
from datetime import timedelta

from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.utils import timezone

from bambu_run.mcp.shapes import display_name, normalize_consumed, resolve_printer
from bambu_run.models import BambuCloudTask, FilamentUsage, PrintJob


def list_print_jobs(
    status: str | None = None,
    days: int = 30,
    name_contains: str | None = None,
    printer: str | int | None = None,
    limit: int = 20,
) -> dict:
    """Print job history, most recent first.

    status filters on FINISH/FAILED/CANCELLED, or "running" for the
    in-flight job (final_status is null while printing). filament_grams
    prefers Bambu Cloud's reported weight over the noisier AMS percentage
    estimate -- check filament_grams_source ("cloud" vs None, meaning no
    cloud data) before trusting precision. cost is always null until
    filament purchase prices are recorded. limit has a hard ceiling of 100,
    independent of days -- a busy printer's older jobs simply won't be
    returned by one call; narrow days or increase limit deliberately.
    """
    limit = min(limit, 100)
    qs = PrintJob.objects.select_related("cloud_task", "device")
    if printer is not None:
        qs = qs.filter(device__in=resolve_printer(printer))
    since = timezone.now() - timedelta(days=days)
    qs = qs.filter(start_time__gte=since)
    if status == "running":
        qs = qs.filter(final_status__isnull=True)
    elif status:
        qs = qs.filter(final_status=status)
    if name_contains:
        qs = qs.filter(project_name__icontains=name_contains)

    jobs = list(qs.order_by("-start_time")[:limit])
    return {"jobs": [_job_summary(j) for j in jobs]}


def _job_summary(job):
    cloud = job.cloud_task
    est_min = int(cloud.cost_time_seconds / 60) if cloud and cloud.cost_time_seconds else None
    grams = None
    grams_source = None
    if cloud and cloud.weight_grams is not None:
        grams = float(cloud.weight_grams)
        grams_source = "cloud"
    return {
        "id": job.id,
        "display_name": display_name(
            cloud.design_title if cloud else "", cloud.plate_title if cloud else "", job.project_name
        ),
        "status": job.final_status,
        "printer": job.device.name,
        "started_at": job.start_time.isoformat(),
        "ended_at": job.end_time.isoformat() if job.end_time else None,
        "duration_min": job.duration_minutes,
        "estimated_duration_min": est_min,
        "layers_total": job.total_layers,
        "filament_grams": grams,
        "filament_grams_source": grams_source,
        "cost": None,
        "has_cover_image": bool(cloud and cloud.cover_url),
    }


def get_print_job(job_id: int) -> dict:
    """Full detail for one print job: the list_print_jobs fields plus
    per-slot filament breakdown, estimate-vs-actual delta, and linked cloud
    metadata. Raises PrintJob.DoesNotExist if job_id is unknown.
    """
    job = PrintJob.objects.select_related("cloud_task", "device").get(id=job_id)
    summary = _job_summary(job)

    delta_percent = None
    if summary["estimated_duration_min"] and summary["duration_min"]:
        delta_percent = round(
            100 * (summary["duration_min"] - summary["estimated_duration_min"])
            / summary["estimated_duration_min"],
            1,
        )

    usages = []
    for u in job.filament_usages.select_related("filament"):
        consumed_percent, consumed_grams, quality = normalize_consumed(
            u.starting_percent, u.ending_percent,
            u.filament.initial_weight_grams if u.filament else None,
        )
        usages.append({
            "tray_id": u.tray_id,
            "ams_unit_id": u.ams_unit_id,
            "filament_id": u.filament_id,
            "consumed_percent": consumed_percent,
            "consumed_grams": consumed_grams,
            "data_quality": quality,
            "is_primary": u.is_primary,
        })

    cloud = job.cloud_task
    return {
        **summary,
        "estimate_delta_percent": delta_percent,
        "filament_usages": usages,
        "cloud_design_title": cloud.design_title if cloud else None,
        "cover_url": cloud.cover_url if cloud and cloud.cover_url else None,
    }
