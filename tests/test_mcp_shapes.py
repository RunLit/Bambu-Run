import pytest
from datetime import timedelta
from django.utils import timezone

from bambu_run.models import Printer
from bambu_run.mcp.shapes import (
    STALE_THRESHOLD_SECONDS,
    freshness,
    remaining_status,
    smoothed_remaining_percent,
    classify_alerts,
    display_name,
    normalize_consumed,
    resolve_printer,
)


def test_freshness_fresh_reading():
    now = timezone.now()
    ts = now - timedelta(seconds=10)
    assert freshness(ts, now) == {"data_age_seconds": 10, "stale": False}


def test_freshness_stale_reading():
    now = timezone.now()
    ts = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 30)
    result = freshness(ts, now)
    assert result["stale"] is True


def test_remaining_status_unread_sentinel():
    assert remaining_status(-1) == (None, "unread")


def test_remaining_status_none_is_unread():
    assert remaining_status(None) == (None, "unread")


def test_remaining_status_empty():
    assert remaining_status(0) == (0, "empty")


def test_remaining_status_low_boundary():
    assert remaining_status(20) == (20, "low")
    assert remaining_status(21) == (21, "ok")


def test_remaining_status_ok():
    assert remaining_status(72) == (72, "ok")


def test_smoothed_remaining_percent_rejects_spikes():
    # Real data pattern (spec, job 122): genuine values bouncing 22-35%.
    readings = [35, 22, 30, 28, 25]
    assert smoothed_remaining_percent(readings) == (28, "ok")


def test_smoothed_remaining_percent_excludes_unread_sentinel():
    readings = [-1, -1, 90, 88, 91]
    assert smoothed_remaining_percent(readings) == (90, "ok")


def test_smoothed_remaining_percent_all_unread():
    assert smoothed_remaining_percent([-1, -1, -1]) == (None, "unread")


def test_smoothed_remaining_percent_only_uses_5_most_recent():
    readings = [10, 10, 10, 10, 10, 100]
    value, _ = smoothed_remaining_percent(readings)
    assert value == 10


def test_classify_alerts_persistent_above_20_percent():
    counts = {(83887616, 131078): 25}
    assert classify_alerts(counts, total_rows=100) == [{
        "attr": 83887616, "code": 131078,
        "kind": "persistent", "occurrences": 25, "severity": "unknown",
    }]


def test_classify_alerts_transient_below_5_percent():
    counts = {(50336256, 131073): 3}
    alerts = classify_alerts(counts, total_rows=100)
    assert alerts[0]["kind"] == "transient"


def test_classify_alerts_omits_ambiguous_band():
    counts = {(1, 2): 10}  # exactly 10% of 100 rows: neither >20% nor <5%
    assert classify_alerts(counts, total_rows=100) == []


def test_display_name_falls_back_through_chain():
    assert display_name("", "", "raw_project") == "raw_project"
    assert display_name("", "plate_1", "raw_project") == "plate_1"
    assert display_name("Cool Design", "plate_1", "raw_project") == "Cool Design"


def test_normalize_consumed_ordinary_reading():
    assert normalize_consumed(74, 68, initial_weight_grams=1000) == (6, 60, "ok")


def test_normalize_consumed_rfid_jitter_goes_unreliable_not_negative():
    # spec finding: start=51% end=52% -> raw consumed=-1% (ordinary jitter)
    assert normalize_consumed(51, 52, initial_weight_grams=1000) == (None, None, "unreliable")


def test_normalize_consumed_sentinel_start_goes_unreliable():
    # spec finding: jobs 62/63/70/77, start=-1% end=100%
    assert normalize_consumed(-1, 100, initial_weight_grams=1000) == (None, None, "unreliable")


@pytest.mark.django_db
def test_resolve_printer_by_id():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    assert list(resolve_printer(p.id)) == [p]


@pytest.mark.django_db
def test_resolve_printer_by_name():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    assert list(resolve_printer("RNL-H2C")) == [p]


@pytest.mark.django_db
def test_resolve_printer_none_returns_all_active():
    p1 = Printer.objects.create(name="A", model="H2C", is_active=True)
    Printer.objects.create(name="B", model="X1C", is_active=False)
    assert list(resolve_printer(None)) == [p1]


@pytest.mark.django_db
def test_resolve_printer_unknown_name_raises():
    with pytest.raises(Printer.DoesNotExist):
        resolve_printer("nonexistent")
