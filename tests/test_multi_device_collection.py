import pytest

from bambu_run.management.commands.bambu_collector import (
    Command,
    DeviceSession,
    resolve_printer_device,
)
from bambu_run.models import PrintJob, PrinterMetrics


class FakeClient:
    """Stub in place of BambuPrinter — returns canned snapshots, no real MQTT."""

    def __init__(self, snapshots):
        self._snapshots = snapshots
        self._index = 0
        self._client = None  # cloud BambuClient handle used by cloud task sync

    def get_snapshot(self):
        snap = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return snap


def make_session(device_id, name, snapshots):
    printer = resolve_printer_device(device_id, {"name": name, "dev_product_name": "H2C"})
    return DeviceSession(device_id=device_id, client=FakeClient(snapshots), printer=printer)


@pytest.mark.django_db
def test_collects_metrics_against_the_correct_printer_per_session():
    session_a = make_session("SERIAL-A", "Printer A", [{"nozzle_temp": 200, "gcode_state": "IDLE"}])
    session_b = make_session("SERIAL-B", "Printer B", [{"nozzle_temp": 210, "gcode_state": "IDLE"}])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session_a)
    cmd._collect_printer_data(session_b)

    metric_a = PrinterMetrics.objects.get(device=session_a.printer)
    metric_b = PrinterMetrics.objects.get(device=session_b.printer)
    assert metric_a.nozzle_temp == 200
    assert metric_b.nozzle_temp == 210


@pytest.mark.django_db
def test_print_job_tracking_is_isolated_per_session():
    session_a = make_session(
        "SERIAL-A",
        "Printer A",
        [
            {"gcode_state": "RUNNING", "subtask_name": "job_A", "print_percent": 10},
            {"gcode_state": "FINISH", "subtask_name": "job_A", "print_percent": 100},
        ],
    )
    session_b = make_session("SERIAL-B", "Printer B", [{"gcode_state": "IDLE"}])

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session_a)
    cmd._collect_printer_data(session_b)
    cmd._collect_printer_data(session_a)

    assert PrintJob.objects.filter(device=session_a.printer).count() == 1
    job = PrintJob.objects.get(device=session_a.printer)
    assert job.final_status == "FINISH"
    assert session_a.current_print_job is None

    assert PrintJob.objects.filter(device=session_b.printer).count() == 0
    assert session_b.current_print_job is None


@pytest.mark.django_db
def test_one_session_error_does_not_affect_another_session():
    session_a = make_session("SERIAL-A", "Printer A", [{"nozzle_temp": 200, "gcode_state": "IDLE"}])
    session_b = make_session("SERIAL-B", "Printer B", [{"nozzle_temp": 210, "gcode_state": "IDLE"}])

    class ExplodingClient:
        def get_snapshot(self):
            raise RuntimeError("MQTT connection lost")

    session_a.client = ExplodingClient()

    cmd = Command()
    cmd.verbose = False
    cmd._collect_printer_data(session_a)
    cmd._collect_printer_data(session_b)

    assert session_a.error_count == 1
    assert PrinterMetrics.objects.filter(device=session_b.printer).exists()
