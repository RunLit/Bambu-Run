"""list_print_jobs, get_print_job, get_print_statistics -- the
read_print_history capability tools."""
from __future__ import annotations

import statistics
from datetime import timedelta

from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.utils import timezone

from bambu_run.mcp.shapes import display_name, normalize_consumed, resolve_printer
from bambu_run.models import BambuCloudTask, FilamentUsage, Filament, PrintJob


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
    now = timezone.now()
    qs = PrintJob.objects.select_related("cloud_task", "device")
    if printer is not None:
        qs = qs.filter(device__in=resolve_printer(printer))
    since = now - timedelta(days=days)
    qs = qs.filter(start_time__gte=since)
    if status == "running":
        qs = qs.filter(final_status__isnull=True)
    elif status:
        qs = qs.filter(final_status=status)
    if name_contains:
        qs = qs.filter(project_name__icontains=name_contains)

    jobs = list(qs.order_by("-start_time")[:limit])
    return {"generated_at": now.isoformat(), "jobs": [_job_summary(j) for j in jobs]}


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
    now = timezone.now()
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
        "generated_at": now.isoformat(),
        "estimate_delta_percent": delta_percent,
        "filament_usages": usages,
        "cloud_design_title": cloud.design_title if cloud else None,
        "cover_url": cloud.cover_url if cloud and cloud.cover_url else None,
    }


def get_print_statistics(days: int = 30, printer: str | int | None = None) -> dict:
    """Aggregate print analytics over a window: success rate, total time and
    filament, estimate accuracy, failure patterns, and material mix.

    cost_total is always null in this phase -- cost_available: false tells
    the agent to explain the gap rather than report zero spend.
    most_used_material answers "what did I print most" directly for the
    requested window (days=7 for last week, days=30 for last month).
    """
    now = timezone.now()
    since = now - timedelta(days=days)
    qs = PrintJob.objects.filter(start_time__gte=since)
    if printer is not None:
        qs = qs.filter(device__in=resolve_printer(printer))

    total_jobs = qs.count()
    status_counts = {
        (row["final_status"] or "running"): row["n"]
        for row in qs.values("final_status").annotate(n=Count("id"))
    }
    finished = status_counts.get("FINISH", 0)
    success_rate = round(finished / total_jobs, 3) if total_jobs else None

    total_duration = qs.aggregate(s=Sum("duration_minutes"))["s"] or 0

    cloud_qs = BambuCloudTask.objects.filter(print_jobs__in=qs).distinct()
    total_grams = cloud_qs.aggregate(s=Sum("weight_grams"))["s"]
    jobs_without_cloud = qs.filter(cloud_task__isnull=True).count()

    # Same exclusion rules as normalize_consumed (starting_percent must be a
    # real reading, and consumption must be non-negative), expressed as a DB
    # filter -- a Python helper can't run inside an aggregate expression.
    valid_usage = (
        Q(starting_percent__gt=F("ending_percent"))
        & ~Q(starting_percent=-1)
        & ~Q(ending_percent=-1)
        & Q(filament__initial_weight_grams__isnull=False)
    )
    material_rows = (
        FilamentUsage.objects.filter(print_job__in=qs)
        .filter(valid_usage)
        .annotate(
            grams=ExpressionWrapper(
                (F("starting_percent") - F("ending_percent")) * F("filament__initial_weight_grams") / 100.0,
                output_field=FloatField(),
            )
        )
        .values("filament__type")
        .annotate(total_grams=Sum("grams"))
        .order_by("-total_grams")
    )
    material_mix = {row["filament__type"]: round(row["total_grams"], 2) for row in material_rows if row["filament__type"]}
    most_used_material = next(iter(material_mix), None)

    failed = qs.filter(final_status="FAILED")
    failure_names = list(failed.values("project_name").annotate(n=Count("id")).order_by("-n")[:5])

    ratio_qs = qs.filter(
        duration_minutes__isnull=False, cloud_task__cost_time_seconds__gt=0
    ).annotate(
        ratio=ExpressionWrapper(
            F("duration_minutes") / (F("cloud_task__cost_time_seconds") / 60.0),
            output_field=FloatField(),
        )
    )
    mean_ratio = ratio_qs.aggregate(avg=Avg("ratio"))["avg"]
    # median has no portable DB-level equivalent across backends; this list
    # is already bounded by the same days/printer filters as everything else.
    ratios = list(ratio_qs.values_list("ratio", flat=True))
    median_ratio = statistics.median(ratios) if ratios else None

    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "total_jobs": total_jobs,
        "success_rate": success_rate,
        "status_counts": status_counts,
        "total_print_minutes": total_duration,
        "total_filament_grams": float(total_grams) if total_grams is not None else None,
        "jobs_without_cloud_data": jobs_without_cloud,
        "estimate_accuracy": {
            "mean_ratio": round(mean_ratio, 2) if mean_ratio is not None else None,
            "median_ratio": round(median_ratio, 2) if median_ratio is not None else None,
        },
        "failures": {
            "count": failed.count(),
            "top_failing_projects": [{"name": f["project_name"], "count": f["n"]} for f in failure_names],
        },
        "material_mix_grams": material_mix,
        "most_used_material": most_used_material,
        "cost_total": None,
        "cost_available": False,
    }
