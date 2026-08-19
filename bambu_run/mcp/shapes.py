"""Shared output-shaping helpers enforcing the spec's data-correction rules.

Every rule here traces to a verified finding in "Bambu-Run MCP Tool Surface"
(the "Data Reality Findings" section) -- not a general defensive-programming
habit. Do not relax these without re-checking against real data.
"""
from __future__ import annotations

import statistics

STALE_THRESHOLD_SECONDS = 120
LOW_REMAINING_THRESHOLD = 20


def freshness(timestamp, now):
    """(data_age_seconds, stale) for a reading timestamp relative to `now`.

    `now` is passed in rather than computed here so a caller building a
    multi-field response reuses one `timezone.now()` call throughout,
    keeping `generated_at` and every `data_age_seconds` mutually consistent.
    """
    age_seconds = (now - timestamp).total_seconds()
    return {
        "data_age_seconds": int(age_seconds),
        "stale": age_seconds > STALE_THRESHOLD_SECONDS,
    }


def remaining_status(percent):
    """Classify one raw remaining-percent reading, honoring the -1 sentinel.

    Returns (value, status): value is percent-or-None; status is one of
    "unread" | "empty" | "low" | "ok". -1 and None both mean "no RFID
    reading yet" -- the spec rules out -1 meaning "low" (jobs 62/63/70/77
    show start=-1% followed by end=90-100%, which a genuinely low reading
    could not do).
    """
    if percent is None or percent == -1:
        return None, "unread"
    percent = int(round(percent))
    if percent <= 0:
        return 0, "empty"
    if percent <= LOW_REMAINING_THRESHOLD:
        return percent, "low"
    return percent, "ok"


def smoothed_remaining_percent(readings):
    """Median of the 5 most recent remain_percent readings for one tray.

    `readings` is most-recent-first. -1 sentinel readings are excluded
    before the median, not treated as zero (spec: AMS remain_percent swings
    22-35% mid-print on real RFID noise; median-of-5 rejects single-sample
    spikes while still tracking genuine change).
    """
    recent = readings[:5]
    valid = [r for r in recent if r is not None and r != -1]
    if not valid:
        return remaining_status(-1 if recent else None)
    return remaining_status(statistics.median(valid))


def classify_alerts(code_counts, total_rows):
    """Turn {(attr, code): occurrences} window counts into the alerts array.

    Frequency heuristic (spec: HMS codes are stateful, not event-based --
    the two most common codes alone accounted for over 80% of all alert
    occurrences in the verified data, in long unbroken runs, not isolated
    events): a code present in >20% of window rows is "persistent" (a
    likely standing advisory, surfaced once with a count); <5% is
    "transient" (possibly actionable). The 5-20% band is omitted rather
    than guessed at. severity is always "unknown" -- nothing in Bambu-Run
    decodes these codes yet; do not assert "fine" or "faulty" from them.
    """
    alerts = []
    for (attr, code), count in code_counts.items():
        ratio = count / total_rows if total_rows else 0
        if ratio > 0.20:
            kind = "persistent"
        elif ratio < 0.05:
            kind = "transient"
        else:
            continue
        alerts.append({
            "attr": attr,
            "code": code,
            "kind": kind,
            "occurrences": count,
            "severity": "unknown",
        })
    return alerts


def display_name(design_title, plate_title, project_name):
    """design_title -> plate_title -> project_name fallback.

    Spec finding: design_title is empty on 4 of 5 recent BambuCloudTask rows.
    """
    return design_title or plate_title or project_name


def normalize_consumed(starting_percent, ending_percent, initial_weight_grams):
    """FilamentUsage consumption, honest about the -1 sentinel and RFID jitter.

    Returns (consumed_percent, consumed_grams, data_quality). data_quality is
    "ok" or "unreliable". A negative or sentinel-derived result becomes
    (None, None, "unreliable") -- never a negative figure, never a
    fabricated zero (spec: 24/269 usage rows go negative; a -1 sentinel
    subtracted as a real value produces e.g. consumed=-101%).
    """
    if (
        starting_percent is None or starting_percent == -1
        or ending_percent is None or ending_percent == -1
    ):
        return None, None, "unreliable"
    consumed_percent = starting_percent - ending_percent
    if consumed_percent < 0:
        return None, None, "unreliable"
    consumed_grams = None
    if initial_weight_grams:
        consumed_grams = int(initial_weight_grams * (consumed_percent / 100.0))
    return consumed_percent, consumed_grams, "ok"


def resolve_printer(printer):
    """Resolve an id, exact name, or None to a Printer queryset.

    None returns all active printers. Raises Printer.DoesNotExist if a
    specific id/name was given and nothing matched -- MCP tool wrappers let
    this propagate as a clear tool error rather than returning empty data
    that looks like "no printers exist".
    """
    from bambu_run.models import Printer

    if printer is None:
        return Printer.objects.filter(is_active=True)

    if isinstance(printer, int) or (isinstance(printer, str) and printer.isdigit()):
        by_id = Printer.objects.filter(pk=int(printer))
        if by_id.exists():
            return by_id

    by_name = Printer.objects.filter(name=printer)
    if not by_name.exists():
        raise Printer.DoesNotExist(f"No printer matching {printer!r}")
    return by_name
