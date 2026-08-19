import pytest
from django.utils import timezone

from bambu_run.models import Filament, Printer, PrintJob, FilamentUsage
from bambu_run.mcp.filaments import list_filaments, get_filament


@pytest.mark.django_db
def test_list_filaments_filters_material_sub_type_color():
    Filament.objects.create(type="PLA", sub_type="PLA Matte", brand="Bambu Lab", color="Black", remaining_percent=50)
    Filament.objects.create(type="PLA", sub_type="PLA Basic", brand="Bambu Lab", color="Black", remaining_percent=50)
    Filament.objects.create(type="ABS", sub_type="ABS", brand="Bambu Lab", color="Black", remaining_percent=50)

    result = list_filaments(material="PLA", sub_type="PLA Matte", color="black")

    assert len(result["filaments"]) == 1
    assert result["filaments"][0]["sub_type"] == "PLA Matte"


@pytest.mark.django_db
def test_list_filaments_min_remaining_grams_excludes_unread_sentinel():
    Filament.objects.create(type="ABS", brand="Bambu Lab", color="Mint", remaining_percent=-1, remaining_weight_grams=-10)
    Filament.objects.create(type="ABS", brand="Bambu Lab", color="Orange", remaining_percent=68, remaining_weight_grams=680)

    result = list_filaments(material="ABS", min_remaining_grams=250)

    assert len(result["filaments"]) == 1
    assert result["filaments"][0]["color_name"] == "Orange"


@pytest.mark.django_db
def test_list_filaments_min_remaining_grams_excludes_unread_even_with_low_threshold():
    # The existing test only checks min_remaining_grams=250, which happens to
    # exclude a -10g sentinel-derived value anyway. This test uses a threshold
    # low enough that a naive filter would let the sentinel spool through.
    Filament.objects.create(
        type="ABS", brand="Bambu Lab", color="Mint",
        remaining_percent=-1, remaining_weight_grams=-10,
    )
    Filament.objects.create(
        type="ABS", brand="Bambu Lab", color="Orange",
        remaining_percent=68, remaining_weight_grams=680,
    )

    result = list_filaments(material="ABS", min_remaining_grams=-20)

    assert len(result["filaments"]) == 1
    assert result["filaments"][0]["color_name"] == "Orange"


@pytest.mark.django_db
def test_list_filaments_unread_sentinel_status_not_low():
    Filament.objects.create(type="ABS", brand="Bambu Lab", color="Mint", remaining_percent=-1)

    result = list_filaments(material="ABS")

    spool = result["filaments"][0]
    assert spool["remaining_percent"] is None
    assert spool["remaining_status"] == "unread"


@pytest.mark.django_db
def test_list_filaments_limit_hard_ceiling_100():
    Filament.objects.bulk_create([
        Filament(type="PLA", brand="Bambu Lab", color=f"Color {i}", remaining_percent=50)
        for i in range(150)
    ])

    result = list_filaments(limit=1000)

    assert len(result["filaments"]) == 100


@pytest.mark.django_db
def test_list_filaments_include_history_adds_recent_usage():
    f = Filament.objects.create(type="PLA", brand="Bambu Lab", color="White", initial_weight_grams=1000, remaining_percent=80)
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    job = PrintJob.objects.create(device=p, project_name="Vase", start_time=timezone.now(), final_status="FINISH")
    FilamentUsage.objects.create(print_job=job, filament=f, tray_id=0, starting_percent=90, ending_percent=80)

    result = list_filaments(material="PLA", include_history=True)

    history = result["filaments"][0]["recent_usage"]
    assert history[0]["job_name"] == "Vase"
    assert history[0]["consumed_grams"] == 100


@pytest.mark.django_db
def test_list_filaments_never_exposes_rfid_identifiers():
    Filament.objects.create(
        type="PLA", brand="Bambu Lab", color="White",
        tray_uuid="SECRET-UUID", tag_uid="SECRET-TAG",
    )

    result = list_filaments(material="PLA")

    entry_str = repr(result["filaments"][0])
    assert "SECRET-UUID" not in entry_str
    assert "SECRET-TAG" not in entry_str


@pytest.mark.django_db
def test_get_filament_returns_full_usage_history_with_data_quality():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    f = Filament.objects.create(type="ABS", brand="Bambu Lab", color="Black", initial_weight_grams=1000)
    job1 = PrintJob.objects.create(device=p, project_name="Bracket", start_time=timezone.now(), final_status="FINISH")
    job2 = PrintJob.objects.create(device=p, project_name="Vase", start_time=timezone.now(), final_status="FINISH")
    FilamentUsage.objects.create(print_job=job1, filament=f, tray_id=0, starting_percent=80, ending_percent=70)
    FilamentUsage.objects.create(print_job=job2, filament=f, tray_id=0, starting_percent=-1, ending_percent=100)

    result = get_filament(f.id)

    assert len(result["usage_history"]) == 2
    reliable = next(u for u in result["usage_history"] if u["job_name"] == "Bracket")
    unreliable = next(u for u in result["usage_history"] if u["job_name"] == "Vase")
    assert reliable["data_quality"] == "ok"
    assert reliable["consumed_grams"] == 100
    assert unreliable["data_quality"] == "unreliable"
    assert unreliable["consumed_grams"] is None


@pytest.mark.django_db
def test_get_filament_never_exposes_purchase_price_or_cost():
    f = Filament.objects.create(type="PLA", brand="Bambu Lab", color="White", purchase_price=25.50)

    result = get_filament(f.id)

    assert "purchase_price" not in result
    assert "cost" not in result


@pytest.mark.django_db
def test_get_filament_unknown_id_raises():
    with pytest.raises(Filament.DoesNotExist):
        get_filament(999999)
