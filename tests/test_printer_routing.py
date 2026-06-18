import pytest
from django.urls import reverse

from bambu_run.models import Printer


@pytest.fixture
def logged_in_client(client, django_user_model):
    user = django_user_model.objects.create_user(username="tester", password="pw")
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_dashboard_with_no_printers_shows_error(logged_in_client):
    resp = logged_in_client.get(reverse("bambu_run:printer_dashboard"))
    assert resp.status_code == 200
    assert "error" in resp.context


@pytest.mark.django_db
def test_dashboard_defaults_to_first_active_printer(logged_in_client):
    printer = Printer.objects.create(name="Only Printer", model="H2C", is_active=True)

    resp = logged_in_client.get(reverse("bambu_run:printer_dashboard"))

    assert resp.context["printer_device"].pk == printer.pk
    assert list(resp.context["all_printers"]) == [printer]


@pytest.mark.django_db
def test_dashboard_pk_route_shows_requested_printer(logged_in_client):
    Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    printer_b = Printer.objects.create(name="Printer B", model="X1C", is_active=True)

    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": printer_b.pk})
    )

    assert resp.context["printer_device"].pk == printer_b.pk
    assert resp.context["device_name"] == "Printer B"


@pytest.mark.django_db
def test_dashboard_unknown_pk_returns_404(logged_in_client):
    resp = logged_in_client.get(
        reverse("bambu_run:printer_dashboard", kwargs={"pk": 99999})
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_api_pk_route_returns_only_requested_printer_data(logged_in_client):
    from bambu_run.models import PrinterMetrics
    from django.utils import timezone
    from decimal import Decimal

    printer_a = Printer.objects.create(name="Printer A", model="H2C", is_active=True)
    printer_b = Printer.objects.create(name="Printer B", model="X1C", is_active=True)
    PrinterMetrics.objects.create(device=printer_a, timestamp=timezone.now(), nozzle_temp=Decimal("200"))
    PrinterMetrics.objects.create(device=printer_b, timestamp=timezone.now(), nozzle_temp=Decimal("210"))

    resp = logged_in_client.get(
        reverse("bambu_run:printer_api", kwargs={"pk": printer_b.pk})
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["nozzle_temp"] == [210.0]
