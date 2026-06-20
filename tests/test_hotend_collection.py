import pytest

from bambu_run.management.commands.bambu_collector import Command, DeviceSession, resolve_printer_device
from bambu_run.models import Hotend, HotendSnapshot, PrinterMetrics


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


def hotends_snapshot(used_time=11472, wear=100.0):
    return {
        "gcode_state": "IDLE",
        "hotends": [
            {
                "raw_id": 21, "serial_number": "20D06A5B2918952", "nozzle_type": "HS01",
                "diameter": 0.4, "fila_id": "GFA01", "color": "FFFFFF",
                "used_time_seconds": used_time, "wear_percent": wear, "stat": 0,
                "is_toolhead": False, "is_empty": False, "slot_number": 6,
            },
            {
                "raw_id": 1, "serial_number": "N/A", "nozzle_type": "HS01",
                "diameter": 0.4, "fila_id": "", "color": None,
                "used_time_seconds": 0, "wear_percent": 0.0, "stat": 0,
                "is_toolhead": False, "is_empty": True, "slot_number": None,
            },
            {
                "raw_id": 0, "serial_number": "20D06A5C0426280", "nozzle_type": "HS01",
                "diameter": 0.4, "fila_id": "GFA00", "color": "FEC600",
                "used_time_seconds": 93490, "wear_percent": 100.0, "stat": 0,
                "is_toolhead": True, "is_empty": False, "slot_number": None,
            },
        ],
    }


@pytest.mark.django_db
def test_first_poll_creates_one_hotend_per_non_empty_entry():
    session = make_session("SERIAL-A", "Printer A", [hotends_snapshot()])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)

    hotends = Hotend.objects.filter(printer=session.printer)
    assert hotends.count() == 2  # empty bay (sn="N/A") skipped

    rack = hotends.get(serial_number="20D06A5B2918952")
    assert rack.raw_id == 21
    assert rack.slot_number == 6
    assert rack.is_toolhead is False
    assert rack.used_time_seconds == 11472
    assert rack.wear_percent == 100.0
    assert rack.nozzle_type == "HS01"
    assert rack.last_filament_profile_id == "GFA01"
    assert rack.last_color == "FFFFFF"

    toolhead = hotends.get(serial_number="20D06A5C0426280")
    assert toolhead.is_toolhead is True
    assert toolhead.slot_number is None


@pytest.mark.django_db
def test_first_poll_creates_one_snapshot_per_non_empty_hotend():
    session = make_session("SERIAL-A", "Printer A", [hotends_snapshot()])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)

    metric = PrinterMetrics.objects.get(device=session.printer)
    assert HotendSnapshot.objects.filter(printer_metric=metric).count() == 2


@pytest.mark.django_db
def test_collector_persists_raw_nozzle_info_including_non_inductive_entries():
    session = make_session("SERIAL-A", "Printer A", [hotends_snapshot()])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)

    metric = PrinterMetrics.objects.get(device=session.printer)
    assert len(metric.nozzle_info) == 3  # all entries, including the empty/non-inductive one
    serials = {h["serial_number"] for h in metric.nozzle_info}
    assert serials == {"20D06A5B2918952", "N/A", "20D06A5C0426280"}


@pytest.mark.django_db
def test_second_poll_updates_existing_hotend_instead_of_duplicating():
    session = make_session(
        "SERIAL-A", "Printer A",
        [hotends_snapshot(used_time=11472, wear=100.0), hotends_snapshot(used_time=11500, wear=100.0)],
    )

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)
    cmd._collect_printer_data(session)

    hotends = Hotend.objects.filter(printer=session.printer, serial_number="20D06A5B2918952")
    assert hotends.count() == 1
    assert hotends.first().used_time_seconds == 11500

    snapshots = HotendSnapshot.objects.filter(hotend=hotends.first())
    assert snapshots.count() == 2
