"""
Initial migration for bambu_run.

For STANDALONE deployments (fresh SQLite), this creates all tables from scratch.

For RAE integration, this migration should NOT be run directly — instead,
use the SeparateDatabaseAndState migration in the infrastructure app
to transfer model ownership without touching existing tables.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Printer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Friendly device name", max_length=200)),
                ("model", models.CharField(help_text="Device model (e.g., X1C, P1S)", max_length=100)),
                ("manufacturer", models.CharField(default="Bambu Lab", help_text="e.g., Bambu Lab", max_length=100)),
                ("description", models.TextField(blank=True, null=True)),
                ("serial_number", models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("location", models.CharField(blank=True, help_text="Physical location", max_length=200)),
                ("first_seen", models.DateTimeField(auto_now_add=True)),
                ("last_updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Printer",
                "verbose_name_plural": "Printers",
                "db_table": "infrastructure_device",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="FilamentType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(help_text="Base material: PLA, PETG, ABS, etc.", max_length=50)),
                ("sub_type", models.CharField(blank=True, help_text="Sub-type: PLA Basic, PLA Matte, etc.", max_length=100, null=True)),
                ("brand", models.CharField(default="Bambu Lab", help_text="Manufacturer name", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Filament Type",
                "verbose_name_plural": "Filament Types",
                "db_table": "infrastructure_filament_type",
                "ordering": ["type", "sub_type", "brand"],
                "unique_together": {("type", "sub_type", "brand")},
            },
        ),
        migrations.CreateModel(
            name="FilamentColor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("color_code", models.CharField(help_text="Hex color code without padding (e.g., '000000' not '000000FF')", max_length=6)),
                ("color_name", models.CharField(help_text="Human-readable color name (e.g., 'Black', 'Orange')", max_length=100)),
                ("filament_type_fk", models.ForeignKey(
                    blank=True, help_text="Link to FilamentType registry", null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="colors", to="bambu_run.filamenttype",
                )),
                ("filament_type", models.CharField(help_text="Base material type: PLA, PETG, ABS, TPU, etc.", max_length=50)),
                ("filament_sub_type", models.CharField(blank=True, help_text="Material sub-type: 'PLA Basic', 'PLA Matte', 'ABS GF', etc.", max_length=100, null=True)),
                ("brand", models.CharField(default="Bambu Lab", help_text="Manufacturer name", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Filament Color",
                "verbose_name_plural": "Filament Colors",
                "db_table": "infrastructure_filament_color",
                "ordering": ["filament_type", "filament_sub_type", "color_name"],
                "unique_together": {("color_code", "filament_type", "filament_sub_type", "brand")},
            },
        ),
        migrations.CreateModel(
            name="Filament",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tray_uuid", models.CharField(blank=True, db_index=True, help_text="Spool serial number from MQTT", max_length=100, null=True, unique=True)),
                ("tag_uid", models.CharField(blank=True, db_index=True, help_text="RFID chip unique identifier", max_length=100, null=True)),
                ("tag_id", models.CharField(blank=True, help_text="User-defined unique identifier (barcode, label, etc.)", max_length=100, null=True)),
                ("created_by", models.CharField(
                    choices=[("Auto Detection", "Auto Detection"), ("Manual", "Manual")],
                    default="Manual", help_text="How this filament was added to inventory", max_length=20,
                )),
                ("filament_type", models.ForeignKey(
                    blank=True, help_text="Link to FilamentType registry", null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="filaments", to="bambu_run.filamenttype",
                )),
                ("type", models.CharField(help_text="PLA, PETG, ABS, TPU, etc.", max_length=50)),
                ("sub_type", models.CharField(blank=True, help_text="Material sub-type from MQTT: 'PLA Matte', 'PLA Basic', etc.", max_length=100, null=True)),
                ("brand", models.CharField(help_text="Manufacturer name", max_length=100)),
                ("color", models.CharField(help_text="Color name", max_length=50)),
                ("color_hex", models.CharField(blank=True, help_text="Color hex code for display (#RRGGBB)", max_length=7, null=True)),
                ("diameter", models.DecimalField(decimal_places=2, default=1.75, help_text="Filament diameter in mm (1.75 or 2.85)", max_digits=4)),
                ("initial_weight_grams", models.IntegerField(blank=True, help_text="Spool weight when new (typically 1000g)", null=True)),
                ("remaining_percent", models.IntegerField(default=100, help_text="Estimated remaining filament (0-100%)")),
                ("remaining_weight_grams", models.IntegerField(blank=True, help_text="Calculated remaining weight", null=True)),
                ("is_loaded_in_ams", models.BooleanField(default=False, help_text="Is this spool currently loaded in AMS?")),
                ("current_tray_id", models.IntegerField(blank=True, help_text="Which AMS slot (0-3) if loaded", null=True)),
                ("last_loaded_date", models.DateTimeField(blank=True, help_text="When was this spool loaded into AMS", null=True)),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("purchase_price", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("supplier", models.CharField(blank=True, max_length=100, null=True)),
                ("notes", models.TextField(blank=True, help_text="Custom notes about this spool")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_used", models.DateTimeField(blank=True, help_text="Last time this spool was used in a print", null=True)),
            ],
            options={
                "verbose_name": "Filament Spool",
                "verbose_name_plural": "Filament Spools",
                "db_table": "infrastructure_filament",
                "ordering": ["type", "brand", "color", "-remaining_percent"],
            },
        ),
        migrations.CreateModel(
            name="PrinterMetrics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device", models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="printer_metrics", to="bambu_run.printer",
                )),
                ("timestamp", models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text="When this reading was taken")),
                ("nozzle_temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("nozzle_target_temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("bed_temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("bed_target_temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("chamber_temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("nozzle_diameter", models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True)),
                ("nozzle_type", models.CharField(blank=True, max_length=50, null=True)),
                ("gcode_state", models.CharField(blank=True, help_text="FINISH, RUNNING, IDLE, etc.", max_length=50, null=True)),
                ("print_type", models.CharField(blank=True, help_text="idle, printing, etc.", max_length=50, null=True)),
                ("print_percent", models.IntegerField(blank=True, help_text="Print progress percentage", null=True)),
                ("remaining_time_min", models.IntegerField(blank=True, help_text="Estimated remaining time in minutes", null=True)),
                ("layer_num", models.IntegerField(blank=True, help_text="Current layer number", null=True)),
                ("total_layer_num", models.IntegerField(blank=True, help_text="Total layers in print", null=True)),
                ("print_line_number", models.IntegerField(blank=True, null=True)),
                ("subtask_name", models.CharField(blank=True, max_length=200, null=True)),
                ("gcode_file", models.CharField(blank=True, max_length=200, null=True)),
                ("cooling_fan_speed", models.IntegerField(blank=True, null=True)),
                ("heatbreak_fan_speed", models.IntegerField(blank=True, null=True)),
                ("big_fan1_speed", models.IntegerField(blank=True, help_text="Auxiliary/chamber fan 1 speed", null=True)),
                ("big_fan2_speed", models.IntegerField(blank=True, help_text="Auxiliary/chamber fan 2 speed", null=True)),
                ("spd_lvl", models.IntegerField(blank=True, help_text="Speed level (1=silent, 2=standard, 3=sport, 4=ludicrous)", null=True)),
                ("spd_mag", models.IntegerField(blank=True, help_text="Speed magnitude percentage", null=True)),
                ("wifi_signal_dbm", models.IntegerField(blank=True, null=True)),
                ("print_error", models.IntegerField(default=0)),
                ("has_errors", models.BooleanField(default=False)),
                ("chamber_light", models.CharField(blank=True, help_text="on/off", max_length=20, null=True)),
                ("ipcam_record", models.CharField(blank=True, help_text="enable/disable", max_length=20, null=True)),
                ("timelapse", models.CharField(blank=True, help_text="enable/disable", max_length=20, null=True)),
                ("stg_cur", models.IntegerField(blank=True, help_text="Current print stage", null=True)),
                ("sdcard", models.BooleanField(blank=True, help_text="SD card present", null=True)),
                ("gcode_file_prepare_percent", models.CharField(blank=True, help_text="File preparation progress", max_length=10, null=True)),
                ("lifecycle", models.CharField(blank=True, help_text="Product lifecycle state", max_length=50, null=True)),
                ("hms", models.JSONField(default=list, help_text="Health management system messages (errors/warnings)")),
                ("ams_unit_count", models.IntegerField(blank=True, null=True)),
                ("ams_status", models.IntegerField(blank=True, null=True)),
                ("ams_rfid_status", models.IntegerField(blank=True, null=True)),
                ("ams_humidity", models.IntegerField(blank=True, help_text="AMS humidity level (processed)", null=True)),
                ("ams_humidity_raw", models.IntegerField(blank=True, help_text="AMS raw humidity reading", null=True)),
                ("ams_temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("ams_version", models.IntegerField(blank=True, help_text="AMS firmware version", null=True)),
                ("tray_is_bbl_bits", models.CharField(blank=True, help_text="Which trays have Bambu Lab (OEM) filament", max_length=20, null=True)),
                ("tray_read_done_bits", models.CharField(blank=True, help_text="RFID read completion status bits", max_length=20, null=True)),
                ("filaments", models.JSONField(default=list, help_text="List of filament info [{tray_id, slot, type, sub_type, color, remain_percent, k, ...}]")),
                ("ams_units", models.JSONField(default=list, help_text="AMS unit info [{unit_id, ams_id, chip_id, humidity, temp, ...}]")),
                ("external_spool", models.JSONField(default=dict, help_text="External spool info {type, color, remain}")),
                ("lights_report", models.JSONField(default=list, help_text="Light status report [{node, mode}]")),
            ],
            options={
                "verbose_name": "Printer Metric",
                "verbose_name_plural": "Printer Metrics",
                "db_table": "infrastructure_printer_metrics",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.CreateModel(
            name="FilamentSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("printer_metric", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="filament_snapshots", to="bambu_run.printermetrics",
                )),
                ("filament", models.ForeignKey(
                    blank=True, help_text="Matched filament from inventory (null if no match)",
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="usage_snapshots", to="bambu_run.filament",
                )),
                ("tray_id", models.IntegerField(help_text="AMS slot number (0-3)")),
                ("slot_name", models.CharField(blank=True, help_text="Slot identifier like A00-W1", max_length=20, null=True)),
                ("type", models.CharField(blank=True, max_length=50, null=True)),
                ("sub_type", models.CharField(blank=True, help_text="Material sub-type from MQTT (PLA Basic, PLA Matte, etc.)", max_length=100, null=True)),
                ("brand", models.CharField(blank=True, help_text="Deprecated: MQTT doesn't provide brand. Use Filament.brand instead.", max_length=100, null=True)),
                ("color", models.CharField(blank=True, max_length=50, null=True)),
                ("remain_percent", models.IntegerField(blank=True, null=True)),
                ("k_value", models.DecimalField(blank=True, decimal_places=4, max_digits=6, null=True)),
                ("tag_uid", models.CharField(blank=True, db_index=True, help_text="RFID chip unique identifier", max_length=100, null=True)),
                ("tray_uuid", models.CharField(blank=True, help_text="Tray UUID from MQTT", max_length=100, null=True)),
                ("state", models.IntegerField(blank=True, help_text="Tray state from MQTT", null=True)),
                ("temp", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("humidity", models.IntegerField(blank=True, null=True)),
                ("auto_matched", models.BooleanField(default=True, help_text="Was this auto-matched to inventory or manually set?")),
                ("match_method", models.CharField(default="none", help_text="tag_id, lowest_remaining, manual, or none", max_length=20)),
            ],
            options={
                "verbose_name": "Filament Snapshot",
                "verbose_name_plural": "Filament Snapshots",
                "db_table": "infrastructure_filament_snapshot",
                "ordering": ["printer_metric", "tray_id"],
            },
        ),
        migrations.CreateModel(
            name="PrintJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="print_jobs", to="bambu_run.printer",
                )),
                ("project_name", models.CharField(help_text="From subtask_name field", max_length=200)),
                ("gcode_file", models.CharField(blank=True, max_length=200, null=True)),
                ("start_time", models.DateTimeField(help_text="When print started")),
                ("end_time", models.DateTimeField(blank=True, help_text="When print finished/failed", null=True)),
                ("duration_minutes", models.IntegerField(blank=True, help_text="Total print duration", null=True)),
                ("total_layers", models.IntegerField(blank=True, null=True)),
                ("final_status", models.CharField(blank=True, help_text="FINISH, FAILED, CANCELLED", max_length=50, null=True)),
                ("completion_percent", models.IntegerField(default=0, help_text="Final completion percentage")),
                ("start_metric", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="started_jobs", to="bambu_run.printermetrics",
                )),
                ("end_metric", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ended_jobs", to="bambu_run.printermetrics",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Print Job",
                "verbose_name_plural": "Print Jobs",
                "db_table": "infrastructure_print_job",
                "ordering": ["-start_time"],
            },
        ),
        migrations.CreateModel(
            name="FilamentUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("print_job", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="filament_usages", to="bambu_run.printjob",
                )),
                ("filament", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="print_usages", to="bambu_run.filament",
                )),
                ("tray_id", models.IntegerField(help_text="Which AMS slot was used")),
                ("starting_percent", models.IntegerField(help_text="Filament remaining % at job start")),
                ("ending_percent", models.IntegerField(blank=True, help_text="Filament remaining % at job end", null=True)),
                ("consumed_percent", models.IntegerField(blank=True, help_text="Amount consumed during print", null=True)),
                ("consumed_grams", models.IntegerField(blank=True, help_text="Estimated grams consumed", null=True)),
                ("is_primary", models.BooleanField(default=True, help_text="Primary filament vs multi-color")),
            ],
            options={
                "verbose_name": "Filament Usage",
                "verbose_name_plural": "Filament Usages",
                "db_table": "infrastructure_filament_usage",
                "ordering": ["print_job", "tray_id"],
            },
        ),
        # Indexes for PrinterMetrics
        migrations.AddIndex(
            model_name="printermetrics",
            index=models.Index(fields=["device", "-timestamp"], name="printer_dev_time_idx"),
        ),
        migrations.AddIndex(
            model_name="printermetrics",
            index=models.Index(fields=["-timestamp"], name="printer_time_idx"),
        ),
        # Indexes for FilamentColor
        migrations.AddIndex(
            model_name="filamentcolor",
            index=models.Index(fields=["color_code", "filament_type", "filament_sub_type", "brand"], name="filcolor_lookup_idx"),
        ),
        migrations.AddIndex(
            model_name="filamentcolor",
            index=models.Index(fields=["filament_type"], name="filcolor_type_idx"),
        ),
        # Indexes for Filament
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["type", "brand", "color"], name="filament_type_brand_color_idx"),
        ),
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["tray_uuid"], name="filament_tray_uuid_idx"),
        ),
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["tag_uid"], name="filament_tag_uid_idx"),
        ),
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["tag_id"], name="filament_tag_id_idx"),
        ),
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["is_loaded_in_ams", "current_tray_id"], name="filament_ams_slot_idx"),
        ),
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["remaining_percent"], name="filament_remaining_idx"),
        ),
        migrations.AddIndex(
            model_name="filament",
            index=models.Index(fields=["created_by"], name="filament_created_by_idx"),
        ),
        # Indexes for FilamentSnapshot
        migrations.AddIndex(
            model_name="filamentsnapshot",
            index=models.Index(fields=["printer_metric", "tray_id"], name="filsnap_metric_tray_idx"),
        ),
        migrations.AddIndex(
            model_name="filamentsnapshot",
            index=models.Index(fields=["filament"], name="filsnap_filament_idx"),
        ),
        # Indexes for PrintJob
        migrations.AddIndex(
            model_name="printjob",
            index=models.Index(fields=["device", "-start_time"], name="printjob_dev_time_idx"),
        ),
        migrations.AddIndex(
            model_name="printjob",
            index=models.Index(fields=["project_name"], name="printjob_name_idx"),
        ),
        migrations.AddIndex(
            model_name="printjob",
            index=models.Index(fields=["-start_time"], name="printjob_time_idx"),
        ),
        # Indexes for FilamentUsage
        migrations.AddIndex(
            model_name="filamentusage",
            index=models.Index(fields=["print_job"], name="filusage_job_idx"),
        ),
        migrations.AddIndex(
            model_name="filamentusage",
            index=models.Index(fields=["filament"], name="filusage_filament_idx"),
        ),
    ]
