import pytest
from django.urls import reverse
from django.utils import timezone

from bambu_run.models import Printer, PrinterMetrics, Hotend


@pytest.fixture
def logged_in_client(client, django_user_model):
    user = django_user_model.objects.create_user(username="tester", password="pw")
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_dashboard_context_includes_hotends_toolhead_first(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    PrinterMetrics.objects.create(device=printer, timestamp=timezone.now())

    Hotend.objects.create(
        printer=printer, serial_number="RACK-SN", raw_id=16, slot_number=1,
        is_toolhead=False, nozzle_type="HS01", used_time_seconds=3600, wear_percent=50,
    )
    Hotend.objects.create(
        printer=printer, serial_number="TOOLHEAD-SN", raw_id=0, slot_number=None,
        is_toolhead=True, nozzle_type="HS01", used_time_seconds=7200, wear_percent=80,
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    hotends = resp.context["stats"]["hotends"]
    assert len(hotends) == 2
    assert hotends[0].serial_number == "TOOLHEAD-SN"
    assert hotends[1].serial_number == "RACK-SN"


@pytest.mark.django_db
def test_dashboard_context_includes_non_inductive_nozzle_positions(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    PrinterMetrics.objects.create(
        device=printer, timestamp=timezone.now(),
        nozzle_info=[
            {
                "raw_id": 1, "serial_number": "N/A", "nozzle_type": "HS01", "diameter": 0.4,
                "fila_id": "", "color": None, "used_time_seconds": 0, "wear_percent": 0.0,
                "stat": 0, "is_toolhead": False, "is_empty": True, "slot_number": None,
            },
        ],
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    positions = resp.context["stats"]["nozzle_positions"]
    assert len(positions) == 1
    assert positions[0]["nozzle_type"] == "HS01"


@pytest.mark.django_db
def test_dashboard_omits_nozzle_positions_with_no_readable_data(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    PrinterMetrics.objects.create(
        device=printer, timestamp=timezone.now(),
        nozzle_info=[
            {
                "raw_id": 1, "serial_number": "N/A", "nozzle_type": "", "diameter": 0,
                "fila_id": "", "color": None, "used_time_seconds": 0, "wear_percent": 0.0,
                "stat": 0, "is_toolhead": False, "is_empty": True, "slot_number": None,
            },
        ],
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    assert resp.context["stats"]["nozzle_positions"] == []
    assert "<h5>Hotends</h5>" not in resp.content.decode()


@pytest.mark.django_db
def test_dashboard_renders_nozzle_position_without_serial_or_wear(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    PrinterMetrics.objects.create(
        device=printer, timestamp=timezone.now(),
        nozzle_info=[
            {
                "raw_id": 1, "serial_number": "N/A", "nozzle_type": "HS01", "diameter": 0.4,
                "fila_id": "", "color": None, "used_time_seconds": 0, "wear_percent": 0.0,
                "stat": 0, "is_toolhead": False, "is_empty": True, "slot_number": None,
            },
        ],
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    html = resp.content.decode()
    assert "Hotends" in html
    assert "HS01" in html
    assert "SN: N/A" not in html
    assert "SN N/A" not in html


@pytest.mark.django_db
def test_dashboard_renders_hotends_card(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    PrinterMetrics.objects.create(device=printer, timestamp=timezone.now())

    Hotend.objects.create(
        printer=printer, serial_number="RACK-SN", raw_id=18, slot_number=3,
        is_toolhead=False, nozzle_type="HS01", diameter=0.4,
        used_time_seconds=3661, wear_percent=50, last_filament_profile_id="GFA01",
        last_color="DE4343",
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    html = resp.content.decode()
    assert "Hotends" in html
    assert "RACK-SN" in html
    assert "Slot 3" in html
