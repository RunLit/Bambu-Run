import pytest
from datetime import timedelta
from django.utils import timezone

from bambu_run.models import Printer, PrinterMetrics
from bambu_run.mcp.status import get_printer_status


@pytest.mark.django_db
def test_get_printer_status_no_data_yet():
    Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)

    result = get_printer_status()

    assert len(result["printers"]) == 1
    entry = result["printers"][0]
    assert entry["state"] == "no_data"
    assert entry["stale"] is True
    assert entry["job"] is None


@pytest.mark.django_db
def test_get_printer_status_running_job_computes_finish_time():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrinterMetrics.objects.create(
        device=p, timestamp=timezone.now(), gcode_state="RUNNING",
        print_percent=63, layer_num=189, total_layer_num=301,
        remaining_time_min=47, subtask_name="SyncGen LightQube Bracket",
    )

    result = get_printer_status(printer=p.id)

    job = result["printers"][0]["job"]
    assert job["print_percent"] == 63
    assert job["name"] == "SyncGen LightQube Bracket"
    assert job["estimated_finish_at"] is not None


@pytest.mark.django_db
def test_get_printer_status_idle_has_no_job():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrinterMetrics.objects.create(device=p, timestamp=timezone.now(), gcode_state="FINISH")

    result = get_printer_status(printer=p.id)

    assert result["printers"][0]["job"] is None


@pytest.mark.django_db
def test_get_printer_status_stale_when_collector_gap_exceeds_120s():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrinterMetrics.objects.create(
        device=p, timestamp=timezone.now() - timedelta(seconds=200), gcode_state="RUNNING",
    )

    result = get_printer_status(printer=p.id)

    assert result["printers"][0]["stale"] is True


@pytest.mark.django_db
def test_get_printer_status_ams_slot_carries_smoothed_percent_and_status():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    # Same tray, jittering readings across the 3 most recent polls (oldest first).
    for i, pct in enumerate([22, 30, 35]):
        PrinterMetrics.objects.create(
            device=p, timestamp=now - timedelta(seconds=(2 - i) * 30), gcode_state="RUNNING",
            filaments=[{
                "ams_unit_id": 1, "tray_id": "2", "slot": "A01-P3",
                "type": "PLA", "sub_type": "PLA Matte", "color": "E8AFCFFF",
                "remain_percent": pct,
            }],
        )

    result = get_printer_status(printer=p.id)

    unit = result["printers"][0]["ams_units"][0]
    slot = unit["slots"][0]
    assert slot["remain_percent"] == 30  # median of [35, 30, 22] most-recent-first
    assert slot["remain_status"] == "ok"
    assert slot["color_hex"] == "#E8AFCF"


@pytest.mark.django_db
def test_get_printer_status_ams_slot_unread_sentinel():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrinterMetrics.objects.create(
        device=p, timestamp=timezone.now(), gcode_state="RUNNING",
        filaments=[{"ams_unit_id": 0, "tray_id": "0", "type": "ABS", "remain_percent": -1}],
    )

    result = get_printer_status(printer=p.id)

    slot = result["printers"][0]["ams_units"][0]["slots"][0]
    assert slot["remain_percent"] is None
    assert slot["remain_status"] == "unread"


@pytest.mark.django_db
def test_get_printer_status_never_exposes_serial_or_ip():
    p = Printer.objects.create(
        name="RNL-H2C", model="H2C", is_active=True,
        serial_number="SECRET123", ip_address="192.168.1.50",
    )
    PrinterMetrics.objects.create(device=p, timestamp=timezone.now())

    result = get_printer_status(printer=p.id)

    entry_str = repr(result["printers"][0])
    assert "SECRET123" not in entry_str
    assert "192.168.1.50" not in entry_str


@pytest.mark.django_db
def test_get_printer_status_alerts_use_frequency_heuristic_not_hms_emptiness():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    # 1 of 5 rows in the alert window carries an HMS code -- below the 5%
    # "transient" floor at this row count is not meaningful, but the point
    # of this test is that a single non-empty hms row does NOT by itself
    # produce an alert with unconditional certainty; it is classified, not
    # surfaced verbatim. With 1/5 = 20%, exactly at the persistent boundary
    # (not > 20%), so it lands in the omitted band.
    for i in range(5):
        hms = [{"attr": 1, "code": 2}] if i == 0 else []
        PrinterMetrics.objects.create(device=p, timestamp=now - timedelta(minutes=i), hms=hms)

    result = get_printer_status(printer=p.id)

    assert result["printers"][0]["alerts"] == []
