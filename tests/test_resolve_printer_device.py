import pytest

from bambu_run.management.commands.bambu_collector import resolve_printer_device
from bambu_run.models import Printer


@pytest.mark.django_db
def test_creates_new_printer_keyed_by_serial():
    printer = resolve_printer_device(
        "0309DA123456", {"name": "RNL-H2C", "dev_product_name": "H2C"}
    )

    assert printer.serial_number == "0309DA123456"
    assert printer.name == "RNL-H2C"
    assert printer.model == "H2C"
    assert printer.is_active is True


@pytest.mark.django_db
def test_second_call_with_same_serial_does_not_create_duplicate():
    first = resolve_printer_device("SERIAL-A", {"name": "Printer A", "dev_product_name": "H2C"})
    second = resolve_printer_device("SERIAL-A", {"name": "Printer A", "dev_product_name": "H2C"})

    assert first.pk == second.pk
    assert Printer.objects.filter(serial_number="SERIAL-A").count() == 1


@pytest.mark.django_db
def test_two_different_serials_create_two_printers():
    a = resolve_printer_device("SERIAL-A", {"name": "Printer A", "dev_product_name": "H2C"})
    b = resolve_printer_device("SERIAL-B", {"name": "Printer B", "dev_product_name": "X1C"})

    assert a.pk != b.pk
    assert Printer.objects.count() == 2


@pytest.mark.django_db
def test_backfills_single_legacy_printer_with_null_serial():
    legacy = Printer.objects.create(
        name="Bambu Lab Printer", model="Bambu Lab", manufacturer="Bambu Lab", is_active=True
    )

    resolved = resolve_printer_device("SERIAL-A", {"name": "RNL-H2C", "dev_product_name": "H2C"})

    legacy.refresh_from_db()
    assert resolved.pk == legacy.pk
    assert legacy.serial_number == "SERIAL-A"
    assert Printer.objects.count() == 1


@pytest.mark.django_db
def test_does_not_guess_when_multiple_legacy_printers_exist():
    Printer.objects.create(name="Legacy 1", model="Bambu Lab")
    Printer.objects.create(name="Legacy 2", model="Bambu Lab")

    resolved = resolve_printer_device("SERIAL-A", {"name": "RNL-H2C", "dev_product_name": "H2C"})

    assert resolved.serial_number == "SERIAL-A"
    assert Printer.objects.count() == 3


@pytest.mark.django_db
def test_falls_back_to_generic_defaults_without_device_info():
    printer = resolve_printer_device("SERIAL-A", None)

    assert printer.serial_number == "SERIAL-A"
    assert printer.name == "Bambu Lab Printer"
    assert printer.model == "Bambu Lab"


@pytest.mark.django_db
def test_updates_name_and_model_on_existing_printer_when_changed():
    resolve_printer_device("SERIAL-A", {"name": "Old Name", "dev_product_name": "H2C"})

    updated = resolve_printer_device("SERIAL-A", {"name": "New Name", "dev_product_name": "H2C"})

    assert updated.name == "New Name"
    assert Printer.objects.filter(serial_number="SERIAL-A").count() == 1
