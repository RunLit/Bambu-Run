"""
Pure Django ORM query functions for MCP tools.

Zero dependency on the `mcp` package — returns markdown strings.
RAE can reuse these directly.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.utils import timezone

from .conf import app_settings


def _redact(value, label="[redacted]"):
    """Redact sensitive values if MCP_HIDE_SENSITIVE is enabled."""
    if app_settings.MCP_HIDE_SENSITIVE:
        return label
    return value


def _format_duration(minutes):
    """Format minutes into human-readable duration."""
    if minutes is None:
        return "Unknown"
    hours, mins = divmod(int(minutes), 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def _format_temp(temp):
    """Format temperature value."""
    if temp is None:
        return "N/A"
    return f"{temp}°C"


# ─── Tools ───────────────────────────────────────────────────────────────────


def get_printer_status(printer_id=None):
    """Current live status of printer(s) including temps, progress, AMS, errors."""
    from .models import Printer, PrinterMetrics

    printers = Printer.objects.filter(is_active=True)
    if printer_id:
        printers = printers.filter(id=printer_id)

    if not printers.exists():
        return "No printers found."

    parts = []
    for printer in printers:
        metric = PrinterMetrics.objects.filter(device=printer).first()
        if not metric:
            parts.append(f"## {printer.name}\n**No data available yet.**\n")
            continue

        state = metric.gcode_state or "Unknown"
        lines = [f"## Printer Status: {printer.name}"]
        lines.append(f"**Model**: {printer.model} | **Serial**: {_redact(printer.serial_number)}")
        lines.append(f"**IP**: {_redact(printer.ip_address)} | **Location**: {printer.location or 'N/A'}")
        lines.append(f"**State**: {state}")

        if metric.print_percent is not None and state == "RUNNING":
            layer_info = ""
            if metric.layer_num is not None and metric.total_layer_num:
                layer_info = f" (Layer {metric.layer_num}/{metric.total_layer_num})"
            lines.append(f"**Progress**: {metric.print_percent}%{layer_info}")
            if metric.subtask_name:
                lines.append(f"**Project**: {metric.subtask_name}")
            if metric.remaining_time_min:
                lines.append(f"**ETA**: {_format_duration(metric.remaining_time_min)} remaining")

        # Temperatures
        lines.append("")
        lines.append("### Temperatures")
        lines.append("| Component | Current | Target |")
        lines.append("|-----------|---------|--------|")
        lines.append(f"| Nozzle | {_format_temp(metric.nozzle_temp)} | {_format_temp(metric.nozzle_target_temp)} |")
        lines.append(f"| Bed | {_format_temp(metric.bed_temp)} | {_format_temp(metric.bed_target_temp)} |")
        lines.append(f"| Chamber | {_format_temp(metric.chamber_temp)} | - |")

        # AMS filaments from JSON
        if metric.filaments:
            lines.append("")
            lines.append("### AMS Slots")
            lines.append("| Slot | Material | Color | Remaining |")
            lines.append("|------|----------|-------|-----------|")
            for f in metric.filaments:
                slot = f.get("slot", "?")
                ftype = f.get("sub_type") or f.get("type", "?")
                color = f.get("color", "")
                color_display = f"#{color[:6]}" if color and len(color) >= 6 else "?"
                remain = f.get("remain_percent", "?")
                lines.append(f"| {slot} | {ftype} | {color_display} | {remain}% |")

        # Errors
        if metric.has_errors or metric.hms:
            lines.append("")
            lines.append("### Alerts")
            if metric.print_error:
                lines.append(f"- Print error code: {metric.print_error}")
            if metric.hms:
                for msg in metric.hms[:5]:
                    lines.append(f"- HMS: {msg}")

        lines.append(f"\n*Last updated: {metric.timestamp.strftime('%Y-%m-%d %H:%M:%S')}*")
        parts.append("\n".join(lines))

    return "\n\n---\n\n".join(parts)


def list_printers():
    """List all registered printers."""
    from .models import Printer

    printers = Printer.objects.all()
    if not printers.exists():
        return "No printers registered."

    lines = ["# Printers", ""]
    lines.append("| ID | Name | Model | Active | Serial | IP | Location |")
    lines.append("|----|------|-------|--------|--------|----|----------|")
    for p in printers:
        lines.append(
            f"| {p.id} | {p.name} | {p.model} | "
            f"{'Yes' if p.is_active else 'No'} | "
            f"{_redact(p.serial_number)} | {_redact(p.ip_address)} | "
            f"{p.location or '-'} |"
        )
    return "\n".join(lines)


def get_print_history(status=None, days=None, project_name=None, limit=20):
    """Print job history with optional filters."""
    from .models import PrintJob

    qs = PrintJob.objects.select_related("device")

    if status:
        qs = qs.filter(final_status__iexact=status)
    if days:
        cutoff = timezone.now() - timedelta(days=int(days))
        qs = qs.filter(start_time__gte=cutoff)
    if project_name:
        qs = qs.filter(project_name__icontains=project_name)

    jobs = qs[:int(limit)]
    if not jobs:
        return "No print jobs found matching the criteria."

    lines = ["# Print History", ""]
    lines.append("| ID | Project | Printer | Status | Progress | Duration | Started |")
    lines.append("|----|---------|---------|--------|----------|----------|---------|")
    for j in jobs:
        lines.append(
            f"| {j.id} | {j.project_name} | {j.device.name} | "
            f"{j.final_status or 'In Progress'} | {j.completion_percent}% | "
            f"{_format_duration(j.duration_minutes)} | "
            f"{j.start_time.strftime('%Y-%m-%d %H:%M')} |"
        )
    return "\n".join(lines)


def get_print_job_detail(job_id):
    """Single job detail including filament usage."""
    from .models import FilamentUsage, PrintJob

    try:
        job = PrintJob.objects.select_related("device").get(id=job_id)
    except PrintJob.DoesNotExist:
        return f"Print job #{job_id} not found."

    lines = [f"# Print Job: {job.project_name}", ""]
    lines.append(f"**Printer**: {job.device.name}")
    lines.append(f"**Status**: {job.final_status or 'In Progress'}")
    lines.append(f"**Progress**: {job.completion_percent}%")
    if job.gcode_file:
        lines.append(f"**G-code**: {job.gcode_file}")
    lines.append(f"**Started**: {job.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if job.end_time:
        lines.append(f"**Ended**: {job.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Duration**: {_format_duration(job.duration_minutes)}")
    if job.total_layers:
        lines.append(f"**Total Layers**: {job.total_layers}")

    # Filament usage
    usages = FilamentUsage.objects.select_related("filament").filter(print_job=job)
    if usages.exists():
        lines.append("")
        lines.append("### Filament Usage")
        lines.append("| Spool | Material | Color | Consumed | Grams |")
        lines.append("|-------|----------|-------|----------|-------|")
        for u in usages:
            f = u.filament
            lines.append(
                f"| {f.brand} {f.type} | {f.sub_type or f.type} | "
                f"{f.color} | {u.consumed_percent or 0}% | "
                f"{u.consumed_grams or '-'}g |"
            )

    return "\n".join(lines)


def list_filaments(type=None, brand=None, color=None, loaded_in_ams=None, low_filament=None):
    """Filament inventory with optional filters."""
    from .models import Filament

    qs = Filament.objects.all()
    if type:
        qs = qs.filter(type__iexact=type)
    if brand:
        qs = qs.filter(brand__icontains=brand)
    if color:
        qs = qs.filter(color__icontains=color)
    if loaded_in_ams is not None:
        qs = qs.filter(is_loaded_in_ams=loaded_in_ams)
    if low_filament:
        qs = qs.filter(remaining_percent__lte=20)

    filaments = qs[:50]
    if not filaments:
        return "No filaments found matching the criteria."

    lines = ["# Filament Inventory", ""]
    lines.append(f"*{qs.count()} spools total*\n")
    lines.append("| ID | Brand | Type | Color | Remaining | In AMS | Last Used |")
    lines.append("|----|-------|------|-------|-----------|--------|-----------|")
    for f in filaments:
        color_display = f"{f.color}"
        if f.color_hex:
            color_display += f" ({f.color_hex})"
        last_used = f.last_used.strftime("%Y-%m-%d") if f.last_used else "-"
        lines.append(
            f"| {f.id} | {f.brand} | {f.sub_type or f.type} | "
            f"{color_display} | {f.remaining_percent}% | "
            f"{'Yes' if f.is_loaded_in_ams else 'No'} | {last_used} |"
        )
    return "\n".join(lines)


def get_filament_detail(filament_id):
    """Single spool detail with usage history."""
    from .models import Filament, FilamentUsage

    try:
        f = Filament.objects.get(id=filament_id)
    except Filament.DoesNotExist:
        return f"Filament #{filament_id} not found."

    lines = [f"# Filament: {f.brand} {f.type} - {f.color}", ""]
    lines.append(f"**Type**: {f.sub_type or f.type}")
    lines.append(f"**Brand**: {f.brand}")
    lines.append(f"**Color**: {f.color} ({f.color_hex or 'N/A'})")
    lines.append(f"**Remaining**: {f.remaining_percent}%")
    if f.remaining_weight_grams:
        lines.append(f"**Remaining Weight**: {f.remaining_weight_grams}g / {f.initial_weight_grams or '?'}g")
    lines.append(f"**In AMS**: {'Yes (slot ' + str(f.current_tray_id) + ')' if f.is_loaded_in_ams else 'No'}")
    lines.append(f"**Created By**: {f.created_by}")
    if f.tray_uuid:
        lines.append(f"**Serial**: {_redact(f.tray_uuid)}")
    if f.purchase_date:
        lines.append(f"**Purchased**: {f.purchase_date}")
    if f.notes:
        lines.append(f"**Notes**: {f.notes}")

    # Usage history
    usages = FilamentUsage.objects.select_related("print_job").filter(filament=f).order_by("-print_job__start_time")[:10]
    if usages.exists():
        lines.append("")
        lines.append("### Recent Print Usage")
        lines.append("| Job | Date | Consumed | Grams |")
        lines.append("|-----|------|----------|-------|")
        for u in usages:
            lines.append(
                f"| {u.print_job.project_name} | "
                f"{u.print_job.start_time.strftime('%Y-%m-%d')} | "
                f"{u.consumed_percent or 0}% | {u.consumed_grams or '-'}g |"
            )

    return "\n".join(lines)


def get_temperature_history(printer_id=None, hours=6, metric="all"):
    """Temperature trends as summary stats (avg/min/max) over recent hours."""
    from .models import Printer, PrinterMetrics

    cutoff = timezone.now() - timedelta(hours=int(hours))

    qs = PrinterMetrics.objects.filter(timestamp__gte=cutoff)
    if printer_id:
        qs = qs.filter(device_id=printer_id)

    if not qs.exists():
        return f"No temperature data in the last {hours} hours."

    printers = Printer.objects.filter(
        id__in=qs.values_list("device_id", flat=True).distinct()
    )

    parts = [f"# Temperature History (last {hours}h)", ""]
    for printer in printers:
        pqs = qs.filter(device=printer)
        stats = pqs.aggregate(
            nozzle_avg=Avg("nozzle_temp"),
            nozzle_min=Min("nozzle_temp"),
            nozzle_max=Max("nozzle_temp"),
            bed_avg=Avg("bed_temp"),
            bed_min=Min("bed_temp"),
            bed_max=Max("bed_temp"),
            chamber_avg=Avg("chamber_temp"),
            chamber_min=Min("chamber_temp"),
            chamber_max=Max("chamber_temp"),
        )

        parts.append(f"## {printer.name}")
        parts.append(f"*{pqs.count()} data points*\n")
        parts.append("| Sensor | Avg | Min | Max |")
        parts.append("|--------|-----|-----|-----|")

        if metric in ("all", "nozzle"):
            parts.append(
                f"| Nozzle | {_format_temp(stats['nozzle_avg'])} | "
                f"{_format_temp(stats['nozzle_min'])} | {_format_temp(stats['nozzle_max'])} |"
            )
        if metric in ("all", "bed"):
            parts.append(
                f"| Bed | {_format_temp(stats['bed_avg'])} | "
                f"{_format_temp(stats['bed_min'])} | {_format_temp(stats['bed_max'])} |"
            )
        if metric in ("all", "chamber"):
            parts.append(
                f"| Chamber | {_format_temp(stats['chamber_avg'])} | "
                f"{_format_temp(stats['chamber_min'])} | {_format_temp(stats['chamber_max'])} |"
            )
        parts.append("")

    return "\n".join(parts)


def get_filament_usage_stats(days=30, group_by="type"):
    """Aggregate filament consumption statistics."""
    from .models import FilamentUsage

    cutoff = timezone.now() - timedelta(days=int(days))
    qs = FilamentUsage.objects.filter(
        print_job__start_time__gte=cutoff,
        consumed_grams__isnull=False,
    ).select_related("filament")

    if not qs.exists():
        return f"No filament usage data in the last {days} days."

    lines = [f"# Filament Usage Stats (last {days} days)", ""]

    if group_by == "type":
        stats = (
            qs.values("filament__type")
            .annotate(
                total_grams=Sum("consumed_grams"),
                total_percent=Sum("consumed_percent"),
                job_count=Count("print_job", distinct=True),
            )
            .order_by("-total_grams")
        )
        lines.append("| Type | Total Grams | Jobs | Avg Grams/Job |")
        lines.append("|------|-------------|------|---------------|")
        for s in stats:
            avg = s["total_grams"] / s["job_count"] if s["job_count"] else 0
            lines.append(
                f"| {s['filament__type']} | {s['total_grams']}g | "
                f"{s['job_count']} | {avg:.0f}g |"
            )
    elif group_by == "color":
        stats = (
            qs.values("filament__color", "filament__type")
            .annotate(total_grams=Sum("consumed_grams"), job_count=Count("print_job", distinct=True))
            .order_by("-total_grams")
        )
        lines.append("| Color | Type | Total Grams | Jobs |")
        lines.append("|-------|------|-------------|------|")
        for s in stats:
            lines.append(
                f"| {s['filament__color']} | {s['filament__type']} | "
                f"{s['total_grams']}g | {s['job_count']} |"
            )
    elif group_by == "spool":
        stats = (
            qs.values("filament__id", "filament__brand", "filament__type", "filament__color")
            .annotate(total_grams=Sum("consumed_grams"), job_count=Count("print_job", distinct=True))
            .order_by("-total_grams")[:20]
        )
        lines.append("| Spool | Total Grams | Jobs |")
        lines.append("|-------|-------------|------|")
        for s in stats:
            lines.append(
                f"| {s['filament__brand']} {s['filament__type']} {s['filament__color']} | "
                f"{s['total_grams']}g | {s['job_count']} |"
            )

    return "\n".join(lines)


def get_printer_health(printer_id=None):
    """Diagnostics: errors, humidity, wifi, recent failed prints."""
    from .models import Printer, PrinterMetrics, PrintJob

    printers = Printer.objects.filter(is_active=True)
    if printer_id:
        printers = printers.filter(id=printer_id)

    if not printers.exists():
        return "No printers found."

    parts = ["# Printer Health Report", ""]
    for printer in printers:
        latest = PrinterMetrics.objects.filter(device=printer).first()
        if not latest:
            parts.append(f"## {printer.name}\n**No data available.**\n")
            continue

        parts.append(f"## {printer.name}")

        # Connectivity
        parts.append("### Connectivity")
        if latest.wifi_signal_dbm is not None:
            signal = latest.wifi_signal_dbm
            quality = "Excellent" if signal > -50 else "Good" if signal > -60 else "Fair" if signal > -70 else "Poor"
            parts.append(f"- WiFi: {signal} dBm ({quality})")
        parts.append(f"- Last seen: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        age = (timezone.now() - latest.timestamp).total_seconds()
        if age > 300:
            parts.append(f"- **Warning**: No data for {_format_duration(age / 60)}")

        # AMS environment
        if latest.ams_humidity is not None or latest.ams_temp is not None:
            parts.append("### AMS Environment")
            if latest.ams_humidity is not None:
                hum_status = "OK" if latest.ams_humidity < 5 else "High" if latest.ams_humidity < 8 else "Critical"
                parts.append(f"- Humidity: {latest.ams_humidity} ({hum_status})")
            if latest.ams_temp is not None:
                parts.append(f"- Temperature: {latest.ams_temp}°C")

        # HMS errors
        if latest.hms:
            parts.append("### Active HMS Alerts")
            for msg in latest.hms:
                parts.append(f"- {msg}")

        # Recent failures
        week_ago = timezone.now() - timedelta(days=7)
        failed = PrintJob.objects.filter(
            device=printer,
            start_time__gte=week_ago,
            final_status__in=["FAILED", "CANCELLED"],
        )
        if failed.exists():
            parts.append(f"### Recent Failures (7d): {failed.count()}")
            for job in failed[:5]:
                parts.append(f"- {job.project_name} ({job.final_status}) — {job.start_time.strftime('%m-%d %H:%M')}")

        # Success rate
        week_jobs = PrintJob.objects.filter(device=printer, start_time__gte=week_ago)
        total = week_jobs.count()
        if total > 0:
            success = week_jobs.filter(final_status="FINISH").count()
            parts.append(f"\n**7-day success rate**: {success}/{total} ({100 * success // total}%)")

        parts.append("")

    return "\n".join(parts)


def search_print_jobs(query):
    """Search print jobs by project name or gcode file."""
    from .models import PrintJob

    if not query:
        return "Please provide a search query."

    jobs = PrintJob.objects.select_related("device").filter(
        Q(project_name__icontains=query) | Q(gcode_file__icontains=query)
    )[:20]

    if not jobs:
        return f"No print jobs matching '{query}'."

    lines = [f"# Search Results: '{query}'", ""]
    lines.append(f"*{len(jobs)} results*\n")
    lines.append("| ID | Project | Printer | Status | Date |")
    lines.append("|----|---------|---------|--------|------|")
    for j in jobs:
        lines.append(
            f"| {j.id} | {j.project_name} | {j.device.name} | "
            f"{j.final_status or 'In Progress'} | {j.start_time.strftime('%Y-%m-%d')} |"
        )
    return "\n".join(lines)


def get_printing_summary(days=7):
    """High-level activity summary."""
    from .models import FilamentUsage, Printer, PrintJob

    cutoff = timezone.now() - timedelta(days=int(days))
    jobs = PrintJob.objects.filter(start_time__gte=cutoff)

    total = jobs.count()
    finished = jobs.filter(final_status="FINISH").count()
    failed = jobs.filter(final_status="FAILED").count()
    cancelled = jobs.filter(final_status="CANCELLED").count()
    in_progress = jobs.filter(final_status__isnull=True).count()

    total_minutes = jobs.filter(duration_minutes__isnull=False).aggregate(
        total=Sum("duration_minutes")
    )["total"] or 0

    total_grams = FilamentUsage.objects.filter(
        print_job__start_time__gte=cutoff,
        consumed_grams__isnull=False,
    ).aggregate(total=Sum("consumed_grams"))["total"] or 0

    lines = [f"# Printing Summary (last {days} days)", ""]
    lines.append(f"**Total Jobs**: {total}")
    lines.append(f"- Completed: {finished}")
    lines.append(f"- Failed: {failed}")
    lines.append(f"- Cancelled: {cancelled}")
    lines.append(f"- In Progress: {in_progress}")
    if total > 0:
        lines.append(f"- Success Rate: {100 * finished // total}%")
    lines.append(f"\n**Total Print Time**: {_format_duration(total_minutes)}")
    lines.append(f"**Total Filament Used**: {total_grams}g")

    # Most printed projects
    top_projects = (
        jobs.values("project_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )
    if top_projects:
        lines.append("\n### Most Printed")
        for p in top_projects:
            lines.append(f"- {p['project_name']} ({p['count']}x)")

    # Active printers
    active_printers = Printer.objects.filter(
        print_jobs__start_time__gte=cutoff
    ).distinct()
    if active_printers.exists():
        lines.append(f"\n**Active Printers**: {', '.join(p.name for p in active_printers)}")

    return "\n".join(lines)


def find_compatible_filament(type, min_remaining_percent=10, color=None):
    """Find spools matching material type criteria."""
    from .models import Filament

    qs = Filament.objects.filter(
        type__iexact=type,
        remaining_percent__gte=int(min_remaining_percent),
    )
    if color:
        qs = qs.filter(color__icontains=color)

    filaments = qs[:20]
    if not filaments:
        return f"No {type} filament found with >={min_remaining_percent}% remaining."

    lines = [f"# Compatible Filament: {type}", ""]
    if color:
        lines.append(f"*Color filter: {color}*\n")
    lines.append(f"*{qs.count()} spools found*\n")
    lines.append("| ID | Brand | Sub-type | Color | Remaining | In AMS |")
    lines.append("|----|-------|----------|-------|-----------|--------|")
    for f in filaments:
        lines.append(
            f"| {f.id} | {f.brand} | {f.sub_type or f.type} | "
            f"{f.color} | {f.remaining_percent}% | "
            f"{'Yes' if f.is_loaded_in_ams else 'No'} |"
        )
    return "\n".join(lines)


# ─── Resources ───────────────────────────────────────────────────────────────


def resource_printers():
    """List all printers (resource)."""
    return list_printers()


def resource_printer_status(printer_id):
    """Latest printer status (resource)."""
    return get_printer_status(printer_id=printer_id)


def resource_filaments():
    """Full filament inventory (resource)."""
    return list_filaments()


def resource_filament_detail(filament_id):
    """Single spool with usage (resource)."""
    return get_filament_detail(filament_id=filament_id)


def resource_recent_print_jobs():
    """Last 20 print jobs (resource)."""
    return get_print_history(limit=20)


def resource_filament_types():
    """Filament type registry (resource)."""
    from .models import FilamentType

    types = FilamentType.objects.all()
    if not types.exists():
        return "No filament types registered."

    lines = ["# Filament Types", ""]
    lines.append("| ID | Type | Sub-type | Brand |")
    lines.append("|----|------|----------|-------|")
    for t in types:
        lines.append(f"| {t.id} | {t.type} | {t.sub_type or '-'} | {t.brand} |")
    return "\n".join(lines)


def resource_filament_colors():
    """Filament color database (resource)."""
    from .models import FilamentColor

    colors = FilamentColor.objects.all()[:100]
    if not colors:
        return "No filament colors in database."

    lines = ["# Filament Colors", ""]
    lines.append(f"*Showing up to 100 of {FilamentColor.objects.count()}*\n")
    lines.append("| Color | Hex | Type | Sub-type | Brand |")
    lines.append("|-------|-----|------|----------|-------|")
    for c in colors:
        lines.append(
            f"| {c.color_name} | #{c.color_code} | {c.filament_type} | "
            f"{c.filament_sub_type or '-'} | {c.brand} |"
        )
    return "\n".join(lines)


# ─── Prompts ─────────────────────────────────────────────────────────────────


def prompt_printer_check_in(printer_id=None):
    """Full status briefing: status + health + recent prints."""
    parts = [
        get_printer_status(printer_id=printer_id),
        get_printer_health(printer_id=printer_id),
        get_print_history(days=1, limit=5),
    ]
    return "\n\n---\n\n".join(parts)


def prompt_filament_inventory_report():
    """Inventory report with low-stock warnings."""
    from .models import Filament

    low_stock = Filament.objects.filter(remaining_percent__lte=20)
    parts = [list_filaments()]
    if low_stock.exists():
        lines = ["\n## Low Stock Warnings"]
        for f in low_stock:
            lines.append(f"- **{f.brand} {f.type} {f.color}**: {f.remaining_percent}% remaining")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def prompt_print_job_review(job_id):
    """Review a completed job."""
    return get_print_job_detail(job_id)


def prompt_weekly_digest():
    """Weekly activity summary."""
    parts = [
        get_printing_summary(days=7),
        get_filament_usage_stats(days=7, group_by="type"),
    ]
    return "\n\n---\n\n".join(parts)


def prompt_troubleshoot_printer(printer_id=None):
    """Diagnose issues from recent data."""
    parts = [
        get_printer_health(printer_id=printer_id),
        get_printer_status(printer_id=printer_id),
        get_temperature_history(printer_id=printer_id, hours=2),
    ]
    return "\n\n---\n\n".join(parts)
