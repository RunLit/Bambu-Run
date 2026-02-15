"""
Initial migration for bambu_run.

For STANDALONE deployments (fresh SQLite), this creates all tables from scratch.

For RAE integration, this migration should NOT be run directly — instead,
use the SeparateDatabaseAndState migration in the infrastructure app
to transfer model ownership without touching existing tables.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Printer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Printer display name", max_length=200)),
                ("ip_address", models.GenericIPAddressField(blank=True, help_text="Local IP address", null=True)),
                ("serial_number", models.CharField(blank=True, help_text="Printer serial number", max_length=100)),
                ("model", models.CharField(blank=True, help_text="Printer model (e.g., X1C, P1S)", max_length=100)),
                ("is_active", models.BooleanField(default=True, help_text="Whether the printer is actively monitored")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Printer",
                "verbose_name_plural": "Printers",
                "db_table": "infrastructure_device",
            },
        ),
        migrations.CreateModel(
            name="PrinterMetrics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(db_index=True, help_text="When this metric was recorded")),
                ("nozzle_temp", models.FloatField(blank=True, help_text="Nozzle temperature in Celsius", null=True)),
                ("nozzle_target_temp", models.FloatField(blank=True, help_text="Nozzle target temperature", null=True)),
                ("bed_temp", models.FloatField(blank=True, help_text="Bed temperature in Celsius", null=True)),
                ("bed_target_temp", models.FloatField(blank=True, help_text="Bed target temperature", null=True)),
                ("chamber_temp", models.FloatField(blank=True, help_text="Chamber temperature", null=True)),
                ("print_percent", models.IntegerField(blank=True, help_text="Print progress percentage", null=True)),
                ("wifi_signal_dbm", models.IntegerField(blank=True, help_text="WiFi signal strength in dBm", null=True)),
                ("cooling_fan_speed", models.IntegerField(blank=True, help_text="Cooling fan speed (0-15)", null=True)),
                ("heatbreak_fan_speed", models.IntegerField(blank=True, help_text="Heatbreak fan speed (0-15)", null=True)),
                ("gcode_state", models.CharField(blank=True, help_text="Current GCode execution state", max_length=50, null=True)),
                ("subtask_name", models.CharField(blank=True, help_text="Current print subtask name", max_length=255, null=True)),
                ("layer_num", models.IntegerField(blank=True, help_text="Current layer number", null=True)),
                ("total_layer_num", models.IntegerField(blank=True, help_text="Total layer count for current print", null=True)),
                ("chamber_light", models.CharField(blank=True, help_text="Chamber light status (on/off)", max_length=10, null=True)),
                ("ams_humidity_raw", models.IntegerField(blank=True, help_text="AMS raw humidity value", null=True)),
                ("ams_temp", models.FloatField(blank=True, help_text="AMS temperature in Celsius", null=True)),
                ("tray_now", models.CharField(blank=True, help_text="Currently active AMS tray", max_length=10, null=True)),
                ("device", models.ForeignKey(help_text="The printer this metric belongs to", on_delete=django.db.models.deletion.CASCADE, related_name="printer_metrics", to="bambu_run.printer")),
            ],
            options={
                "verbose_name": "Printer Metrics",
                "verbose_name_plural": "Printer Metrics",
                "db_table": "infrastructure_printer_metrics",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.CreateModel(
            name="FilamentType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(help_text="Base material type (PLA, PETG, ABS, etc.)", max_length=50)),
                ("sub_type", models.CharField(blank=True, default="", help_text="Material variant (Basic, Matte, Silk, etc.)", max_length=50)),
                ("brand", models.CharField(help_text="Filament manufacturer", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
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
                ("color_name", models.CharField(help_text="Human-readable color name", max_length=100)),
                ("color_code", models.CharField(help_text="8-char hex color code from printer (RRGGBBFF)", max_length=8)),
                ("filament_type", models.CharField(blank=True, default="", help_text="Material type (legacy field)", max_length=50)),
                ("filament_sub_type", models.CharField(blank=True, default="", help_text="Sub type (legacy field)", max_length=50)),
                ("brand", models.CharField(blank=True, default="", help_text="Brand (legacy field)", max_length=100)),
                ("filament_type_fk", models.ForeignKey(blank=True, help_text="Link to filament type registry", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="colors", to="bambu_run.filamenttype")),
            ],
            options={
                "verbose_name": "Filament Color",
                "verbose_name_plural": "Filament Colors",
                "db_table": "infrastructure_filament_color",
                "ordering": ["filament_type", "color_name"],
            },
        ),
        migrations.CreateModel(
            name="Filament",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tray_uuid", models.CharField(blank=True, db_index=True, help_text="Spool serial number from AMS (unique per spool)", max_length=100, null=True)),
                ("tag_uid", models.CharField(blank=True, db_index=True, help_text="RFID chip UID from AMS tray", max_length=100, null=True)),
                ("tag_id", models.CharField(blank=True, help_text="User-defined tag/barcode ID", max_length=100, null=True)),
                ("type", models.CharField(help_text="Material type (PLA, PETG, ABS, etc.)", max_length=50)),
                ("sub_type", models.CharField(blank=True, default="", help_text="Material sub-type (Basic, Matte, Silk, etc.)", max_length=50)),
                ("brand", models.CharField(default="Unknown", help_text="Filament manufacturer/brand", max_length=100)),
                ("color", models.CharField(help_text="Color name (e.g., Black, White, Red)", max_length=50)),
                ("color_hex", models.CharField(blank=True, help_text="Hex color code (#RRGGBB format)", max_length=9, null=True)),
                ("diameter", models.FloatField(default=1.75, help_text="Filament diameter in mm")),
                ("initial_weight_grams", models.FloatField(blank=True, help_text="Initial spool weight in grams", null=True)),
                ("remaining_percent", models.FloatField(default=100, help_text="Remaining filament percentage (0-100)")),
                ("remaining_weight_grams", models.FloatField(blank=True, help_text="Remaining filament weight in grams", null=True)),
                ("is_loaded_in_ams", models.BooleanField(default=False, help_text="Whether this filament is currently in an AMS tray")),
                ("current_tray_id", models.IntegerField(blank=True, help_text="AMS tray slot (0-3) if loaded", null=True)),
                ("last_loaded_date", models.DateTimeField(blank=True, help_text="When filament was last loaded into AMS", null=True)),
                ("last_used", models.DateTimeField(blank=True, help_text="Last time this filament was used in a print", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.CharField(default="Manual", help_text="How this filament was added (Manual or Auto Detection)", max_length=50)),
                ("purchase_date", models.DateField(blank=True, help_text="When the filament was purchased", null=True)),
                ("purchase_price", models.DecimalField(blank=True, decimal_places=2, help_text="Purchase price", max_digits=8, null=True)),
                ("supplier", models.CharField(blank=True, help_text="Where the filament was purchased", max_length=200, null=True)),
                ("notes", models.TextField(blank=True, help_text="Additional notes about this filament", null=True)),
                ("filament_color", models.ForeignKey(blank=True, help_text="Matched color from database", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="filaments", to="bambu_run.filamentcolor")),
            ],
            options={
                "verbose_name": "Filament",
                "verbose_name_plural": "Filaments",
                "db_table": "infrastructure_filament",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="FilamentSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tray_id", models.IntegerField(help_text="AMS tray slot (0-3)")),
                ("type", models.CharField(blank=True, help_text="Filament type at snapshot time", max_length=50, null=True)),
                ("sub_type", models.CharField(blank=True, help_text="Filament sub-type at snapshot time", max_length=50, null=True)),
                ("color", models.CharField(blank=True, help_text="Hex color code at snapshot time", max_length=20, null=True)),
                ("remain_percent", models.IntegerField(blank=True, help_text="Remaining percentage at snapshot time", null=True)),
                ("tray_uuid", models.CharField(blank=True, help_text="Spool serial number at snapshot time", max_length=100, null=True)),
                ("tag_uid", models.CharField(blank=True, help_text="RFID tag UID at snapshot time", max_length=100, null=True)),
                ("filament", models.ForeignKey(blank=True, help_text="Matched filament from inventory", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="snapshots", to="bambu_run.filament")),
                ("printer_metric", models.ForeignKey(help_text="The printer metric this snapshot belongs to", on_delete=django.db.models.deletion.CASCADE, related_name="filament_snapshots", to="bambu_run.printermetrics")),
            ],
            options={
                "verbose_name": "Filament Snapshot",
                "verbose_name_plural": "Filament Snapshots",
                "db_table": "infrastructure_filament_snapshot",
                "ordering": ["-printer_metric__timestamp"],
            },
        ),
        migrations.CreateModel(
            name="PrintJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project_name", models.CharField(help_text="Name of the print project", max_length=255)),
                ("gcode_file", models.CharField(blank=True, help_text="GCode filename", max_length=255, null=True)),
                ("start_time", models.DateTimeField(db_index=True, help_text="When the print started")),
                ("end_time", models.DateTimeField(blank=True, help_text="When the print ended", null=True)),
                ("final_status", models.CharField(blank=True, help_text="Final status (FINISH, FAILED, etc.)", max_length=50, null=True)),
                ("total_layers", models.IntegerField(blank=True, help_text="Total layers in the print", null=True)),
                ("device", models.ForeignKey(help_text="Printer used for this job", on_delete=django.db.models.deletion.CASCADE, related_name="print_jobs", to="bambu_run.printer")),
                ("start_metric", models.ForeignKey(blank=True, help_text="Metric snapshot at print start", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="started_jobs", to="bambu_run.printermetrics")),
                ("end_metric", models.ForeignKey(blank=True, help_text="Metric snapshot at print end", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ended_jobs", to="bambu_run.printermetrics")),
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
                ("tray_id", models.IntegerField(help_text="AMS tray slot used (0-3)")),
                ("starting_percent", models.FloatField(blank=True, help_text="Filament remaining % at print start", null=True)),
                ("ending_percent", models.FloatField(blank=True, help_text="Filament remaining % at print end", null=True)),
                ("consumed_percent", models.FloatField(blank=True, help_text="Percentage of filament consumed", null=True)),
                ("consumed_grams", models.FloatField(blank=True, help_text="Weight of filament consumed in grams", null=True)),
                ("filament", models.ForeignKey(blank=True, help_text="Which filament spool was used", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_records", to="bambu_run.filament")),
                ("print_job", models.ForeignKey(help_text="The print job that used this filament", on_delete=django.db.models.deletion.CASCADE, related_name="filament_usages", to="bambu_run.printjob")),
            ],
            options={
                "verbose_name": "Filament Usage",
                "verbose_name_plural": "Filament Usages",
                "db_table": "infrastructure_filament_usage",
                "ordering": ["-print_job__start_time"],
            },
        ),
        # Add indexes
        migrations.AddIndex(
            model_name="printermetrics",
            index=models.Index(fields=["device", "-timestamp"], name="infra_pm_device_ts_idx"),
        ),
    ]
