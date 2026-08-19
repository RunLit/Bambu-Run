import pytest
from datetime import timedelta
from django.utils import timezone

from bambu_run.models import Printer, PrintJob, BambuCloudTask, Filament, FilamentUsage
from bambu_run.mcp.jobs import list_print_jobs, get_print_job, get_print_statistics


@pytest.mark.django_db
def test_list_print_jobs_orders_most_recent_first():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    older = PrintJob.objects.create(device=p, project_name="Old", start_time=now - timedelta(days=1), final_status="FINISH")
    newer = PrintJob.objects.create(device=p, project_name="New", start_time=now, final_status="FINISH")

    result = list_print_jobs()

    assert [j["id"] for j in result["jobs"]] == [newer.id, older.id]


@pytest.mark.django_db
def test_list_print_jobs_filters_by_status_running():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    running = PrintJob.objects.create(device=p, project_name="Live", start_time=timezone.now(), final_status=None)
    PrintJob.objects.create(device=p, project_name="Done", start_time=timezone.now(), final_status="FINISH")

    result = list_print_jobs(status="running")

    assert [j["id"] for j in result["jobs"]] == [running.id]


@pytest.mark.django_db
def test_list_print_jobs_limit_hard_ceiling_100():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    PrintJob.objects.bulk_create([
        PrintJob(device=p, project_name=f"Job {i}", start_time=now - timedelta(hours=i), final_status="FINISH")
        for i in range(150)
    ])

    result = list_print_jobs(limit=1000)

    assert len(result["jobs"]) == 100


@pytest.mark.django_db
def test_list_print_jobs_prefers_cloud_weight_and_tags_source():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    cloud = BambuCloudTask.objects.create(task_id=1, design_title="Cool Bracket", weight_grams=70.10)
    PrintJob.objects.create(
        device=p, project_name="raw_name", start_time=timezone.now(),
        final_status="FINISH", cloud_task=cloud,
    )

    result = list_print_jobs()

    job = result["jobs"][0]
    assert job["display_name"] == "Cool Bracket"
    assert job["filament_grams"] == 70.10
    assert job["filament_grams_source"] == "cloud"
    assert job["cost"] is None


@pytest.mark.django_db
def test_list_print_jobs_display_name_falls_back_to_project_name():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    PrintJob.objects.create(device=p, project_name="raw_project", start_time=timezone.now(), final_status="FINISH")

    result = list_print_jobs()

    assert result["jobs"][0]["display_name"] == "raw_project"


@pytest.mark.django_db
def test_get_print_job_marks_negative_consumption_unreliable():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    job = PrintJob.objects.create(device=p, project_name="Bracket", start_time=timezone.now(), final_status="FINISH")
    filament = Filament.objects.create(type="ABS", brand="Bambu Lab", color="Mint", initial_weight_grams=1000)
    FilamentUsage.objects.create(
        print_job=job, filament=filament, tray_id=0,
        starting_percent=51, ending_percent=52,  # ordinary RFID jitter, spec finding
    )

    result = get_print_job(job.id)

    usage = result["filament_usages"][0]
    assert usage["consumed_grams"] is None
    assert usage["data_quality"] == "unreliable"


@pytest.mark.django_db
def test_get_print_job_computes_estimate_delta_percent():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    cloud = BambuCloudTask.objects.create(task_id=1, cost_time_seconds=205 * 60)
    job = PrintJob.objects.create(
        device=p, project_name="Bracket", start_time=timezone.now(),
        final_status="FINISH", cloud_task=cloud, duration_minutes=237,
    )

    result = get_print_job(job.id)

    assert result["estimate_delta_percent"] == round(100 * (237 - 205) / 205, 1)


@pytest.mark.django_db
def test_get_print_job_unknown_id_raises():
    with pytest.raises(PrintJob.DoesNotExist):
        get_print_job(999999)


@pytest.mark.django_db
def test_get_print_statistics_success_rate_and_status_counts():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    PrintJob.objects.create(device=p, project_name="A", start_time=now, final_status="FINISH")
    PrintJob.objects.create(device=p, project_name="B", start_time=now, final_status="FAILED")

    result = get_print_statistics(days=30)

    assert result["total_jobs"] == 2
    assert result["success_rate"] == 0.5
    assert result["status_counts"]["FINISH"] == 1
    assert result["status_counts"]["FAILED"] == 1


@pytest.mark.django_db
def test_get_print_statistics_material_mix_excludes_negative_consumption():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    job = PrintJob.objects.create(device=p, project_name="A", start_time=timezone.now(), final_status="FINISH")
    pla = Filament.objects.create(type="PLA", brand="Bambu Lab", color="Black", initial_weight_grams=1000)
    abs_f = Filament.objects.create(type="ABS", brand="Bambu Lab", color="White", initial_weight_grams=1000)
    FilamentUsage.objects.create(print_job=job, filament=pla, tray_id=0, starting_percent=74, ending_percent=68)  # 6% -> 60g, valid
    FilamentUsage.objects.create(print_job=job, filament=abs_f, tray_id=1, starting_percent=51, ending_percent=52)  # jitter, excluded

    result = get_print_statistics(days=30)

    assert result["material_mix_grams"] == {"PLA": 60.0}
    assert result["most_used_material"] == "PLA"


@pytest.mark.django_db
def test_get_print_statistics_estimate_accuracy_mean_and_median():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    cloud1 = BambuCloudTask.objects.create(task_id=1, cost_time_seconds=100 * 60)
    cloud2 = BambuCloudTask.objects.create(task_id=2, cost_time_seconds=100 * 60)
    PrintJob.objects.create(
        device=p, project_name="A", start_time=timezone.now(),
        final_status="FINISH", cloud_task=cloud1, duration_minutes=110,
    )
    PrintJob.objects.create(
        device=p, project_name="B", start_time=timezone.now(),
        final_status="FINISH", cloud_task=cloud2, duration_minutes=130,
    )

    result = get_print_statistics(days=30)

    assert result["estimate_accuracy"]["mean_ratio"] == 1.2
    assert result["estimate_accuracy"]["median_ratio"] == 1.2


@pytest.mark.django_db
def test_get_print_statistics_cost_always_null_and_unavailable():
    result = get_print_statistics(days=30)
    assert result["cost_total"] is None
    assert result["cost_available"] is False


@pytest.mark.django_db
def test_get_print_statistics_failures_lists_top_failing_projects():
    p = Printer.objects.create(name="RNL-H2C", model="H2C", is_active=True)
    now = timezone.now()
    PrintJob.objects.create(device=p, project_name="Flaky", start_time=now, final_status="FAILED")
    PrintJob.objects.create(device=p, project_name="Flaky", start_time=now, final_status="FAILED")
    PrintJob.objects.create(device=p, project_name="Solid", start_time=now, final_status="FINISH")

    result = get_print_statistics(days=30)

    assert result["failures"]["count"] == 2
    assert result["failures"]["top_failing_projects"][0] == {"name": "Flaky", "count": 2}
