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


from bambu_run.mcp.status import get_metrics_history


@pytest.mark.django_db
def test_get_metrics_history_returns_series_within_window():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    for i in range(3):
        PrinterMetrics.objects.create(
            device=p, timestamp=now - timedelta(hours=i),
            nozzle_temp=200 + i, bed_temp=60, chamber_temp=35,
            print_percent=50 + i, ams_humidity_raw=5, cooling_fan_speed=100,
        )
    PrinterMetrics.objects.create(device=p, timestamp=now - timedelta(hours=10), nozzle_temp=999)

    result = get_metrics_history(printer=p.id, hours=6)

    assert result["printer"]["id"] == p.id
    assert len(result["timestamps"]) == 3
    assert 999.0 not in result["series"]["nozzle_c"]


@pytest.mark.django_db
def test_get_metrics_history_filters_to_requested_metrics():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrinterMetrics.objects.create(device=p, timestamp=timezone.now(), nozzle_temp=200, print_percent=10)

    result = get_metrics_history(printer=p.id, metrics=["progress"])

    assert "print_percent" in result["series"]
    assert "nozzle_c" not in result["series"]


@pytest.mark.django_db
def test_get_metrics_history_hard_ceiling_500_points():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    PrinterMetrics.objects.bulk_create([
        PrinterMetrics(device=p, timestamp=now - timedelta(minutes=i))
        for i in range(600)
    ])

    result = get_metrics_history(printer=p.id, hours=24, max_points=10000)

    assert len(result["timestamps"]) <= 500


@pytest.mark.django_db
def test_get_metrics_history_no_matching_printer_returns_empty_shape():
    result = get_metrics_history(printer=None)
    assert result == {"printer": None, "timestamps": [], "series": {}}


from bambu_run.models import Hotend
from bambu_run.mcp.status import get_hardware_health


@pytest.mark.django_db
def test_get_hardware_health_reports_wifi_and_humidity_averages():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    PrinterMetrics.objects.create(device=p, timestamp=now, wifi_signal_dbm=-50, ams_humidity_raw=4)
    PrinterMetrics.objects.create(device=p, timestamp=now - timedelta(hours=1), wifi_signal_dbm=-60, ams_humidity_raw=6)

    result = get_hardware_health(printer=p.id, days=7)

    assert result["wifi_signal_dbm"]["current"] == -50
    assert result["wifi_signal_dbm"]["window_avg"] == -55.0
    assert result["ams_humidity_raw_window_avg"] == 5.0


@pytest.mark.django_db
def test_get_hardware_health_excludes_wear_percent_field():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrinterMetrics.objects.create(device=p, timestamp=timezone.now())
    Hotend.objects.create(
        printer=p, serial_number="SN1", raw_id=0, is_toolhead=True,
        used_time_seconds=3600, wear_percent=100,
    )

    result = get_hardware_health(printer=p.id)

    hotend = result["hotends"][0]
    assert hotend["used_time_hours"] == 1.0
    assert "wear_percent" not in hotend


@pytest.mark.django_db
def test_get_hardware_health_classifies_persistent_alert():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    for i in range(30):
        PrinterMetrics.objects.create(
            device=p, timestamp=now - timedelta(minutes=i),
            hms=[{"attr": 83887616, "code": 131078}],
        )
    for i in range(30, 100):
        PrinterMetrics.objects.create(device=p, timestamp=now - timedelta(minutes=i), hms=[])

    result = get_hardware_health(printer=p.id, days=1)

    assert result["alerts"][0]["kind"] == "persistent"
    assert result["alerts"][0]["occurrences"] == 30


@pytest.mark.django_db
def test_get_hardware_health_no_printer_returns_empty_shape():
    assert get_hardware_health(printer=None) == {"printer": None}
