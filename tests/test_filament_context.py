import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone

from bambu_run.models import Printer, PrinterMetrics, FilamentSnapshot


@pytest.fixture
def logged_in_client(client, django_user_model):
    user = django_user_model.objects.create_user(username="tester", password="pw")
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_dashboard_filaments_carry_ams_unit_info(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    metric = PrinterMetrics.objects.create(device=printer, timestamp=timezone.now())
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=0, ams_type="AMS",
        type="PLA", remain_percent=80,
    )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=128, ams_type="AMS HT",
        type="PA-CF", remain_percent=50,
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    filaments = resp.context["stats"]["filaments"]
    assert len(filaments) == 2
    units = {(f["ams_unit_id"], f["ams_type"]) for f in filaments}
    assert units == {(0, "AMS"), (128, "AMS HT")}

    ams_units = resp.context["stats"]["ams_units"]
    assert ams_units == [
        {"ams_unit_id": 0, "ams_type": "AMS"},
        {"ams_unit_id": 128, "ams_type": "AMS HT"},
    ]


@pytest.mark.django_db
def test_filament_timeline_keeps_same_tray_id_units_separate(logged_in_client):
    from bambu_run.views import PrinterDashboardView

    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    metric = PrinterMetrics.objects.create(device=printer, timestamp=timezone.now())
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=0, ams_type="AMS",
        type="PLA", sub_type="PLA Basic", color="FF0000", remain_percent=80,
    )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=128, ams_type="AMS HT",
        type="PLA", sub_type="PLA Basic", color="FF0000", remain_percent=50,
    )

    view = PrinterDashboardView()
    timeline = view._prepare_filament_timeline(PrinterMetrics.objects.filter(pk=metric.pk))

    assert len(timeline) == 2


@pytest.mark.django_db
def test_dashboard_renders_unit_pills_and_badges_with_multiple_units(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    metric = PrinterMetrics.objects.create(device=printer, timestamp=timezone.now())
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=0, ams_type="AMS",
        type="PLA", color="FF0000FF", remain_percent=80,
    )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=128, ams_type="AMS HT",
        type="PA-CF", color="00FF00FF", remain_percent=50,
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "ams-filter-pills" in html
    assert "ams-badge-ams" in html
    assert "ams-badge-ams-ht" in html
    assert 'data-ams-unit-id="0"' in html
    assert 'data-ams-unit-id="128"' in html


@pytest.mark.django_db
def test_dashboard_groups_filaments_by_ams_unit(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    metric = PrinterMetrics.objects.create(
        device=printer, timestamp=timezone.now(),
        ams_units=[
            {"unit_id": "0", "ams_type": "AMS 2 Pro", "humidity": 5, "temp": 22.5},
            {"unit_id": "128", "ams_type": "AMS HT", "humidity": 8, "temp": 60.0},
        ],
    )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=0, ams_type="AMS 2 Pro",
        type="ABS", remain_percent=80,
    )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=1, ams_unit_id=0, ams_type="AMS 2 Pro",
        type="ABS", remain_percent=60,
    )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=128, ams_type="AMS HT",
        type="PA-CF", remain_percent=50,
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    groups = resp.context["stats"]["ams_groups"]
    assert len(groups) == 2

    ams2pro_group, ht_group = groups
    assert ams2pro_group["unit_id"] == 0
    assert ams2pro_group["label"] == "AMS 2 Pro (Unit 0)"
    assert ams2pro_group["humidity"] == 5
    assert ams2pro_group["temp"] == 22.5
    assert len(ams2pro_group["filaments"]) == 2

    assert ht_group["unit_id"] == 128
    assert ht_group["label"] == "AMS HT (Unit 128)"
    assert ht_group["humidity"] == 8
    assert len(ht_group["filaments"]) == 1


@pytest.mark.django_db
def test_dashboard_renders_wide_and_compact_panels(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    metric = PrinterMetrics.objects.create(
        device=printer, timestamp=timezone.now(),
        ams_units=[
            {"unit_id": "0", "ams_type": "AMS 2 Pro", "humidity": 5, "temp": 22.5},
            {"unit_id": "128", "ams_type": "AMS HT", "humidity": 8, "temp": 60.0},
        ],
    )
    for tray_id in range(4):
        FilamentSnapshot.objects.create(
            printer_metric=metric, tray_id=tray_id, ams_unit_id=0, ams_type="AMS 2 Pro",
            type="ABS", remain_percent=80,
        )
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=128, ams_type="AMS HT",
        type="PA-CF", remain_percent=50,
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    html = resp.content.decode()
    assert "col-12 ams-group" in html        # wide group: col-12 only
    assert "col-lg-3 ams-group" in html      # compact group: col-lg-3
    assert "AMS 2 Pro (Unit 0)" in html
    assert "AMS HT (Unit 128)" in html


@pytest.mark.django_db
def test_dashboard_hides_unit_pills_with_single_unit(logged_in_client):
    printer = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    metric = PrinterMetrics.objects.create(device=printer, timestamp=timezone.now())
    FilamentSnapshot.objects.create(
        printer_metric=metric, tray_id=0, ams_unit_id=0, ams_type="AMS",
        type="PLA", color="FF0000FF", remain_percent=80,
    )

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer.pk})
    )

    assert resp.status_code == 200
    assert "ams-filter-pills" not in resp.content.decode()
