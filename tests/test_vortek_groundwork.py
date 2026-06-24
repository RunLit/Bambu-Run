import pytest

from bambu_run.mqtt_client import PrinterState
from bambu_run.management.commands.bambu_collector import Command, DeviceSession, resolve_printer_device
from bambu_run.models import PrinterMetrics


def test_snapshot_includes_raw_device_payload_for_future_vortek_modeling():
    raw_device = {
        "extruder": {"info": [{"id": 0, "temp": 12058720}, {"id": 1, "temp": 11534560}]},
        "nozzle": {"info": [{"id": 0, "diameter": 0.4}]},
    }
    data = {"print": {"device": raw_device, "gcode_state": "IDLE"}}

    state = PrinterState.from_mqtt_data(data)
    snapshot = state.get_snapshot()

    assert snapshot["vortek_raw"] == raw_device


def test_snapshot_vortek_raw_defaults_to_empty_dict_when_no_device_payload():
    state = PrinterState.from_mqtt_data({"print": {"gcode_state": "IDLE"}})
    snapshot = state.get_snapshot()

    assert snapshot["vortek_raw"] == {}


@pytest.mark.django_db
def test_collector_persists_vortek_raw_onto_printer_metrics():
    printer = resolve_printer_device("SERIAL-A", {"name": "H2C", "dev_product_name": "H2C"})

    class FakeClient:
        def get_snapshot(self):
            return {"gcode_state": "IDLE", "vortek_raw": {"extruder": {"info": []}}}

    session = DeviceSession(device_id="SERIAL-A", client=FakeClient(), printer=printer)

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session)

    metric = PrinterMetrics.objects.get(device=printer)
    assert metric.vortek_raw == {"extruder": {"info": []}}
