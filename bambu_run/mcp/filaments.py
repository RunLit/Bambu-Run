"""list_filaments, get_filament -- the read_filament capability tools."""
from __future__ import annotations

from bambu_run.mcp.shapes import normalize_consumed, remaining_status
from bambu_run.models import Filament


def list_filaments(
    material: str | None = None,
    sub_type: str | None = None,
    brand: str | None = None,
    color: str | None = None,
    loaded_only: bool = False,
    min_remaining_percent: int | None = None,
    min_remaining_grams: int | None = None,
    include_history: bool = False,
    limit: int = 50,
) -> dict:
    """Filament spool inventory with composable filters.

    "PLA Matte Black" is material="PLA", sub_type="PLA Matte", color="black".
    "250g of black PLA" is material="PLA", color="black",
    min_remaining_grams=250. remaining_percent/remaining_grams are null when
    the spool's RFID has never been read (remaining_status is "unread" in
    that case, not "low" or "empty"). include_history (default off) adds
    each spool's last 3 uses inline; call get_filament for the complete
    history of one spool. limit hard ceiling is 100.
    """
    limit = min(limit, 100)
    qs = Filament.objects.all()
    if material:
        qs = qs.filter(type__iexact=material)
    if sub_type:
        qs = qs.filter(sub_type__iexact=sub_type)
    if brand:
        qs = qs.filter(brand__icontains=brand)
    if color:
        qs = qs.filter(color__icontains=color)
    if loaded_only:
        qs = qs.filter(is_loaded_in_ams=True)
    if min_remaining_percent is not None:
        qs = qs.exclude(remaining_percent=-1).filter(remaining_percent__gte=min_remaining_percent)
    if min_remaining_grams is not None:
        qs = qs.exclude(remaining_percent=-1).exclude(remaining_weight_grams__isnull=True).filter(remaining_weight_grams__gte=min_remaining_grams)

    spools = [_spool_summary(f, include_history) for f in qs.order_by("-remaining_percent")[:limit]]
    return {"filaments": spools}


def _spool_summary(f, include_history):
    value, status = remaining_status(f.remaining_percent)
    grams = f.remaining_weight_grams
    entry = {
        "id": f.id,
        "material": f.type,
        "sub_type": f.sub_type,
        "brand": f.brand,
        "color_name": f.color,
        "color_hex": f.color_hex,
        "is_transparent": f.is_transparent,
        "remaining_percent": value,
        "remaining_status": status,
        "remaining_grams": grams if (grams is not None and grams >= 0) else None,
        "ams_location": (
            {"unit_id": f.ams_unit_id, "unit_type": f.ams_type, "slot": f.current_tray_id}
            if f.is_loaded_in_ams else None
        ),
        "last_used": f.last_used.isoformat() if f.last_used else None,
    }
    if include_history:
        entry["recent_usage"] = [
            {
                "job_id": u.print_job_id,
                "job_name": u.print_job.project_name,
                "started_at": u.print_job.start_time.isoformat(),
                "consumed_grams": normalize_consumed(
                    u.starting_percent, u.ending_percent, f.initial_weight_grams
                )[1],
            }
            for u in f.print_usages.select_related("print_job").order_by("-print_job__start_time")[:3]
        ]
    return entry
