"""get_printer_status, get_metrics_history, get_hardware_health -- the
read_printer capability tools."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from bambu_run.mcp.shapes import classify_alerts, freshness, resolve_printer, smoothed_remaining_percent
from bambu_run.models import Hotend, PrinterMetrics
from bambu_run.utils import strip_color_padding

ALERT_WINDOW_HOURS = 24


def get_printer_status(printer: str | int | None = None) -> dict:
    """Current live status of one or all printers: temps, print progress, AMS slots, and alerts.

    Pass a printer id or exact name to scope to one printer; omit to get every
    active printer. Numeric percentages under ams_units[].slots[] are smoothed
    (median of the 5 most recent readings) and paired with a remain_status
    field ("ok"/"low"/"empty"/"unread") -- treat "unread" as "no RFID reading
    yet", not as "empty". alerts are frequency-classified, not raw fault
    codes; severity is always "unknown" until Bambu's HMS codes are mapped,
    so never assert the printer is fine or faulty purely from an alert entry.
    """
    now = timezone.now()
    printers = resolve_printer(printer)

    entries = []
    for p in printers:
        metric = PrinterMetrics.objects.filter(device=p).order_by("-timestamp").first()
        if metric is None:
            entries.append({
                "id": p.id, "name": p.name, "model": p.model, "location": p.location,
                "data_age_seconds": None, "stale": True, "state": "no_data",
                "job": None, "temperatures": None, "ams_units": [], "alerts": [],
                "fans": None, "chamber_light": None,
            })
            continue

        entries.append({
            "id": p.id,
            "name": p.name,
            "model": p.model,
            "location": p.location,
            **freshness(metric.timestamp, now),
            "state": metric.gcode_state or "UNKNOWN",
            "job": _job_info(metric, now),
            "temperatures": _temperatures(metric),
            "ams_units": _ams_units(p, metric),
            "alerts": _alerts_for_printer(p, now),
            "fans": {
                "cooling_percent": metric.cooling_fan_speed,
                "aux_percent": metric.big_fan1_speed,
                "chamber_percent": metric.big_fan2_speed,
            },
            "chamber_light": metric.chamber_light,
        })

    return {"generated_at": now.isoformat(), "printers": entries}


def _job_info(metric, now):
    if metric.gcode_state != "RUNNING":
        return None
    remaining = metric.remaining_time_min
    finish_at = (now + timedelta(minutes=remaining)).isoformat() if remaining is not None else None
    return {
        "name": metric.subtask_name,
        "print_percent": metric.print_percent,
        "layer_current": metric.layer_num,
        "layer_total": metric.total_layer_num,
        "remaining_time_min": remaining,
        "estimated_finish_at": finish_at,
    }


def _temperatures(metric):
    def f(v):
        return float(v) if v is not None else None
    return {
        "nozzle_c": f(metric.nozzle_temp), "nozzle_target_c": f(metric.nozzle_target_temp),
        "nozzle_left_c": f(metric.nozzle_temp_left), "nozzle_left_target_c": f(metric.nozzle_target_temp_left),
        "bed_c": f(metric.bed_temp), "bed_target_c": f(metric.bed_target_temp),
        "chamber_c": f(metric.chamber_temp),
    }


def _ams_units(printer, latest_metric):
    """Build ams_units from the latest metric's filaments, with remain_percent
    smoothed against the printer's 5 most recent metric rows."""
    recent_filament_lists = list(
        PrinterMetrics.objects.filter(device=printer)
        .order_by("-timestamp")
        .values_list("filaments", flat=True)[:5]
    )
    readings = defaultdict(list)
    for filaments in recent_filament_lists:
        for f in filaments or []:
            key = (f.get("ams_unit_id"), int(f.get("tray_id", -1)))
            readings[key].append(f.get("remain_percent"))

    units = {}
    for f in latest_metric.filaments or []:
        unit_id = f.get("ams_unit_id")
        tray_id = int(f.get("tray_id", -1))
        value, status = smoothed_remaining_percent(readings[(unit_id, tray_id)])
        unit = units.setdefault(unit_id, {
            "unit_id": unit_id,
            "type": f.get("ams_type", ""),
            "humidity_raw": latest_metric.ams_humidity_raw,
            "temp_c": float(latest_metric.ams_temp) if latest_metric.ams_temp is not None else None,
            "slots": [],
        })
        color = f.get("color")
        unit["slots"].append({
            "slot": tray_id,
            "label": f.get("slot", ""),
            "material": f.get("type", ""),
            "sub_type": f.get("sub_type", ""),
            "color_hex": f"#{strip_color_padding(color)}" if color else None,
            "remain_percent": value,
            "remain_status": status,
        })
    return list(units.values())


def _alerts_for_printer(printer, now, window_hours=ALERT_WINDOW_HOURS):
    since = now - timedelta(hours=window_hours)
    window = PrinterMetrics.objects.filter(device=printer, timestamp__gte=since)
    total = window.count()
    counts = defaultdict(int)
    for hms_list in window.exclude(hms=[]).values_list("hms", flat=True):
        for entry in hms_list:
            counts[(entry.get("attr"), entry.get("code"))] += 1
    return classify_alerts(counts, total)


def get_metrics_history(
    printer: str | int | None = None,
    hours: int = 6,
    metrics: list[str] | None = None,
    max_points: int = 300,
) -> dict:
    """Sampled time-series history for one printer: temps, humidity, progress, fans.

    metrics selects which series to include: any of "temps", "humidity",
    "progress", "fans" (omit for all four). Server-side sampled to at most
    max_points (hard ceiling 500) evenly across the window -- do not expect
    one point per collector poll on a long window. printer defaults to the
    first active printer when omitted; pass an id or name explicitly if more
    than one printer is registered.
    """
    from bambu_run.views import sample_metrics  # reuse: same thinning the dashboard already uses

    max_points = min(max_points, 500)
    target = resolve_printer(printer).first()
    if target is None:
        return {"printer": None, "timestamps": [], "series": {}}

    since = timezone.now() - timedelta(hours=hours)
    rows = list(
        PrinterMetrics.objects.filter(device=target, timestamp__gte=since).order_by("timestamp")
    )
    rows = sample_metrics(rows, max_points=max_points)

    wanted = set(metrics) if metrics else {"temps", "humidity", "progress", "fans"}
    series = {}
    if "temps" in wanted:
        series["nozzle_c"] = [float(r.nozzle_temp) if r.nozzle_temp is not None else None for r in rows]
        series["bed_c"] = [float(r.bed_temp) if r.bed_temp is not None else None for r in rows]
        series["chamber_c"] = [float(r.chamber_temp) if r.chamber_temp is not None else None for r in rows]
    if "humidity" in wanted:
        series["ams_humidity_raw"] = [r.ams_humidity_raw for r in rows]
    if "progress" in wanted:
        series["print_percent"] = [r.print_percent for r in rows]
    if "fans" in wanted:
        series["cooling_fan_percent"] = [r.cooling_fan_speed for r in rows]

    return {
        "printer": {"id": target.id, "name": target.name},
        "timestamps": [r.timestamp.isoformat() for r in rows],
        "series": series,
    }
