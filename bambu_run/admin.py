from django.contrib import admin
from .models import Printer, PrinterMetrics, Filament, FilamentType, FilamentSnapshot, PrintJob, FilamentUsage


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = [
        "name", "model", "manufacturer", "ip_address", "is_active", "first_seen",
    ]
    list_filter = ["manufacturer", "is_active"]
    search_fields = ["name", "model", "serial_number", "ip_address"]
    readonly_fields = ["first_seen", "last_updated"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "model", "manufacturer", "description")}),
        ("Identification", {"fields": ("serial_number",)}),
        ("Network", {"fields": ("ip_address",)}),
        ("Status", {"fields": ("is_active", "location")}),
        ("Metadata", {"fields": ("first_seen", "last_updated"), "classes": ("collapse",)}),
    )


@admin.register(PrinterMetrics)
class PrinterMetricsAdmin(admin.ModelAdmin):
    list_display = [
        "device", "timestamp", "nozzle_temp", "bed_temp",
        "print_percent", "gcode_state", "chamber_light",
    ]
    list_filter = ["device", "gcode_state", "print_type", "chamber_light"]
    search_fields = ["device__name", "subtask_name", "gcode_file"]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"

    fieldsets = (
        ("Device & Timestamp", {"fields": ("device", "timestamp")}),
        ("Temperatures", {
            "fields": ("nozzle_temp", "nozzle_target_temp", "bed_temp", "bed_target_temp", "chamber_temp")
        }),
        ("Print Status", {
            "fields": ("gcode_state", "print_type", "print_percent", "remaining_time_min",
                       "layer_num", "total_layer_num", "subtask_name", "gcode_file")
        }),
        ("AMS & Filaments", {
            "fields": ("ams_unit_count", "ams_status", "ams_temp", "ams_humidity",
                       "ams_humidity_raw", "filaments", "external_spool")
        }),
        ("System", {
            "fields": ("chamber_light", "wifi_signal_dbm", "cooling_fan_speed",
                       "heatbreak_fan_speed", "has_errors", "print_error")
        }),
    )


@admin.register(FilamentType)
class FilamentTypeAdmin(admin.ModelAdmin):
    list_display = ('type', 'sub_type', 'brand', 'created_at')
    search_fields = ('type', 'sub_type', 'brand')
    list_filter = ('type', 'brand')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Filament)
class FilamentAdmin(admin.ModelAdmin):
    list_display = (
        'brand', 'type', 'sub_type', 'color', 'remaining_percent',
        'is_loaded_in_ams', 'current_tray_id', 'last_used'
    )
    list_filter = ('type', 'brand', 'is_loaded_in_ams')
    search_fields = ('brand', 'color', 'type', 'tag_id')
    readonly_fields = ('created_at', 'updated_at', 'last_used')

    fieldsets = (
        ('Identification', {'fields': ('tag_id',)}),
        ('Specifications', {
            'fields': ('type', 'sub_type', 'brand', 'color', 'color_hex', 'diameter', 'initial_weight_grams')
        }),
        ('Current Status', {
            'fields': ('remaining_percent', 'remaining_weight_grams',
                       'is_loaded_in_ams', 'current_tray_id', 'last_loaded_date')
        }),
        ('Purchase Info', {'fields': ('purchase_date', 'purchase_price', 'supplier', 'notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'last_used')}),
    )


@admin.register(FilamentSnapshot)
class FilamentSnapshotAdmin(admin.ModelAdmin):
    list_display = ('printer_metric', 'tray_id', 'filament', 'type', 'sub_type', 'tag_uid', 'remain_percent', 'match_method')
    list_filter = ('match_method', 'auto_matched', 'tray_id', 'type')
    search_fields = ('type', 'sub_type', 'brand', 'color', 'tag_uid')
    readonly_fields = ('printer_metric', 'filament', 'auto_matched', 'match_method', 'tag_uid', 'tray_uuid', 'state')


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'device', 'start_time', 'end_time', 'duration_minutes', 'final_status', 'completion_percent')
    list_filter = ('device', 'final_status')
    search_fields = ('project_name', 'gcode_file')
    readonly_fields = ('created_at', 'updated_at', 'duration_minutes')
    date_hierarchy = 'start_time'


@admin.register(FilamentUsage)
class FilamentUsageAdmin(admin.ModelAdmin):
    list_display = ('print_job', 'filament', 'tray_id', 'consumed_percent', 'consumed_grams', 'is_primary')
    list_filter = ('is_primary', 'tray_id')
    readonly_fields = ('consumed_percent', 'consumed_grams')
