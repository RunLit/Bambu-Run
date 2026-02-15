from django.db import models
from django.utils import timezone


class Printer(models.Model):
    """Represents a Bambu Lab 3D printer device"""

    name = models.CharField(max_length=200, help_text="Friendly device name")
    model = models.CharField(max_length=100, help_text="Device model (e.g., X1C, P1S)")
    manufacturer = models.CharField(
        max_length=100, default="Bambu Lab", help_text="e.g., Bambu Lab"
    )
    description = models.TextField(blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    location = models.CharField(
        max_length=200, blank=True, help_text="Physical location"
    )

    first_seen = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "infrastructure_device"
        verbose_name = "Printer"
        verbose_name_plural = "Printers"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.model})"


class PrinterMetrics(models.Model):
    """Time-series metrics for 3D Printer devices (Bambu Lab)"""

    device = models.ForeignKey(
        Printer, on_delete=models.CASCADE, related_name="printer_metrics", db_index=True
    )
    timestamp = models.DateTimeField(
        default=timezone.now, db_index=True, help_text="When this reading was taken"
    )

    # Temperature metrics
    nozzle_temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    nozzle_target_temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    bed_temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    bed_target_temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    chamber_temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Nozzle info
    nozzle_diameter = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    nozzle_type = models.CharField(max_length=50, null=True, blank=True)

    # Print job status
    gcode_state = models.CharField(
        max_length=50, null=True, blank=True, help_text="FINISH, RUNNING, IDLE, etc."
    )
    print_type = models.CharField(
        max_length=50, null=True, blank=True, help_text="idle, printing, etc."
    )
    print_percent = models.IntegerField(
        null=True, blank=True, help_text="Print progress percentage"
    )
    remaining_time_min = models.IntegerField(
        null=True, blank=True, help_text="Estimated remaining time in minutes"
    )
    layer_num = models.IntegerField(
        null=True, blank=True, help_text="Current layer number"
    )
    total_layer_num = models.IntegerField(
        null=True, blank=True, help_text="Total layers in print"
    )
    print_line_number = models.IntegerField(null=True, blank=True)
    subtask_name = models.CharField(max_length=200, null=True, blank=True)
    gcode_file = models.CharField(max_length=200, null=True, blank=True)

    # Fan speeds (0-100%)
    cooling_fan_speed = models.IntegerField(null=True, blank=True)
    heatbreak_fan_speed = models.IntegerField(null=True, blank=True)
    big_fan1_speed = models.IntegerField(
        null=True, blank=True, help_text="Auxiliary/chamber fan 1 speed"
    )
    big_fan2_speed = models.IntegerField(
        null=True, blank=True, help_text="Auxiliary/chamber fan 2 speed"
    )

    # Speed settings
    spd_lvl = models.IntegerField(
        null=True, blank=True,
        help_text="Speed level (1=silent, 2=standard, 3=sport, 4=ludicrous)",
    )
    spd_mag = models.IntegerField(
        null=True, blank=True, help_text="Speed magnitude percentage"
    )

    # Network & connectivity
    wifi_signal_dbm = models.IntegerField(null=True, blank=True)

    # Error tracking
    print_error = models.IntegerField(default=0)
    has_errors = models.BooleanField(default=False)

    # Chamber light & camera
    chamber_light = models.CharField(
        max_length=20, null=True, blank=True, help_text="on/off"
    )
    ipcam_record = models.CharField(
        max_length=20, null=True, blank=True, help_text="enable/disable"
    )
    timelapse = models.CharField(
        max_length=20, null=True, blank=True, help_text="enable/disable"
    )

    # System info
    stg_cur = models.IntegerField(
        null=True, blank=True, help_text="Current print stage"
    )
    sdcard = models.BooleanField(
        null=True, blank=True, help_text="SD card present"
    )
    gcode_file_prepare_percent = models.CharField(
        max_length=10, null=True, blank=True, help_text="File preparation progress"
    )
    lifecycle = models.CharField(
        max_length=50, null=True, blank=True, help_text="Product lifecycle state"
    )

    # HMS (Health Management System)
    hms = models.JSONField(
        default=list, help_text="Health management system messages (errors/warnings)"
    )

    # AMS (Automatic Material System) status
    ams_unit_count = models.IntegerField(null=True, blank=True)
    ams_status = models.IntegerField(null=True, blank=True)
    ams_rfid_status = models.IntegerField(null=True, blank=True)
    ams_humidity = models.IntegerField(
        null=True, blank=True, help_text="AMS humidity level (processed)"
    )
    ams_humidity_raw = models.IntegerField(
        null=True, blank=True, help_text="AMS raw humidity reading"
    )
    ams_temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    ams_version = models.IntegerField(
        null=True, blank=True, help_text="AMS firmware version"
    )
    tray_is_bbl_bits = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="Which trays have Bambu Lab (OEM) filament",
    )
    tray_read_done_bits = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="RFID read completion status bits",
    )

    # JSON fields for complex nested data
    filaments = models.JSONField(
        default=list,
        help_text="List of filament info [{tray_id, slot, type, sub_type, color, remain_percent, k, ...}]",
    )
    ams_units = models.JSONField(
        default=list,
        help_text="AMS unit info [{unit_id, ams_id, chip_id, humidity, temp, ...}]",
    )
    external_spool = models.JSONField(
        default=dict, help_text="External spool info {type, color, remain}"
    )
    lights_report = models.JSONField(
        default=list, help_text="Light status report [{node, mode}]"
    )

    class Meta:
        db_table = "infrastructure_printer_metrics"
        verbose_name = "Printer Metric"
        verbose_name_plural = "Printer Metrics"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["device", "-timestamp"], name="printer_dev_time_idx"),
            models.Index(fields=["-timestamp"], name="printer_time_idx"),
        ]

    def __str__(self):
        return f"{self.device.name} @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class FilamentType(models.Model):
    """Central registry of filament types (material + sub-type + brand)"""

    type = models.CharField(max_length=50, help_text="Base material: PLA, PETG, ABS, etc.")
    sub_type = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Sub-type: PLA Basic, PLA Matte, etc."
    )
    brand = models.CharField(
        max_length=100, default='Bambu Lab',
        help_text="Manufacturer name"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "infrastructure_filament_type"
        verbose_name = "Filament Type"
        verbose_name_plural = "Filament Types"
        ordering = ['type', 'sub_type', 'brand']
        unique_together = [['type', 'sub_type', 'brand']]

    def __str__(self):
        sub = f" {self.sub_type}" if self.sub_type else ""
        return f"{self.type}{sub} ({self.brand})"


class FilamentColor(models.Model):
    """Master database of Bambu Lab filament colors for auto-matching"""

    color_code = models.CharField(
        max_length=6,
        help_text="Hex color code without padding (e.g., '000000' not '000000FF')"
    )
    color_name = models.CharField(
        max_length=100,
        help_text="Human-readable color name (e.g., 'Black', 'Orange')"
    )

    filament_type_fk = models.ForeignKey(
        'FilamentType', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='colors',
        help_text="Link to FilamentType registry"
    )

    filament_type = models.CharField(
        max_length=50,
        help_text="Base material type: PLA, PETG, ABS, TPU, etc."
    )
    filament_sub_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Material sub-type: 'PLA Basic', 'PLA Matte', 'ABS GF', etc."
    )
    brand = models.CharField(
        max_length=100,
        default='Bambu Lab',
        help_text="Manufacturer name"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "infrastructure_filament_color"
        verbose_name = "Filament Color"
        verbose_name_plural = "Filament Colors"
        ordering = ['filament_type', 'filament_sub_type', 'color_name']
        indexes = [
            models.Index(fields=['color_code', 'filament_type', 'filament_sub_type', 'brand']),
            models.Index(fields=['filament_type']),
        ]
        unique_together = [['color_code', 'filament_type', 'filament_sub_type', 'brand']]

    def __str__(self):
        sub_type_info = f" {self.filament_sub_type}" if self.filament_sub_type else ""
        return f"{self.filament_type}{sub_type_info}: {self.color_name} (#{self.color_code})"

    def get_hex_color(self):
        """Return color code with # prefix for display"""
        return f"#{self.color_code}"


class Filament(models.Model):
    """Master inventory of filament spools owned by user"""

    # Unique identification
    tray_uuid = models.CharField(
        max_length=100, unique=True, null=True, blank=True, db_index=True,
        help_text="Spool serial number from MQTT"
    )
    tag_uid = models.CharField(
        max_length=100, null=True, blank=True, db_index=True,
        help_text="RFID chip unique identifier"
    )
    tag_id = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="User-defined unique identifier (barcode, label, etc.)"
    )

    # Creation tracking
    created_by = models.CharField(
        max_length=20, default='Manual',
        choices=[
            ('Auto Detection', 'Auto Detection'),
            ('Manual', 'Manual'),
        ],
        help_text="How this filament was added to inventory"
    )

    # FK to FilamentType registry
    filament_type = models.ForeignKey(
        'FilamentType', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='filaments',
        help_text="Link to FilamentType registry"
    )

    # Filament specifications
    type = models.CharField(max_length=50, help_text="PLA, PETG, ABS, TPU, etc.")
    sub_type = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Material sub-type from MQTT: 'PLA Matte', 'PLA Basic', etc."
    )
    brand = models.CharField(max_length=100, help_text="Manufacturer name")
    color = models.CharField(max_length=50, help_text="Color name")
    color_hex = models.CharField(
        max_length=7, null=True, blank=True,
        help_text="Color hex code for display (#RRGGBB)"
    )

    # Physical properties
    diameter = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.75,
        help_text="Filament diameter in mm (1.75 or 2.85)"
    )
    initial_weight_grams = models.IntegerField(
        null=True, blank=True,
        help_text="Spool weight when new (typically 1000g)"
    )

    # Current status
    remaining_percent = models.IntegerField(
        default=100,
        help_text="Estimated remaining filament (0-100%)"
    )
    remaining_weight_grams = models.IntegerField(
        null=True, blank=True,
        help_text="Calculated remaining weight"
    )

    # Current location in AMS
    is_loaded_in_ams = models.BooleanField(
        default=False,
        help_text="Is this spool currently loaded in AMS?"
    )
    current_tray_id = models.IntegerField(
        null=True, blank=True,
        help_text="Which AMS slot (0-3) if loaded"
    )
    last_loaded_date = models.DateTimeField(
        null=True, blank=True,
        help_text="When was this spool loaded into AMS"
    )

    # Purchase/inventory tracking
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    supplier = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Custom notes about this spool")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(
        null=True, blank=True,
        help_text="Last time this spool was used in a print"
    )

    class Meta:
        db_table = "infrastructure_filament"
        verbose_name = "Filament Spool"
        verbose_name_plural = "Filament Spools"
        ordering = ['type', 'brand', 'color', '-remaining_percent']
        indexes = [
            models.Index(fields=['type', 'brand', 'color']),
            models.Index(fields=['tray_uuid']),
            models.Index(fields=['tag_uid']),
            models.Index(fields=['tag_id']),
            models.Index(fields=['is_loaded_in_ams', 'current_tray_id']),
            models.Index(fields=['remaining_percent']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        sn_info = f"[SN:{self.tray_uuid[:8]}...] " if self.tray_uuid else ""
        return f"{sn_info}{self.brand} {self.type} - {self.color} ({self.remaining_percent}%)"

    def update_remaining_weight(self):
        """Calculate remaining weight based on percentage"""
        if self.initial_weight_grams:
            self.remaining_weight_grams = int(
                self.initial_weight_grams * (self.remaining_percent / 100.0)
            )


class FilamentSnapshot(models.Model):
    """Links PrinterMetrics to Filament inventory with point-in-time AMS data"""

    printer_metric = models.ForeignKey(
        'PrinterMetrics', on_delete=models.CASCADE,
        related_name='filament_snapshots'
    )
    filament = models.ForeignKey(
        'Filament', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usage_snapshots',
        help_text="Matched filament from inventory (null if no match)"
    )

    tray_id = models.IntegerField(help_text="AMS slot number (0-3)")
    slot_name = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="Slot identifier like A00-W1"
    )

    type = models.CharField(max_length=50, null=True, blank=True)
    sub_type = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Material sub-type from MQTT (PLA Basic, PLA Matte, etc.)"
    )
    brand = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Deprecated: MQTT doesn't provide brand. Use Filament.brand instead."
    )
    color = models.CharField(max_length=50, null=True, blank=True)
    remain_percent = models.IntegerField(null=True, blank=True)
    k_value = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True
    )

    tag_uid = models.CharField(
        max_length=100, null=True, blank=True, db_index=True,
        help_text="RFID chip unique identifier"
    )
    tray_uuid = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Tray UUID from MQTT"
    )
    state = models.IntegerField(
        null=True, blank=True,
        help_text="Tray state from MQTT"
    )

    temp = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    humidity = models.IntegerField(null=True, blank=True)

    auto_matched = models.BooleanField(
        default=True,
        help_text="Was this auto-matched to inventory or manually set?"
    )
    match_method = models.CharField(
        max_length=20, default='none',
        help_text="tag_id, lowest_remaining, manual, or none"
    )

    class Meta:
        db_table = "infrastructure_filament_snapshot"
        verbose_name = "Filament Snapshot"
        verbose_name_plural = "Filament Snapshots"
        ordering = ['printer_metric', 'tray_id']
        indexes = [
            models.Index(fields=['printer_metric', 'tray_id']),
            models.Index(fields=['filament']),
        ]

    def __str__(self):
        filament_info = str(self.filament) if self.filament else f"{self.brand} {self.type}"
        return f"Tray {self.tray_id}: {filament_info}"


class PrintJob(models.Model):
    """Represents a single print job from start to finish"""

    device = models.ForeignKey(
        'Printer', on_delete=models.CASCADE,
        related_name='print_jobs'
    )

    project_name = models.CharField(
        max_length=200, help_text="From subtask_name field"
    )
    gcode_file = models.CharField(max_length=200, null=True, blank=True)

    start_time = models.DateTimeField(help_text="When print started")
    end_time = models.DateTimeField(null=True, blank=True, help_text="When print finished/failed")
    duration_minutes = models.IntegerField(null=True, blank=True, help_text="Total print duration")

    total_layers = models.IntegerField(null=True, blank=True)
    final_status = models.CharField(
        max_length=50, null=True, blank=True, help_text="FINISH, FAILED, CANCELLED"
    )
    completion_percent = models.IntegerField(
        default=0, help_text="Final completion percentage"
    )

    start_metric = models.ForeignKey(
        'PrinterMetrics', on_delete=models.SET_NULL,
        null=True, related_name='started_jobs'
    )
    end_metric = models.ForeignKey(
        'PrinterMetrics', on_delete=models.SET_NULL,
        null=True, related_name='ended_jobs'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "infrastructure_print_job"
        verbose_name = "Print Job"
        verbose_name_plural = "Print Jobs"
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['device', '-start_time']),
            models.Index(fields=['project_name']),
            models.Index(fields=['-start_time']),
        ]

    def __str__(self):
        status = self.final_status or 'In Progress'
        return f"{self.project_name} ({status}) - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def calculate_duration(self):
        """Calculate print duration if end_time is set"""
        if self.end_time and self.start_time:
            delta = self.end_time - self.start_time
            self.duration_minutes = int(delta.total_seconds() / 60)


class FilamentUsage(models.Model):
    """Tracks filament consumption during print jobs"""

    print_job = models.ForeignKey(
        'PrintJob', on_delete=models.CASCADE,
        related_name='filament_usages'
    )
    filament = models.ForeignKey(
        'Filament', on_delete=models.CASCADE,
        related_name='print_usages'
    )

    tray_id = models.IntegerField(help_text="Which AMS slot was used")

    starting_percent = models.IntegerField(help_text="Filament remaining % at job start")
    ending_percent = models.IntegerField(
        null=True, blank=True, help_text="Filament remaining % at job end"
    )
    consumed_percent = models.IntegerField(
        null=True, blank=True, help_text="Amount consumed during print"
    )
    consumed_grams = models.IntegerField(
        null=True, blank=True, help_text="Estimated grams consumed"
    )

    is_primary = models.BooleanField(
        default=True, help_text="Primary filament vs multi-color"
    )

    class Meta:
        db_table = "infrastructure_filament_usage"
        verbose_name = "Filament Usage"
        verbose_name_plural = "Filament Usages"
        ordering = ['print_job', 'tray_id']
        indexes = [
            models.Index(fields=['print_job']),
            models.Index(fields=['filament']),
        ]

    def __str__(self):
        return f"{self.filament} - {self.print_job.project_name} ({self.consumed_percent}%)"

    def calculate_consumed(self):
        """Calculate consumed amount"""
        if self.ending_percent is not None:
            self.consumed_percent = self.starting_percent - self.ending_percent
            if self.filament.initial_weight_grams:
                self.consumed_grams = int(
                    self.filament.initial_weight_grams * (self.consumed_percent / 100.0)
                )
