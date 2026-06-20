import pytest

from bambu_run.management.commands.bambu_collector import Command, DeviceSession, resolve_printer_device
from bambu_run.models import Filament, FilamentSnapshot, FilamentUsage, PrinterMetrics


class FakeClient:
    """Stub in place of BambuPrinter — returns canned snapshots, no real MQTT."""

    def __init__(self, snapshots):
        self._snapshots = snapshots
        self._index = 0
        self._client = None

    def get_snapshot(self):
        snap = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return snap


def make_session(device_id, name, snapshots):
    printer = resolve_printer_device(device_id, {"name": name, "dev_product_name": "H2C"})
    return DeviceSession(device_id=device_id, client=FakeClient(snapshots), printer=printer)


def two_unit_tray0_snapshot():
    """Two AMS units (AMS unit_id=0, AMS HT unit_id=128) both report tray_id=0,
    with different filament types loaded — these must not collide."""
    return {
        "gcode_state": "IDLE",
        "ams_units": [
            {"unit_id": "0", "ams_type": "AMS", "humidity": 30, "temp": 25.0},
            {"unit_id": "128", "ams_type": "AMS HT", "humidity": 20, "temp": 60.0},
        ],
        "filaments": [
            {
                "tray_id": 0, "type": "PLA", "sub_type": "PLA Basic", "color": "FF0000FF",
                "tray_uuid": "UUID-UNIT0-TRAY0",
                "remain_percent": 80, "ams_unit_id": 0, "ams_type": "AMS",
            },
            {
                "tray_id": 0, "type": "PA-CF", "sub_type": "PA6-CF", "color": "00FF00FF",
                "tray_uuid": "UUID-UNIT128-TRAY0",
                "remain_percent": 50, "ams_unit_id": 128, "ams_type": "AMS HT",
            },
        ],
    }


@pytest.mark.django_db
def test_two_ams_units_with_same_tray_id_create_distinct_snapshots():
    session = make_session("SERIAL-A", "Printer A", [two_unit_tray0_snapshot()])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)

    metric = PrinterMetrics.objects.get(device=session.printer)
    snapshots = FilamentSnapshot.objects.filter(printer_metric=metric).order_by("ams_unit_id")

    assert snapshots.count() == 2

    ams_snap, ht_snap = snapshots
    assert ams_snap.tray_id == 0
    assert ams_snap.ams_unit_id == 0
    assert ams_snap.ams_type == "AMS"
    assert ams_snap.type == "PLA"

    assert ht_snap.tray_id == 0
    assert ht_snap.ams_unit_id == 128
    assert ht_snap.ams_type == "AMS HT"
    assert ht_snap.type == "PA-CF"


@pytest.mark.django_db
def test_filament_usage_matches_correct_unit_when_tray_ids_collide():
    start_snapshot = two_unit_tray0_snapshot()
    start_snapshot.update({"gcode_state": "RUNNING", "subtask_name": "job_1", "print_percent": 1, "tray_now": "0"})

    end_snapshot = two_unit_tray0_snapshot()
    end_snapshot["filaments"][0]["remain_percent"] = 70  # AMS unit 0 consumed
    end_snapshot["filaments"][1]["remain_percent"] = 50  # AMS HT unit 128 untouched
    end_snapshot.update({"gcode_state": "FINISH", "subtask_name": "job_1", "print_percent": 100})

    session = make_session("SERIAL-A", "Printer A", [start_snapshot, end_snapshot])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)
    cmd._collect_printer_data(session)

    usages = FilamentUsage.objects.filter(print_job__device=session.printer).order_by("ams_unit_id")
    # Both units reported tray_id=0 with a tracked filament loaded throughout the
    # job — usage is recorded per physical unit, not collapsed into one ambiguous row.
    assert usages.count() == 2

    ams_usage, ht_usage = usages
    assert ams_usage.ams_unit_id == 0
    assert ams_usage.starting_percent == 80
    assert ams_usage.ending_percent == 70

    assert ht_usage.ams_unit_id == 128
    assert ht_usage.starting_percent == 50
    assert ht_usage.ending_percent == 50
